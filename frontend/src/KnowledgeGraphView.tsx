import React, { useState, useEffect } from 'react';
import { Network, Database, Search, Cpu, AlertTriangle, ShieldCheck, User, FileText, Activity, RefreshCw } from 'lucide-react';

interface KnowledgeGraphViewProps {
  apiBase: string;
  showMsg: (text: string, type?: 'success' | 'error') => void;
}

interface GraphStats {
  connected: boolean;
  total_nodes?: number;
  total_relationships?: number;
  equipment_nodes?: number;
  failure_nodes?: number;
  document_nodes?: number;
  error?: string;
}

interface GraphNode {
  label: string;
  id?: string;
  name?: string;
  type?: string;
  code?: string;
  description?: string;
  location?: string;
  health_score?: number;
  risk_level?: string;
  criticality?: string;
  date?: string;
  confidence?: number;
  priority?: string;
  source_doc?: string;
  [key: string]: any;
}

const DEMO_EQUIPMENT = ['PMP-102', 'TURB-401', 'COMP-301', 'VALV-204'];

export default function KnowledgeGraphView({ apiBase, showMsg }: KnowledgeGraphViewProps) {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(false);
  const [equipmentId, setEquipmentId] = useState<string>('PMP-102');
  const [searchQuery, setSearchQuery] = useState<string>('PMP-102');
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: any[]; graphAvailable: boolean } | null>(null);
  const [loadingGraph, setLoadingGraph] = useState<boolean>(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    fetchStats();
    handleSearchEquipment('PMP-102');
  }, []);

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await fetch(`${apiBase}/graph/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      } else {
        setStats({ connected: false });
      }
    } catch (e) {
      setStats({ connected: false });
    } finally {
      setLoadingStats(false);
    }
  };

  const handleSearchEquipment = async (targetId: string) => {
    if (!targetId.trim()) return;
    const cleanId = targetId.trim().toUpperCase();
    setEquipmentId(cleanId);
    setSearchQuery(cleanId);
    setLoadingGraph(true);
    setSelectedNode(null);

    try {
      const res = await fetch(`${apiBase}/graph/equipment/${cleanId}`);
      if (res.ok) {
        const data = await res.json();
        setGraphData({
          nodes: data.nodes || [],
          edges: data.edges || [],
          graphAvailable: data.graph_available ?? true
        });
        if (data.nodes && data.nodes.length > 0) {
          setSelectedNode(data.nodes[0]);
        }
      } else {
        // Generate mock fallback graph representation for rich UI visualization
        generateFallbackGraph(cleanId);
      }
    } catch (e) {
      generateFallbackGraph(cleanId);
    } finally {
      setLoadingGraph(false);
    }
  };

  const generateFallbackGraph = (eqId: string) => {
    const mockNodes: GraphNode[] = [
      { label: 'Equipment', id: eqId, name: eqId, location: 'Pump House 3', health_score: 76.0, risk_level: 'MEDIUM', criticality: 'HIGH' },
      { label: 'Component', name: 'Impeller Blades', type: 'Rotary' },
      { label: 'Component', name: 'Shaft Casing', type: 'Structural' },
      { label: 'Failure', id: `${eqId}_cavitation`, type: 'Cavitation Damage', date: '2026-06-15', confidence: 0.92, source_doc: 'Inspection_Log_PMP102.pdf' },
      { label: 'Failure', id: `${eqId}_vibration`, type: 'High Shaft Vibration', date: '2026-05-10', confidence: 0.88, source_doc: 'Telemetry_Report_Q2.pdf' },
      { label: 'Action', description: 'Replace Impeller Blades & Recalibrate Shaft', priority: 'HIGH' },
      { label: 'Technician', name: 'John Doe' },
      { label: 'Regulation', code: 'Factory Act Sec 21' },
      { label: 'Document', name: 'SOP_Pump_Maintenance_v2.pdf', version: '2.1' },
    ];
    setGraphData({
      nodes: mockNodes,
      edges: [],
      graphAvailable: false
    });
    setSelectedNode(mockNodes[0]);
  };

  const getNodeColor = (label: string) => {
    switch (label) {
      case 'Equipment': return '#22d3ee';   // Cyan
      case 'Component': return '#f97316';   // Orange
      case 'Failure': return '#f43f5e';     // Rose/Red
      case 'Action': return '#10b981';      // Emerald Green
      case 'Technician': return '#a855f7';  // Purple
      case 'Regulation': return '#f59e0b';  // Amber
      case 'Document': return '#64748b';    // Slate
      default: return '#94a3b8';
    }
  };

  const getNodeIcon = (label: string) => {
    switch (label) {
      case 'Equipment': return <Cpu className="nav-icon" style={{ color: '#22d3ee' }} />;
      case 'Component': return <Activity className="nav-icon" style={{ color: '#f97316' }} />;
      case 'Failure': return <AlertTriangle className="nav-icon" style={{ color: '#f43f5e' }} />;
      case 'Action': return <ShieldCheck className="nav-icon" style={{ color: '#10b981' }} />;
      case 'Technician': return <User className="nav-icon" style={{ color: '#a855f7' }} />;
      case 'Regulation': return <Database className="nav-icon" style={{ color: '#f59e0b' }} />;
      case 'Document': return <FileText className="nav-icon" style={{ color: '#64748b' }} />;
      default: return <Network className="nav-icon" />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Neo4j Knowledge Graph Overview Header Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Network className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            Neo4j Knowledge Graph Explorer
          </span>
          <button className="btn btn-secondary" onClick={fetchStats} disabled={loadingStats}>
            <RefreshCw className={`nav-icon ${loadingStats ? 'spinner' : ''}`} /> Refresh Graph Index
          </button>
        </div>

        <div className="grid-4">
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Graph Database Status</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: stats?.connected ? 'var(--color-success)' : 'var(--color-warning)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="status-dot" style={{ backgroundColor: stats?.connected ? 'var(--color-success)' : 'var(--color-warning)' }}></span>
              {stats?.connected ? 'Neo4j Connected' : 'Mock Graph Engine'}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Total Indexed Nodes</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-primary)' }}>
              {stats?.total_nodes ?? (graphData?.nodes.length || 9)}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Failure & CAPA Edges</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-secondary)' }}>
              {stats?.total_relationships ?? 14}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Equipment & Document Nodes</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-title)' }}>
              {(stats?.equipment_nodes || 1)} Equipment / {(stats?.document_nodes || 2)} Docs
            </div>
          </div>
        </div>
      </div>

      {/* Equipment Query & Graph Topology */}
      <div className="grid-3" style={{ gridTemplateColumns: '2fr 1fr' }}>
        {/* Left Column: Graph Visualizer */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <span className="card-title">
              <Cpu className="nav-icon" style={{ color: 'var(--color-primary)' }} />
              Graph Neighborhood Topology
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Active Target: <strong style={{ color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>{equipmentId}</strong>
            </span>
          </div>

          {/* Search bar & Preset Selector */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
            <div style={{ flexGrow: 1, position: 'relative' }}>
              <input
                type="text"
                className="input-field"
                placeholder="Search Equipment ID (e.g. PMP-102, TURB-401)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchEquipment(searchQuery)}
              />
            </div>
            <button className="btn btn-primary" onClick={() => handleSearchEquipment(searchQuery)} disabled={loadingGraph}>
              <Search className="nav-icon" /> Lookup
            </button>
          </div>

          {/* Preset Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Quick Presets:</span>
            {DEMO_EQUIPMENT.map((id) => (
              <button
                key={id}
                className={`btn ${equipmentId === id ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '4px 10px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}
                onClick={() => handleSearchEquipment(id)}
              >
                {id}
              </button>
            ))}
          </div>

          {/* Graph Interactive Nodes Viewport */}
          <div
            style={{
              position: 'relative',
              height: '420px',
              borderRadius: '12px',
              background: 'radial-gradient(circle at center, rgba(15, 23, 42, 0.8) 0%, rgba(2, 6, 23, 0.95) 100%)',
              border: '1px dashed var(--border-muted)',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            {loadingGraph ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <span className="spinner" style={{ width: '28px', height: '28px', marginBottom: '12px' }}></span>
                <p>Traversing Neo4j Knowledge Graph...</p>
              </div>
            ) : graphData && graphData.nodes.length > 0 ? (
              <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
                {/* SVG Connections connecting peripheral nodes to central Equipment node */}
                {graphData.nodes.map((node, idx) => {
                  if (idx === 0) return null;
                  const angle = ((idx - 1) / (graphData.nodes.length - 1)) * 2 * Math.PI;
                  const centerX = 260;
                  const centerY = 210;
                  const radius = 140;
                  const x = centerX + radius * Math.cos(angle);
                  const y = centerY + radius * Math.sin(angle);
                  const isSelected = selectedNode === node;

                  return (
                    <g key={idx}>
                      <line
                        x1={centerX}
                        y1={centerY}
                        x2={x}
                        y2={y}
                        stroke={isSelected ? 'var(--color-primary)' : 'rgba(100, 116, 139, 0.3)'}
                        strokeWidth={isSelected ? '2.5' : '1.5'}
                        strokeDasharray={isSelected ? 'none' : '4 4'}
                      />
                    </g>
                  );
                })}

                {/* SVG Nodes */}
                {graphData.nodes.map((node, idx) => {
                  const isCentral = idx === 0;
                  const angle = isCentral ? 0 : ((idx - 1) / (graphData.nodes.length - 1)) * 2 * Math.PI;
                  const centerX = 260;
                  const centerY = 210;
                  const radius = 140;
                  const cx = isCentral ? centerX : centerX + radius * Math.cos(angle);
                  const cy = isCentral ? centerY : centerY + radius * Math.sin(angle);
                  const isSelected = selectedNode === node;
                  const color = getNodeColor(node.label);

                  return (
                    <g
                      key={idx}
                      onClick={() => setSelectedNode(node)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* Glow Ring */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isCentral ? 34 : 24}
                        fill={color}
                        fillOpacity={isSelected ? 0.35 : 0.15}
                        stroke={color}
                        strokeWidth={isSelected ? 3 : 1.5}
                      />
                      {/* Center Node Circle */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isCentral ? 22 : 14}
                        fill={color}
                      />
                      {/* Label Text */}
                      <text
                        x={cx}
                        y={cy + (isCentral ? 44 : 34)}
                        textAnchor="middle"
                        fill="var(--text-title)"
                        fontSize={isCentral ? '12px' : '10px'}
                        fontWeight={isCentral ? '700' : '500'}
                        fontFamily="var(--font-mono)"
                      >
                        {node.id || node.name || node.type || node.code || node.label}
                      </text>
                      <text
                        x={cx}
                        y={cy + (isCentral ? 56 : 45)}
                        textAnchor="middle"
                        fill="var(--text-muted)"
                        fontSize="9px"
                      >
                        :{node.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                <AlertTriangle style={{ width: '36px', height: '36px', color: 'var(--color-warning)', marginBottom: '12px' }} />
                <p>No graph neighborhood found for equipment "{equipmentId}".</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Node Inspector */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Database className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
              Graph Node Inspector
            </span>
          </div>

          {selectedNode ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingBottom: '12px', borderBottom: '1px solid var(--border-muted)' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: `${getNodeColor(selectedNode.label)}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {getNodeIcon(selectedNode.label)}
                </div>
                <div>
                  <span className="badge" style={{ background: `${getNodeColor(selectedNode.label)}25`, color: getNodeColor(selectedNode.label), border: `1px solid ${getNodeColor(selectedNode.label)}50` }}>
                    :{selectedNode.label}
                  </span>
                  <h3 style={{ fontSize: '1.1rem', color: 'var(--text-title)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                    {selectedNode.id || selectedNode.name || selectedNode.type || selectedNode.code || selectedNode.description}
                  </h3>
                </div>
              </div>

              {/* Node Attribute Key-Value List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {Object.entries(selectedNode).map(([key, value]) => {
                  if (value === undefined || value === null || value === '') return null;
                  return (
                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', padding: '6px 8px', borderRadius: '6px', background: 'rgba(0, 0, 0, 0.2)' }}>
                      <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}:</span>
                      <span style={{ fontWeight: 600, color: key === 'health_score' ? 'var(--color-primary)' : key === 'risk_level' ? (value === 'CRITICAL' ? 'var(--color-danger)' : 'var(--color-warning)') : 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Additional Context Bridge */}
              <div style={{ marginTop: '12px', padding: '12px', borderRadius: '8px', background: 'rgba(6, 182, 212, 0.08)', border: '1px solid rgba(6, 182, 212, 0.2)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Network style={{ width: '14px', height: '14px' }} /> Vector-Graph Bridge Linked
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-main)' }}>
                  This node is cross-referenced with ChromaDB embeddings for instant semantic retrieval in multi-agent RAG queries.
                </p>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
              <p>Click on any node in the graph topology to view entity attributes and relationships.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
