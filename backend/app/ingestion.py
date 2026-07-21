import os
import re
import logging
from typing import Dict, List, Any
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Tesseract path
if os.path.exists(settings.TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    logger.info(f"Tesseract OCR path set to {settings.TESSERACT_CMD}")
else:
    # Try default PATH search
    logger.warning(
        f"Tesseract not found at '{settings.TESSERACT_CMD}'. "
        "Will attempt to use system PATH or fall back to native PDF text extraction."
    )

def clean_text(text: str) -> str:
    """
    Cleans extracted text: normalizes whitespace, resolves line breaks,
    fixes common hyphenation splits, and removes noise.
    """
    if not text:
        return ""
    
    # Replace multiple spaces/newlines with single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Fix words split by line-wrap hyphens (e.g. "com- \nponent" or "com-ponent")
    text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)
    text = re.sub(r'(\w+)-\s*(\w+)', r'\1\2', text)
    
    # Remove control characters or excessive non-printable chars
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', text)
    
    return text.strip()

def extract_ocr_from_page(page: fitz.Page, zoom: float = 2.0) -> str:
    """
    Renders a page as a high-resolution image and performs Tesseract OCR.
    """
    try:
        # Create a matrix for higher resolution rendering
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Load pixmap data into PIL Image
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # Run OCR
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        logger.error(f"Error performing OCR on page {page.number + 1}: {str(e)}")
        # Check if tesseract is missing
        if "tesseract is not installed" in str(e).lower() or "no such file" in str(e).lower():
            logger.error("Tesseract binary is missing. OCR failed. Please check installation.")
        return ""

def ingest_pdf(file_path: str, force_ocr: bool = False, min_text_len: int = 50) -> Dict[str, Any]:
    """
    Ingests a PDF file (digital or scanned), extracts text page by page,
    performs OCR if a page is scanned, cleans the text, and returns structured data.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Ingesting PDF: {file_path}")
    doc = fitz.open(file_path)
    
    # Extract document metadata
    metadata = {
        "title": doc.metadata.get("title", "") or os.path.basename(file_path),
        "author": doc.metadata.get("author", ""),
        "subject": doc.metadata.get("subject", ""),
        "keywords": doc.metadata.get("keywords", ""),
        "creator": doc.metadata.get("creator", ""),
        "producer": doc.metadata.get("producer", ""),
        "page_count": len(doc),
        "file_size_bytes": os.path.getsize(file_path)
    }
    
    pages_data = []
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        
        # Try direct text extraction
        extracted_text = page.get_text()
        is_ocr = False
        
        # Detect if page is scanned or empty
        # A page is likely scanned if it has very little text, but has images
        images_list = page.get_images()
        text_length = len(extracted_text.strip())
        
        # Trigger OCR if forced or if direct text is very short and page contains images (or is completely blank)
        should_ocr = force_ocr or (text_length < min_text_len and (len(images_list) > 0 or text_length == 0))
        
        if should_ocr:
            logger.info(f"Page {page_num}: Low digital text detected ({text_length} chars). Running OCR...")
            ocr_text = extract_ocr_from_page(page)
            if ocr_text.strip():
                extracted_text = ocr_text
                is_ocr = True
            else:
                logger.warning(f"Page {page_num}: OCR returned empty text. Falling back to native text.")
        
        cleaned = clean_text(extracted_text)
        
        pages_data.append({
            "page_number": page_num,
            "content": cleaned,
            "is_ocr": is_ocr,
            "char_count": len(cleaned),
            "image_count": len(images_list),
            "dimensions": {
                "width": page.rect.width,
                "height": page.rect.height
            }
        })
        
    doc.close()
    
    return {
        "document_name": os.path.basename(file_path),
        "metadata": metadata,
        "pages": pages_data
    }

if __name__ == "__main__":
    # Test ingestion
    import sys
    import json
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            res = ingest_pdf(test_file)
            print(json.dumps(res, indent=2)[:1000] + "\n...")
        except Exception as ex:
            print(f"Error: {ex}")
    else:
        print("Please provide a PDF file path to test.")
