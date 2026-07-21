import React from 'react';
import {
  Settings,
  MessageSquare,
  Activity,
  ArrowRight
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

interface DocumentItem {
  document_name: string;
  page_count: number;
  max_page: number;
}

interface ChatMessage {
  sender: 'user' | 'agent';
  text: string;
  confidence?: number;
  references?: Array<{
    source: string;
    page: number;
    content: string;
    confidence: number;
  }>;
  route?: string;
}

interface ChatViewProps {
  query: string;
  setQuery: React.Dispatch<React.SetStateAction<string>>;
  chatLog: ChatMessage[];
  chatLoading: boolean;
  filterDoc: string;
  setFilterDoc: React.Dispatch<React.SetStateAction<string>>;
  topK: number;
  setTopK: React.Dispatch<React.SetStateAction<number>>;
  rerankTopN: number;
  setRerankTopN: React.Dispatch<React.SetStateAction<number>>;
  documents: DocumentItem[];
  handleChatSubmit: (e: React.FormEvent) => Promise<void> | void;
}

export default function ChatView({
  query,
  setQuery,
  chatLog,
  chatLoading,
  filterDoc,
  setFilterDoc,
  topK,
  setTopK,
  rerankTopN,
  setRerankTopN,
  documents,
  handleChatSubmit
}: ChatViewProps) {
  return (
    <div className="chat-container">
      <div style={{ display: 'flex', gap: '24px', height: '100%' }}>
        {/* Settings panel left */}
        <div className="card" style={{ width: '280px', flexShrink: 0, padding: '20px' }}>
          <div className="card-title" style={{ fontSize: '0.95rem', marginBottom: '16px' }}>
            <Settings style={{ width: '16px', height: '16px' }} />
            RAG & Router Settings
          </div>
          
          <div className="form-group">
            <label className="form-label">Filter Document Source</label>
            <select
              className="input-field"
              value={filterDoc}
              onChange={(e) => setFilterDoc(e.target.value)}
            >
              <option value="">Search all documents</option>
              {documents.map((d, i) => (
                <option key={i} value={d.document_name}>{d.document_name}</option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px' }}>
              <span>Chroma Retrieve Top-K</span>
              <span className="slider-val">{topK}</span>
            </div>
            <input
              type="range"
              className="range-slider"
              min="5"
              max="25"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
          </div>

          <div className="form-group" style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px' }}>
              <span>Reranker Top-N</span>
              <span className="slider-val">{rerankTopN}</span>
            </div>
            <input
              type="range"
              className="range-slider"
              min="2"
              max="10"
              value={rerankTopN}
              onChange={(e) => setRerankTopN(Number(e.target.value))}
            />
          </div>

          <div style={{ marginTop: '24px', padding: '12px', borderRadius: '8px', border: '1px dashed var(--border-muted)', backgroundColor: 'rgba(0,0,0,0.2)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <p style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>LangGraph Orchestration</p>
            The orchestrator evaluates user queries in real-time, routing compliance checks, predictive data, root cause audits, or standard page queries to their respective agents.
          </div>
        </div>

        {/* Chat message space right */}
        <div className="card" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', padding: '20px' }}>
          <div className="chat-messages">
            {chatLog.length === 0 ? (
              <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '400px', color: 'var(--text-muted)' }}>
                <MessageSquare style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5, color: 'var(--color-primary)' }} />
                <p style={{ fontWeight: 600, color: 'var(--text-title)', marginBottom: '6px' }}>Industrial Expert Q&A Agent</p>
                <p style={{ fontSize: '0.9rem' }}>Ask questions about operations, log incidents for diagnostics, verify Factory Act compliances, or enter telemetry numbers.</p>
              </div>
            ) : (
              chatLog.map((msg, idx) => (
                <div key={idx} className={`chat-bubble ${msg.sender}`} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {msg.sender === 'agent' && msg.route && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                      <Activity style={{ width: '12px', height: '12px' }} />
                      Routed to: {msg.route} Agent
                    </div>
                  )}

                  <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeHighlight]}
                      components={{
                          h1: ({children}) => (
                              <h1 style={{
                                  fontSize: "28px",
                                  fontWeight: 700,
                                  marginBottom: 16,
                                  marginTop: 20
                              }}>
                                  {children}
                              </h1>
                          ),

                          h2: ({children}) => (
                              <h2 style={{
                                  fontSize: "24px",
                                  fontWeight: 700,
                                  marginBottom: 14,
                                  marginTop: 18
                              }}>
                                  {children}
                              </h2>
                          ),

                          h3: ({children}) => (
                              <h3 style={{
                                  fontSize: "20px",
                                  fontWeight: 700,
                                  marginBottom: 12,
                                  marginTop: 16
                              }}>
                                  {children}
                              </h3>
                          ),

                          p: ({children}) => (
                              <p style={{
                                  lineHeight: 1.8,
                                  marginBottom: 12
                              }}>
                                  {children}
                              </p>
                          ),

                          ul: ({children}) => (
                              <ul style={{
                                  paddingLeft: 22,
                                  marginBottom: 14
                              }}>
                                  {children}
                              </ul>
                          ),

                          ol: ({children}) => (
                              <ol style={{
                                  paddingLeft: 22,
                                  marginBottom: 14
                              }}>
                                  {children}
                              </ol>
                          ),

                          li: ({children}) => (
                              <li style={{
                                  marginBottom: 6
                              }}>
                                  {children}
                              </li>
                          ),

                          strong: ({children}) => (
                              <strong style={{
                                  fontWeight: 700
                              }}>
                                  {children}
                              </strong>
                          ),

                          code({inline, children, ...props}: any) {
                              if (inline) {
                                  return (
                                      <code
                                          style={{
                                              background: "#f4f4f4",
                                              padding: "2px 5px",
                                              borderRadius: 4
                                          }}
                                          {...props}
                                      >
                                          {children}
                                      </code>
                                  );
                              }

                              return (
                                  <pre
                                      style={{
                                          background: "#1e1e1e",
                                          color: "white",
                                          padding: 15,
                                          borderRadius: 8,
                                          overflowX: "auto"
                                      }}
                                  >
                                      <code {...props}>{children}</code>
                                  </pre>
                              );
                          }
                      }}
                  >
                      {msg.text}
                  </ReactMarkdown>

                  {msg.sender === 'agent' && msg.confidence !== undefined && (
                    <div style={{ marginTop: '10px' }}>
                      <div className="confidence-wrapper">
                        <span className="confidence-label">Agent Confidence:</span>
                        <div className="confidence-bar">
                          <div
                            className="confidence-fill"
                            style={{
                              width: `${msg.confidence * 100}%`,
                              backgroundColor: msg.confidence > 0.75 ? 'var(--color-success)' : msg.confidence > 0.45 ? 'var(--color-warning)' : 'var(--color-danger)'
                            }}
                          ></div>
                        </div>
                        <span className="confidence-value" style={{
                           color: msg.confidence > 0.75 ? 'var(--color-success)' : msg.confidence > 0.45 ? 'var(--color-warning)' : 'var(--color-danger)'
                        }}>{(msg.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  )}

                  {msg.sender === 'agent' && msg.references && msg.references.length > 0 && (
                    <div className="references-section">
                      <div className="references-title">Source Citations:</div>
                      {msg.references.map((r, rIdx) => (
                        <div key={rIdx} className="reference-card">
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: 'var(--text-title)' }}>
                            <span>[Ref {rIdx + 1}] {r.source} - Page {r.page}</span>
                            <span style={{ color: 'var(--color-secondary)' }}>{(r.confidence * 100).toFixed(0)}% match</span>
                          </div>
                          <div style={{ fontStyle: 'italic', color: 'var(--text-muted)', marginTop: '4px', fontSize: '0.8rem' }}>
                            "{r.content.length > 140 ? r.content.substring(0, 140) + '...' : r.content}"
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            {chatLoading && (
              <div className="chat-bubble agent" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="spinner"></span> LangGraph Router thinking...
              </div>
            )}
          </div>

          <form onSubmit={handleChatSubmit} className="chat-input-bar">
            <input
              type="text"
              className="input-field"
              placeholder="Ask an industrial question, e.g. 'Audit the shaft coupling safety steps' or 'Vibration 8.2 temp 98.5 failed why?'"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={chatLoading}
            />
            <button type="submit" className="btn btn-primary" disabled={chatLoading}>
              <ArrowRight style={{ width: '18px', height: '18px' }} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
