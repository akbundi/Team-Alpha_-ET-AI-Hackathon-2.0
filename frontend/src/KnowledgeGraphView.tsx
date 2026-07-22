import { useState, useEffect, useRef } from 'react';
import { Network, Database, Search, Cpu, AlertTriangle, ShieldCheck, User, FileText, Activity, RefreshCw, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

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
  id: string;
  name: string;
  [key: string]: any;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
}

const DEMO_EQUIPMENT = ['PMP-102', 'TURB-401', 'COMP-301', 'VALV-204', 'AHU-04'];

const LEGEND_ITEMS = [
  { label: 'Equipment', color: '#06b6d4' },
  { label: 'Component', color: '#f97316' },
  { label: 'Failure', color: '#ef4444' },
  { label: 'Action', color: '#22c55e' },
  { label: 'Technician', color: '#a855f7' },
  { label: 'Document', color: '#6b7280' },
  { label: 'WorkOrder', color: '#3b82f6' },
  { label: 'Cause', color: '#eab308' },
  { label: 'Recommendation', color: '#0ea5e9' },
  { label: 'Location', color: '#6366f1' },
  { label: 'Manufacturer', color: '#14b8a6' },
];

export default function KnowledgeGraphView({ apiBase, showMsg }: KnowledgeGraphViewProps) {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(false);
  const [equipmentId, setEquipmentId] = useState<string>('PMP-102');
  const [searchQuery, setSearchQuery] = useState<string>('PMP-102');
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphLink[]; graphAvailable: boolean } | null>(null);
  const [loadingGraph, setLoadingGraph] = useState<boolean>(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Force-directed layout physics simulation state
  const svgRef = useRef<SVGSVGElement | null>(null);
  const nodesRef = useRef<any[]>([]);
  const linksRef = useRef<GraphLink[]>([]);
  const animationRef = useRef<number | null>(null);
  const [tick, setTick] = useState(0);

  // Interaction: Zoom & Pan state
  const [zoomState, setZoomState] = useState({ x: 0, y: 0, k: 1 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });

  // Interaction: Dragging state
  const [draggedNode, setDraggedNode] = useState<any | null>(null);

  useEffect(() => {
    fetchStats();
    handleSearchEquipment('PMP-102');
  }, []);

  // Update simulation when graphData loads
  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) {
      nodesRef.current = [];
      linksRef.current = [];
      return;
    }

    const centerX = 260;
    const centerY = 210;

    // Initialize node positions
    const newNodes = graphData.nodes.map((n, idx) => {
      const existing = nodesRef.current.find(oldNode => oldNode.id === n.id);
      const isCentral = idx === 0 || n.id === `Equipment:${equipmentId}`;

      let x = centerX;
      let y = centerY;
      if (!isCentral) {
        if (existing) {
          x = existing.x;
          y = existing.y;
        } else {
          // Arrange in a circle around center
          const angle = Math.random() * 2 * Math.PI;
          const r = 100 + Math.random() * 60;
          x = centerX + r * Math.cos(angle);
          y = centerY + r * Math.sin(angle);
        }
      }

      return {
        ...n,
        name: n.name || '',
        x,
        y,
        vx: existing ? existing.vx : 0,
        vy: existing ? existing.vy : 0,
        fx: isCentral ? centerX : null,
        fy: isCentral ? centerY : null,
      };
    });

    nodesRef.current = newNodes;
    linksRef.current = graphData.edges || [];
    setZoomState({ x: 0, y: 0, k: 1 });
  }, [graphData]);

  // physics tick loop
  useEffect(() => {
    const runSimulation = () => {
      const nodes = nodesRef.current;
      const links = linksRef.current;
      if (nodes.length === 0) {
        animationRef.current = requestAnimationFrame(runSimulation);
        return;
      }

      const centerX = 260;
      const centerY = 210;

      // Run multiple iterations per frame for speedier stabilization
      for (let iter = 0; iter < 4; iter++) {
        // 1. Charge / Repulsion force
        for (let i = 0; i < nodes.length; i++) {
          const u = nodes[i];
          for (let j = i + 1; j < nodes.length; j++) {
            const v = nodes[j];
            let dx = v.x - u.x;
            let dy = v.y - u.y;
            if (dx === 0) dx = 0.1;
            let dist = Math.sqrt(dx * dx + dy * dy);

            // Colliding boundaries
            const rU = u.label === 'Equipment' ? 38 : 24;
            const rV = v.label === 'Equipment' ? 38 : 24;
            const minDist = rU + rV + 24;

            if (dist < 240) {
              let force = (240 - dist) * 0.025;
              if (dist < minDist) {
                force += (minDist - dist) * 0.45;
              }
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;

              if (u.fx === null || u.fx === undefined) {
                u.vx -= fx;
                u.vy -= fy;
              }
              if (v.fx === null || v.fx === undefined) {
                v.vx += fx;
                v.vy += fy;
              }
            }
          }
        }

        // 2. Link force / Attraction
        links.forEach((link) => {
          const sourceNode = nodes.find(n => n.id === link.source);
          const targetNode = nodes.find(n => n.id === link.target);
          if (!sourceNode || !targetNode) return;

          const dx = targetNode.x - sourceNode.x;
          const dy = targetNode.y - sourceNode.y;
          let dist = Math.sqrt(dx * dx + dy * dy);
          if (dist === 0) dist = 0.1;

          const desiredDist = 120;
          const force = (dist - desiredDist) * 0.055;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (sourceNode.fx === null || sourceNode.fx === undefined) {
            sourceNode.vx += fx;
            sourceNode.vy += fy;
          }
          if (targetNode.fx === null || targetNode.fx === undefined) {
            targetNode.vx -= fx;
            targetNode.vy -= fy;
          }
        });

        // 3. Center gravity pull
        nodes.forEach((n) => {
          if (n.fx === null || n.fx === undefined) {
            const dx = centerX - n.x;
            const dy = centerY - n.y;
            n.vx += dx * 0.008;
            n.vy += dy * 0.008;
          }
        });

        // 4. Update dynamic positions
        nodes.forEach((n) => {
          if (n.fx !== null && n.fx !== undefined) {
            n.x = n.fx;
            n.y = n.fy;
            n.vx = 0;
            n.vy = 0;
          } else {
            n.vx *= 0.83; // damping friction
            n.vy *= 0.83;
            n.x += n.vx;
            n.y += n.vy;
          }
        });
      }

      setTick(prev => prev + 1);
      animationRef.current = requestAnimationFrame(runSimulation);
    };

    animationRef.current = requestAnimationFrame(runSimulation);
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
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
        setGraphData({
          nodes: [],
          edges: [],
          graphAvailable: false
        });
        showMsg("Graph not found in database. Please upload/ingest documents first.", "error");
      }
    } catch (e) {
      setGraphData({
        nodes: [],
        edges: [],
        graphAvailable: false
      });
      showMsg("Backend connection failed. Graph unavailable.", "error");
    } finally {
      setLoadingGraph(false);
    }
  };

  const getNodeColor = (label: string) => {
    const item = LEGEND_ITEMS.find(i => i.label === label);
    return item ? item.color : '#94a3b8';
  };

  const getNodeIcon = (label: string) => {
    const color = getNodeColor(label);
    switch (label) {
      case 'Equipment': return <Cpu className="nav-icon" style={{ color }} />;
      case 'Component': return <Activity className="nav-icon" style={{ color }} />;
      case 'Failure': return <AlertTriangle className="nav-icon" style={{ color }} />;
      case 'Action': return <ShieldCheck className="nav-icon" style={{ color }} />;
      case 'Technician': return <User className="nav-icon" style={{ color }} />;
      case 'Document': return <FileText className="nav-icon" style={{ color }} />;
      case 'WorkOrder': return <Database className="nav-icon" style={{ color }} />;
      case 'Cause': return <AlertTriangle className="nav-icon" style={{ color }} />;
      case 'Recommendation': return <ShieldCheck className="nav-icon" style={{ color }} />;
      case 'Location': return <Network className="nav-icon" style={{ color }} />;
      case 'Manufacturer': return <Cpu className="nav-icon" style={{ color }} />;
      default: return <Network className="nav-icon" />;
    }
  };

  // Zoom & Pan interaction handlers
  const handleWheel = (e: any) => {
    e.preventDefault();
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = 0.08;
    const factor = e.deltaY < 0 ? (1 + zoomFactor) : (1 - zoomFactor);
    const newK = Math.max(0.25, Math.min(2.5, zoomState.k * factor));

    const newX = mouseX - (mouseX - zoomState.x) * (newK / zoomState.k);
    const newY = mouseY - (mouseY - zoomState.y) * (newK / zoomState.k);

    setZoomState({ x: newX, y: newY, k: newK });
  };

  const handleMouseDown = (e: any) => {
    if ((e.target as SVGElement).tagName === 'svg' || (e.target as SVGElement).id === 'bg-rect') {
      setIsPanning(true);
      panStart.current = { x: e.clientX - zoomState.x, y: e.clientY - zoomState.y };
    }
  };

  const handleMouseMove = (e: any) => {
    if (isPanning) {
      setZoomState(prev => ({
        ...prev,
        x: e.clientX - panStart.current.x,
        y: e.clientY - panStart.current.y
      }));
    } else if (draggedNode && svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;

      const graphX = (screenX - zoomState.x) / zoomState.k;
      const graphY = (screenY - zoomState.y) / zoomState.k;

      const node = nodesRef.current.find(n => n.id === draggedNode.id);
      if (node) {
        node.fx = graphX;
        node.fy = graphY;
      }
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
    if (draggedNode) {
      const node = nodesRef.current.find(n => n.id === draggedNode.id);
      if (node) {
        // Keep central equipment fixed at center, release others
        const isCentral = node.id === `Equipment:${equipmentId}`;
        if (!isCentral) {
          node.fx = null;
          node.fy = null;
        }
      }
      setDraggedNode(null);
    }
  };

  const handleNodeMouseDown = (e: any, node: any) => {
    e.stopPropagation();
    setDraggedNode(node);
  };

  const handleNodeDoubleClick = (node: any) => {
    if (node.label === 'Equipment' && node.name) {
      handleSearchEquipment(node.name);
    }
  };

  const zoomIn = () => {
    setZoomState(prev => ({
      ...prev,
      k: Math.min(2.5, prev.k * 1.25)
    }));
  };

  const zoomOut = () => {
    setZoomState(prev => ({
      ...prev,
      k: Math.max(0.25, prev.k / 1.25)
    }));
  };

  const resetZoom = () => {
    setZoomState({ x: 0, y: 0, k: 1 });
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
              {stats?.total_nodes ?? (graphData?.nodes.length || 0)}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Failure & CAPA Edges</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-secondary)' }}>
              {stats?.total_relationships ?? (graphData?.edges.length || 0)}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-muted)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Equipment & Document Nodes</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-title)' }}>
              {(stats?.equipment_nodes || 1)} Equipment / {(stats?.document_nodes || 0)} Docs
            </div>
          </div>
        </div>
      </div>

      {/* Equipment Query & Graph Topology */}
      <div className="grid-3" style={{ gridTemplateColumns: '2.2fr 1fr' }}>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
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

          {/* Entity Legend list */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px', marginBottom: '16px', padding: '10px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
            {LEGEND_ITEMS.map((item) => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem' }}>
                <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', backgroundColor: item.color }}></span>
                <span style={{ color: 'var(--text-muted)' }}>{item.label}</span>
              </div>
            ))}
          </div>

          {/* Graph Interactive Viewport */}
          <div
            style={{
              position: 'relative',
              height: '460px',
              borderRadius: '12px',
              background: 'radial-gradient(circle at center, rgba(15, 23, 42, 0.8) 0%, rgba(2, 6, 23, 0.95) 100%)',
              border: '1px dashed var(--border-muted)',
              overflow: 'hidden',
              userSelect: 'none'
            }}
          >
            {/* Viewport Control Buttons */}
            <div style={{ position: 'absolute', right: '16px', top: '16px', display: 'flex', flexDirection: 'column', gap: '8px', zIndex: 10 }}>
              <button className="btn btn-secondary" style={{ padding: '8px', minWidth: 'auto' }} onClick={zoomIn} title="Zoom In">
                <ZoomIn size={16} />
              </button>
              <button className="btn btn-secondary" style={{ padding: '8px', minWidth: 'auto' }} onClick={zoomOut} title="Zoom Out">
                <ZoomOut size={16} />
              </button>
              <button className="btn btn-secondary" style={{ padding: '8px', minWidth: 'auto' }} onClick={resetZoom} title="Reset Zoom">
                <Maximize size={16} />
              </button>
            </div>

            {loadingGraph ? (
              <div style={{ display: 'flex', height: '100%', width: '100%', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: 'var(--text-muted)' }}>
                <span className="spinner" style={{ width: '28px', height: '28px', marginBottom: '12px' }}></span>
                <p>Traversing Neo4j Knowledge Graph...</p>
              </div>
            ) : graphData && graphData.nodes.length > 0 ? (
              <svg
                ref={svgRef}
                data-tick={tick}
                width="100%"
                height="100%"
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{ cursor: isPanning ? 'grabbing' : 'grab' }}
              >
                {/* Background rect to capture events */}
                <rect id="bg-rect" width="100%" height="100%" fill="none" pointerEvents="all" />

                {/* Transform group for Zoom & Pan */}
                <g transform={`translate(${zoomState.x}, ${zoomState.y}) scale(${zoomState.k})`}>
                  
                  {/* Clean SVG Connection Lines */}
                  {linksRef.current.map((link, idx) => {
                    const sourceNode = nodesRef.current.find(n => n.id === link.source);
                    const targetNode = nodesRef.current.find(n => n.id === link.target);
                    if (!sourceNode || !targetNode) return null;

                    const midX = (sourceNode.x + targetNode.x) / 2;
                    const midY = (sourceNode.y + targetNode.y) / 2;

                    return (
                      <g key={idx}>
                        <line
                          x1={sourceNode.x}
                          y1={sourceNode.y}
                          x2={targetNode.x}
                          y2={targetNode.y}
                          stroke="rgba(148, 163, 184, 0.28)"
                          strokeWidth="2"
                        />
                        {/* Display link relationship label */}
                        <text
                          x={midX}
                          y={midY - 4}
                          textAnchor="middle"
                          fill="rgba(148, 163, 184, 0.65)"
                          fontSize="7.5px"
                          fontWeight="bold"
                          fontFamily="var(--font-mono)"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >
                          {link.type}
                        </text>
                      </g>
                    );
                  })}

                  {/* SVG Nodes */}
                  {nodesRef.current.map((node, idx) => {
                    const isCentral = node.id === `Equipment:${equipmentId}`;
                    const isSelected = selectedNode?.id === node.id;
                    const color = getNodeColor(node.label);

                    return (
                      <g
                        key={node.id || idx}
                        onClick={() => setSelectedNode(node)}
                        onDoubleClick={() => handleNodeDoubleClick(node)}
                        onMouseDown={(e) => handleNodeMouseDown(e, node)}
                        style={{ cursor: 'pointer' }}
                      >
                        {/* Glow halo on hovered/selected node */}
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={isCentral ? 38 : 24}
                          fill={color}
                          fillOpacity={isSelected ? 0.38 : 0.14}
                          stroke={color}
                          strokeWidth={isSelected ? 3 : 1.5}
                        />
                        {/* Core circle */}
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={isCentral ? 25 : 15}
                          fill={color}
                        />
                        {/* Clean micro-ring */}
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={isCentral ? 21 : 12}
                          fill="none"
                          stroke="rgba(255,255,255,0.3)"
                          strokeWidth="1"
                        />

                        {/* Node Label Title */}
                        <text
                          x={node.x}
                          y={node.y + (isCentral ? 50 : 36)}
                          textAnchor="middle"
                          fill="var(--text-title)"
                          fontSize={isCentral ? '11px' : '9.5px'}
                          fontWeight={isCentral ? '700' : '500'}
                          fontFamily="var(--font-mono)"
                        >
                          {(node.name || '').length > 20 ? (node.name || '').slice(0, 18) + '...' : (node.name || '')}
                        </text>

                        {/* Node Label Type */}
                        <text
                          x={node.x}
                          y={node.y + (isCentral ? 62 : 46)}
                          textAnchor="middle"
                          fill="var(--text-muted)"
                          fontSize="8.5px"
                          fontWeight="600"
                        >
                          :{node.label}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            ) : (
              <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: 'var(--text-muted)', padding: '20px' }}>
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
                  <h3 style={{ fontSize: '1.05rem', color: 'var(--text-title)', marginTop: '4px', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                    {selectedNode.name}
                  </h3>
                </div>
              </div>

              {/* Node Attribute List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '310px', overflowY: 'auto', paddingRight: '4px' }}>
                {Object.entries(selectedNode).map(([key, value]) => {
                  if (['id', 'label', 'name', 'x', 'y', 'vx', 'vy', 'fx', 'fy'].includes(key)) return null;
                  if (value === undefined || value === null || value === '') return null;
                  return (
                    <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.82rem', padding: '8px', borderRadius: '6px', background: 'rgba(0, 0, 0, 0.25)' }}>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 'bold' }}>{key.replace(/_/g, ' ')}:</span>
                      <span style={{ fontWeight: 600, color: key === 'health_score' ? 'var(--color-primary)' : key === 'risk_level' ? (value === 'CRITICAL' ? 'var(--color-danger)' : 'var(--color-warning)') : 'var(--text-main)', fontFamily: 'var(--font-mono)', wordBreak: 'break-word' }}>
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Additional Context Bridge */}
              <div style={{ marginTop: '4px', padding: '12px', borderRadius: '8px', background: 'rgba(6, 182, 212, 0.08)', border: '1px solid rgba(6, 182, 212, 0.2)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Network style={{ width: '14px', height: '14px' }} /> Vector-Graph Bridge Active
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  This entity is cross-linked with vector chunks in ChromaDB. Hover, drag, or double-click to trace relationships across standard logs.
                </p>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
              <p>Click on any node in the topology visualization to inspect properties. Double-click Equipment nodes to traverse.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
