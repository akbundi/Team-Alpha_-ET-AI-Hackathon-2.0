import os
import uuid
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# Try importing ChromaDB
CHROMA_AVAILABLE = False
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    logger.error("chromadb is not installed. RAG functionality will run in mock mode.")

# Try importing SentenceTransformers
SENTENCE_TRANSFORMERS_AVAILABLE = None

from app.config import settings

class RAGEngine:
    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.embedding_model = None
        self.reranker_model = None
        self.api_client = None
        
        self.initialize_models()
        self.initialize_db()

    def initialize_models(self):
        """
        Loads embeddings and reranker models. Falls back to InferenceClient API or mocks.
        """
        global SENTENCE_TRANSFORMERS_AVAILABLE
        
        # Initialize API client if configured
        try:
            from huggingface_hub import InferenceClient
            self.api_client = InferenceClient(api_key=settings.HF_TOKEN if settings.HF_TOKEN else None)
            logger.info("Hugging Face InferenceClient initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Hugging Face InferenceClient: {e}")
            self.api_client = None

        if settings.USE_LOCAL_EMBEDDINGS:
            if SENTENCE_TRANSFORMERS_AVAILABLE is None:
                try:
                    from sentence_transformers import SentenceTransformer, CrossEncoder
                    SENTENCE_TRANSFORMERS_AVAILABLE = True
                except ImportError:
                    logger.warning("sentence-transformers not installed. Embedding and Reranking will use fallback/mock methods.")
                    SENTENCE_TRANSFORMERS_AVAILABLE = False
            
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                try:
                    from sentence_transformers import SentenceTransformer
                    logger.info(f"Loading local Embedding Model: {settings.EMBEDDING_MODEL} (this may take a moment)...")
                    # Using BAAI/bge-large-en-v1.5
                    self.embedding_model = SentenceTransformer(
                        settings.EMBEDDING_MODEL,
                        device="cpu",
                        token=settings.HF_TOKEN if settings.HF_TOKEN else None
                    )
                    logger.info("Local Embedding Model loaded successfully.")
                except Exception as e:
                    logger.error(f"Error loading local embedding model: {e}. Using mock embedding engine.")
                    self.embedding_model = None

                try:
                    from sentence_transformers import CrossEncoder
                    logger.info(f"Loading local Reranker Model: {settings.RERANK_MODEL}...")
                    # Using BAAI/bge-reranker-large
                    self.reranker_model = CrossEncoder(
                        settings.RERANK_MODEL,
                        device="cpu",
                        automodel_args={"token": settings.HF_TOKEN if settings.HF_TOKEN else None},
                        tokenizer_args={"token": settings.HF_TOKEN if settings.HF_TOKEN else None}
                    )
                    logger.info("Local Reranker Model loaded successfully.")
                except Exception as e:
                    logger.error(f"Error loading local reranker model: {e}. Using cosine similarity fallback.")
                    self.reranker_model = None
            else:
                logger.info("Running in API/Mock Embedding mode due to sentence-transformers import failure.")
        else:
            logger.info("Running in API mode (Local sentence-transformers loading bypassed).")

    def initialize_db(self):
        """
        Initializes the persistent ChromaDB collection.
        """
        if not CHROMA_AVAILABLE:
            logger.warning("ChromaDB is unavailable. Skipping collection setup.")
            return

        try:
            os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_DIR,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            # Since we manage embeddings manually, we create a collection without default embedding fn
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"} # Use cosine similarity
            )
            
            # Check for embedding dimensionality mismatch
            if self.collection.count() > 0:
                peek_data = self.collection.peek(limit=1)
                if peek_data and "embeddings" in peek_data and peek_data["embeddings"]:
                    existing_dim = len(peek_data["embeddings"][0])
                    # Get target embedding dimension
                    test_emb = self.get_embedding("test")
                    target_dim = len(test_emb)
                    if existing_dim != target_dim:
                        logger.warning(
                            f"Embedding dimension mismatch detected: "
                            f"Collection has {existing_dim} dimensions, but current model '{settings.EMBEDDING_MODEL}' uses {target_dim}. "
                            f"Recreating collection '{settings.CHROMA_COLLECTION}'..."
                        )
                        self.chroma_client.delete_collection(settings.CHROMA_COLLECTION)
                        self.collection = self.chroma_client.get_or_create_collection(
                            name=settings.CHROMA_COLLECTION,
                            metadata={"hnsw:space": "cosine"}
                        )
            
            logger.info(f"ChromaDB collection '{settings.CHROMA_COLLECTION}' initialized at {settings.CHROMA_DB_DIR}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.collection = None

    def get_embedding(self, text: str) -> List[float]:
        """
        Computes vector embeddings for a given text segment.
        """
        if self.embedding_model is not None:
            try:
                # BGE model recommends adding query instruction for retrieval
                # but for simplicity and page chunk indexing, direct embedding is standard
                emb = self.embedding_model.encode(text, normalize_embeddings=True)
                return emb.tolist()
            except Exception as e:
                logger.error(f"Failed to compute embedding: {e}")
        
        if self.api_client is not None:
            try:
                emb = self.api_client.feature_extraction(
                    text=text,
                    model=settings.EMBEDDING_MODEL
                )
                if hasattr(emb, "tolist"):
                    return emb.tolist()
                elif isinstance(emb, list):
                    if len(emb) > 0 and isinstance(emb[0], list):
                        return emb[0]
                    return emb
            except Exception as e:
                logger.error(f"Failed to compute API embedding: {e}. Falling back to mock.")
        
        # Simple deterministic mock embedding based on character hashing
        return self._generate_mock_embedding(text)

    def _generate_mock_embedding(self, text: str, dimension: int = 1024) -> List[float]:
        """Generates a pseudo-random normalized vector based on the hash of the text."""
        np.random.seed(abs(hash(text)) % 2**32)
        v = np.random.randn(dimension)
        v /= np.linalg.norm(v)
        return v.tolist()

    def chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 120) -> List[str]:
        """
        Splits a text block into overlapping chunks.
        """
        if not text:
            return []
            
        words = text.split()
        if len(words) <= chunk_size // 5: # rough character conversion
            return [text]
            
        chunks = []
        # Character-based recursive splitting logic simplified
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            
            # Try to align end with a sentence or paragraph boundary
            if end < text_len:
                # Look for a period or newline within 50 chars of the end
                boundary = -1
                for i in range(max(start, end - 60), min(text_len, end + 20)):
                    if text[i] in [".", "\n", "?", "!"]:
                        boundary = i
                if boundary != -1:
                    end = boundary + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start >= text_len or end >= text_len:
                break
                
        return chunks

    def add_document(self, doc_data: Dict[str, Any]) -> bool:
        """
        Chunks and inserts document pages into ChromaDB.
        """
        if self.collection is None:
            logger.error("ChromaDB collection is not initialized. Cannot index document.")
            return False
            
        doc_name = doc_data["document_name"]
        pages = doc_data["pages"]
        
        logger.info(f"Indexing document '{doc_name}' into ChromaDB...")
        
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        for page in pages:
            page_num = page["page_number"]
            content = page["content"]
            
            if not content.strip():
                continue
                
            chunks = self.chunk_text(content)
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_name}_p{page_num}_c{idx}_{uuid.uuid4().hex[:6]}"
                
                ids.append(chunk_id)
                documents.append(chunk)
                embeddings.append(self.get_embedding(chunk))
                metadatas.append({
                    "source": doc_name,
                    "page": int(page_num),
                    "chunk_index": int(idx),
                    "is_ocr": bool(page.get("is_ocr", False))
                })
                
        # Insert in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end_idx = min(i + batch_size, len(ids))
            try:
                self.collection.add(
                    ids=ids[i:end_idx],
                    embeddings=embeddings[i:end_idx],
                    metadatas=metadatas[i:end_idx],
                    documents=documents[i:end_idx]
                )
                logger.info(f"Indexed batch {i//batch_size + 1}: Chunks {i} to {end_idx}")
            except Exception as e:
                logger.error(f"Error adding batch to ChromaDB: {e}")
                return False
                
        return True

    def add_document_with_ids(self, doc_data: Dict[str, Any]) -> Optional[List[str]]:
        """
        Chunks and inserts document pages into ChromaDB.
        Returns the list of chunk IDs (for Neo4j bridging) or None on failure.
        This is the preferred method — use add_document() only for backward compat.
        """
        if self.collection is None:
            logger.error("ChromaDB collection is not initialized. Cannot index document.")
            return None

        doc_name = doc_data["document_name"]
        pages = doc_data["pages"]

        logger.info(f"Indexing document '{doc_name}' into ChromaDB (with ID return)...")

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for page in pages:
            page_num = page["page_number"]
            content = page["content"]

            if not content.strip():
                continue

            chunks = self.chunk_text(content)
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_name}_p{page_num}_c{idx}_{uuid.uuid4().hex[:6]}"

                ids.append(chunk_id)
                documents.append(chunk)
                embeddings.append(self.get_embedding(chunk))
                metadatas.append({
                    "source": doc_name,
                    "page": int(page_num),
                    "chunk_index": int(idx),
                    "is_ocr": bool(page.get("is_ocr", False))
                })

        # Insert in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end_idx = min(i + batch_size, len(ids))
            try:
                self.collection.add(
                    ids=ids[i:end_idx],
                    embeddings=embeddings[i:end_idx],
                    metadatas=metadatas[i:end_idx],
                    documents=documents[i:end_idx]
                )
                logger.info(f"Indexed batch {i//batch_size + 1}: Chunks {i} to {end_idx}")
            except Exception as e:
                logger.error(f"Error adding batch to ChromaDB: {e}")
                return None

        return ids  # Return all chunk IDs for Neo4j bridging

    def retrieve(self, query: str, top_k: int = 15, rerank_top_n: int = 5, doc_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant chunks using dense retrieval and BGE Reranker.
        """
        if self.collection is None:
            logger.error("ChromaDB collection not initialized. Cannot retrieve.")
            return []
            
        # Get query embedding
        query_emb = self.get_embedding(query)
        
        # Build filter dictionary if provided
        where_filter = None
        if doc_filter:
            where_filter = {"source": doc_filter}
            
        # 1. Query ChromaDB (returns similarity scores)
        try:
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=min(top_k, self.collection.count() or top_k),
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}")
            return []
            
        # Format initial results
        retrieved_chunks = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            
            for idx in range(len(docs)):
                # Convert distance (cosine distance) to similarity score
                # cosine_similarity = 1 - cosine_distance
                sim_score = 1.0 - dists[idx]
                retrieved_chunks.append({
                    "content": docs[idx],
                    "metadata": metas[idx],
                    "retrieval_score": float(sim_score)
                })
                
        if not retrieved_chunks:
            return []
            
        logger.info(f"Retrieved chunks from ChromaDB: {[(c['metadata']['page'], c['retrieval_score']) for c in retrieved_chunks]}")
            
        # 2. Rerank retrieved chunks
        reranked_chunks = []
        if self.reranker_model is not None:
            try:
                pairs = [[query, chunk["content"]] for chunk in retrieved_chunks]
                # Compute cross-encoder scores (higher score means more relevant)
                scores = self.reranker_model.predict(pairs)
                
                # Attach scores
                for idx, score in enumerate(scores):
                    # Normalize raw logits to standard confidence scale 0-1
                    # Sigmoid function for raw score: 1 / (1 + exp(-x))
                    norm_score = 1.0 / (1.0 + np.exp(-float(score)))
                    retrieved_chunks[idx]["rerank_score"] = norm_score
                    # Combined confidence score
                    retrieved_chunks[idx]["confidence"] = norm_score
                    
                # Sort by rerank score
                reranked = sorted(retrieved_chunks, key=lambda x: x["confidence"], reverse=True)
                reranked_chunks = reranked[:rerank_top_n]
            except Exception as e:
                logger.error(f"Error during reranking: {e}. Falling back to retrieval similarity.")
                reranked_chunks = self._fallback_rerank(retrieved_chunks, rerank_top_n)
        elif self.api_client is not None:
            try:
                import requests
                headers = {}
                if settings.HF_TOKEN:
                    headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
                
                API_URL = f"https://router.huggingface.co/hf-inference/models/{settings.RERANK_MODEL}"
                payload = {
                    "inputs": [
                        {"text": query, "text_pair": chunk["content"]} for chunk in retrieved_chunks
                    ]
                }
                response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
                if response.status_code == 200:
                    scores_data = response.json()
                    if isinstance(scores_data, list) and len(scores_data) > 0 and isinstance(scores_data[0], list):
                        scores_data = scores_data[0]
                    for idx, item in enumerate(scores_data):
                        score = 0.0
                        if isinstance(item, dict):
                            score = float(item.get("score", 0.0))
                        elif isinstance(item, (int, float)):
                            score = float(item)
                        
                        retrieved_chunks[idx]["rerank_score"] = score
                        retrieved_chunks[idx]["confidence"] = score
                        
                    reranked = sorted(retrieved_chunks, key=lambda x: x["confidence"], reverse=True)
                    # Deduplicate by (source, page) to maximize unique page representation
                    unique_reranked = []
                    seen_pages_rerank = set()
                    for chunk in reranked:
                        if chunk.get("metadata") and "page" in chunk["metadata"]:
                            page_key = (chunk["metadata"]["source"], chunk["metadata"]["page"])
                            if page_key in seen_pages_rerank:
                                continue
                            seen_pages_rerank.add(page_key)
                        unique_reranked.append(chunk)
                    reranked_chunks = unique_reranked[:rerank_top_n]
                else:
                    logger.error(f"API Reranking failed (HTTP {response.status_code}): {response.text}")
                    reranked_chunks = self._fallback_rerank(retrieved_chunks, rerank_top_n)
            except Exception as e:
                logger.error(f"Error during API reranking: {e}. Falling back to retrieval similarity.")
                reranked_chunks = self._fallback_rerank(retrieved_chunks, rerank_top_n)
        else:
            reranked_chunks = self._fallback_rerank(retrieved_chunks, rerank_top_n)
            
        logger.info(f"Reranked chunks: {[(c['metadata']['page'], c['confidence']) for c in reranked_chunks]}")
        # Reconstruct full page context for the top reranked chunks to prevent table/list truncation
        final_context_chunks = []
        seen_pages = set()
        
        for chunk in reranked_chunks:
            # Check if metadata and page exist
            if not chunk.get("metadata") or "page" not in chunk["metadata"]:
                final_context_chunks.append(chunk)
                continue
                
            source = chunk["metadata"]["source"]
            page = chunk["metadata"]["page"]
            page_key = (source, page)
            
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            
            try:
                logger.info(f"Reconstructing page context for source={source}, page={page}")
                page_data = self.collection.get(
                    where={
                        "$and": [
                            {"source": {"$eq": source}},
                            {"page": {"$eq": int(page)}}
                        ]
                    }
                )
                logger.info(f"Page data retrieved: found {len(page_data['documents']) if page_data else 0} documents")
                if page_data and page_data["documents"]:
                    # Group and sort chunks by chunk_index, deduplicating duplicates
                    page_chunks = []
                    seen_contents = set()
                    for doc, meta in zip(page_data["documents"], page_data["metadatas"]):
                        if doc in seen_contents:
                            continue
                        seen_contents.add(doc)
                        page_chunks.append({
                            "content": doc,
                            "chunk_index": meta.get("chunk_index", 0)
                        })
                    page_chunks = sorted(page_chunks, key=lambda x: x["chunk_index"])
                    
                    merged_content = ""
                    for pc in page_chunks:
                        if not merged_content:
                            merged_content = pc["content"]
                        else:
                            merged_content += "\n" + pc["content"]
                            
                    final_context_chunks.append({
                        "content": merged_content,
                        "metadata": {
                            "source": source,
                            "page": page
                        },
                        "retrieval_score": chunk.get("retrieval_score", chunk["confidence"]),
                        "confidence": chunk["confidence"]
                    })
                else:
                    logger.warning(f"No documents found on page {page} for source {source}")
                    final_context_chunks.append(chunk)
            except Exception as e:
                logger.error(f"Error reconstructing page context: {e}", exc_info=True)
                final_context_chunks.append(chunk)
                
        if not final_context_chunks:
            return reranked_chunks
            
        return final_context_chunks

    def _fallback_rerank(self, chunks: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        for chunk in chunks:
            # Normalize cosine similarity to confidence (0 to 1)
            chunk["confidence"] = max(0.0, min(1.0, chunk["retrieval_score"]))
            chunk["rerank_score"] = chunk["confidence"]
        
        # Sort by similarity
        sorted_chunks = sorted(chunks, key=lambda x: x["confidence"], reverse=True)
        # Deduplicate by (source, page) to maximize unique page representation
        unique_reranked = []
        seen_pages_rerank = set()
        for chunk in sorted_chunks:
            if chunk.get("metadata") and "page" in chunk["metadata"]:
                page_key = (chunk["metadata"]["source"], chunk["metadata"]["page"])
                if page_key in seen_pages_rerank:
                    continue
                seen_pages_rerank.add(page_key)
            unique_reranked.append(chunk)
        return unique_reranked[:top_n]

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        Lists all document names and their page counts in the collection.
        """
        if self.collection is None:
            return []
            
        try:
            # Retrieve all metadata (just source fields)
            res = self.collection.get(include=["metadatas"])
            metas = res["metadatas"]
            
            if not metas:
                return []
                
            docs = {}
            for m in metas:
                source = m["source"]
                page = m["page"]
                if source not in docs:
                    docs[source] = set()
                docs[source].add(page)
                
            doc_list = []
            for name, pages in docs.items():
                doc_list.append({
                    "document_name": name,
                    "page_count": len(pages),
                    "max_page": max(pages) if pages else 0
                })
            return doc_list
        except Exception as e:
            logger.error(f"Error listing documents in ChromaDB: {e}")
            return []
            
    def delete_document(self, doc_name: str) -> bool:
        """
        Deletes all chunks of a document from ChromaDB.
        """
        if self.collection is None:
            return False
            
        try:
            self.collection.delete(where={"source": doc_name})
            logger.info(f"Deleted document '{doc_name}' from ChromaDB.")
            return True
        except Exception as e:
            logger.error(f"Error deleting document '{doc_name}': {e}")
            return False

# Singleton instance
rag_engine = RAGEngine()
