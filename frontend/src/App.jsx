import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  Handle, 
  Position,
  useNodesState,
  useEdgesState,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  AlertTriangle,
  Database,
  Globe,
  Network,
  Server,
  ShieldAlert,
  ShieldCheck,
  Skull,
  TerminalSquare
} from 'lucide-react';

// Hardcoded friendly names to make the simulation easier to understand
const NODE_ROLES = {
  1:  { role: "Public Gateway", icon: Globe },
  2:  { role: "DMZ Server α", icon: Server },
  3:  { role: "DMZ Server β", icon: Server },
  4:  { role: "DMZ Server γ", icon: Server },
  5:  { role: "Web App", icon: TerminalSquare },
  6:  { role: "API Gateway", icon: Network },
  7:  { role: "Auth Server", icon: ShieldCheck },
  8:  { role: "App Server", icon: Server },
  9:  { role: "CMS Portal", icon: TerminalSquare },
  10: { role: "Log Collector", icon: Server },
  11: { role: "Service Bus", icon: Network },
  12: { role: "Task Queue", icon: Server },
  13: { role: "Config Store", icon: ShieldCheck },
  14: { role: "Scheduler", icon: TerminalSquare },
  15: { role: "Admin Panel", icon: ShieldCheck },
  16: { role: "Data Pipeline", icon: Network },
  17: { role: "Backup Server", icon: Server },
  18: { role: "Core Engine", icon: Server },
  19: { role: "Key Vault", icon: ShieldCheck },
  20: { role: "Vault Core", icon: Database },
};

const STATUS_ICONS = {
  SECURE: ShieldCheck,
  EXPOSED: AlertTriangle,
  COMPROMISED: ShieldAlert,
  ROOT_ACCESS: Skull,
};

// Custom Node Component for A.R.M.O.R
const ArmorNode = ({ data, id }) => {
  const isTarget = data.os_type === 'Database';
  const roleInfo = NODE_ROLES[id] || { role: "Server", icon: Server };
  const Icon = roleInfo.icon;
  const StatusIcon = STATUS_ICONS[data.status] || ShieldCheck;

  let statusClass = `status-${data.status}`;
  if (isTarget && data.status === 'SECURE') statusClass = 'status-Target';
  if (data.status === 'ROOT_ACCESS') statusClass = 'status-ROOT_ACCESS';

  return (
    <div className={`armor-node ${statusClass}`}>
      <Handle type="target" position={Position.Left} style={{ background: '#475569', width: 8, height: 8 }} />
      
      <div className="node-icon-container">
        <Icon size={24} className="node-icon" />
      </div>

      <div className="node-content">
        <div className="node-title">{roleInfo.role}</div>
        <div className="node-subtitle">{data.ip_address} | {data.os_type}</div>
        
        <div className="status-indicator">
            <StatusIcon size={14} />
            <span>{data.status}</span>
        </div>

        <div className="node-stats">
          {data.status === 'ROOT_ACCESS' ? (
            <div className="stat-row" style={{ justifyContent: 'center', background: 'rgba(239, 68, 68, 0.2)', padding: '6px', borderRadius: '4px', border: '1px solid rgba(239, 68, 68, 0.5)' }}>
              <span className="stat-label" style={{ color: '#ef4444', fontStyle: 'italic', letterSpacing: '2px', fontSize: '9px', fontWeight: '800' }}>⚠️ DATA BREACHED</span>
            </div>
          ) : (
            <div className="stat-row" style={{ justifyContent: 'center', background: 'rgba(0,0,0,0.2)', padding: '6px', borderRadius: '4px' }}>
              <span className="stat-label" style={{ color: '#64748b', fontStyle: 'italic', letterSpacing: '2px', fontSize: '9px', fontWeight: '700' }}>🔒 DATA ENCRYPTED</span>
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} style={{ background: '#475569', width: 8, height: 8 }} />
    </div>
  );
};

const nodeTypes = {
  armor: ArmorNode,
};

// 20-node 7-layer layout
const getInitialLayout = (nodesData) => {
  return nodesData.map((node) => {
    let x, y;
    const num = parseInt(node.id.replace('Node_', ''), 10);

    switch(num) {
      // Layer 0: Gateway
      case 1:  x = 50;   y = 400; break;
      // Layer 1: DMZ (3 nodes)
      case 2:  x = 330;  y = 150; break;
      case 3:  x = 330;  y = 400; break;
      case 4:  x = 330;  y = 650; break;
      // Layer 2: App (5 nodes)
      case 5:  x = 610;  y = 50;  break;
      case 6:  x = 610;  y = 200; break;
      case 7:  x = 610;  y = 400; break;
      case 8:  x = 610;  y = 600; break;
      case 9:  x = 610;  y = 750; break;
      // Layer 3: Services (5 nodes)
      case 10: x = 890;  y = 100; break;
      case 11: x = 890;  y = 280; break;
      case 12: x = 890;  y = 460; break;
      case 13: x = 890;  y = 600; break;
      case 14: x = 890;  y = 750; break;
      // Layer 4: Internal (3 nodes)
      case 15: x = 1170; y = 180; break;
      case 16: x = 1170; y = 420; break;
      case 17: x = 1170; y = 660; break;
      // Layer 5: Core (2 nodes)
      case 18: x = 1450; y = 280; break;
      case 19: x = 1450; y = 540; break;
      // Layer 6: Database
      case 20: x = 1730; y = 400; break;
      default: x = 0;    y = 0;
    }

    return {
      id: node.id,
      type: 'armor',
      position: { x, y },
      data: node
    };
  });
};


const getInitialEdges = (nodesData) => {
  const edges = [];

  const connections = [
    // Gateway → DMZ
    { source: 'Node_1', target: 'Node_2' },
    { source: 'Node_1', target: 'Node_3' },
    { source: 'Node_1', target: 'Node_4' },
    // DMZ → App
    { source: 'Node_2', target: 'Node_5' },
    { source: 'Node_2', target: 'Node_6' },
    { source: 'Node_3', target: 'Node_6' },
    { source: 'Node_3', target: 'Node_7' },
    { source: 'Node_4', target: 'Node_8' },
    { source: 'Node_4', target: 'Node_9' },
    // App → Services
    { source: 'Node_5', target: 'Node_10' },
    { source: 'Node_6', target: 'Node_10' },
    { source: 'Node_6', target: 'Node_11' },
    { source: 'Node_7', target: 'Node_11' },
    { source: 'Node_7', target: 'Node_12' },
    { source: 'Node_8', target: 'Node_13' },
    { source: 'Node_8', target: 'Node_12' },
    { source: 'Node_9', target: 'Node_14' },
    // Services → Internal
    { source: 'Node_10', target: 'Node_15' },
    { source: 'Node_11', target: 'Node_15' },
    { source: 'Node_11', target: 'Node_16' },
    { source: 'Node_12', target: 'Node_16' },
    { source: 'Node_13', target: 'Node_16' },
    { source: 'Node_13', target: 'Node_17' },
    { source: 'Node_14', target: 'Node_17' },
    // Internal → Core
    { source: 'Node_15', target: 'Node_18' },
    { source: 'Node_16', target: 'Node_18' },
    { source: 'Node_16', target: 'Node_19' },
    { source: 'Node_17', target: 'Node_19' },
    // Core → Database
    { source: 'Node_18', target: 'Node_20' },
    { source: 'Node_19', target: 'Node_20' },
  ];

  connections.forEach((conn) => {
    edges.push({
      id: `e${conn.source}-${conn.target}`,
      source: conn.source,
      target: conn.target,
      type: 'smoothstep',
      animated: false,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' },
      style: { stroke: '#475569', strokeWidth: 2 }
    });
  });

  return edges;
};


export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [logs, setLogs] = useState([]);
  const ws = useRef(null);

  const enrichNode = (id, data) => ({
    ...data,
    id,
    ip_address: data.ip_address || `192.168.1.${id.replace('Node_', '')}`,
  });

  const enrichNodes = (nodesDict) =>
    Object.entries(nodesDict).map(([id, data]) => enrichNode(id, data));

  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8000/ws/combat');

    ws.current.onopen = () => {
      addLocalLog('System', 'Connected to ARMOR Simulation Network', 'info');
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      let changedNodesArray = [];

      if (message.type === 'snapshot' && message.nodes) {
        const nodesArray = enrichNodes(message.nodes);
        changedNodesArray = nodesArray;

        setNodes((nds) => {
          if (nds.length === 0) {
            const layout = getInitialLayout(nodesArray);
            setEdges(getInitialEdges(nodesArray));
            return layout;
          }

          return nds.map((node) => {
            const updated = nodesArray.find((n) => n.id === node.id);
            return updated ? { ...node, data: updated } : node;
          });
        });
      } else if (message.type === 'delta' && message.changed_nodes) {
        const deltaById = Object.fromEntries(
          Object.entries(message.changed_nodes).map(([id, data]) => [id, enrichNode(id, data)])
        );
        changedNodesArray = Object.values(deltaById);

        setNodes((nds) =>
          nds.map((node) => {
            const updated = deltaById[node.id];
            return updated ? { ...node, data: { ...node.data, ...updated } } : node;
          })
        );

        setEdges((eds) =>
          eds.map((edge) => {
            const src = deltaById[edge.source];
            if (!src) {
              return edge;
            }

            const isUnderAttack = ['EXPOSED', 'COMPROMISED', 'ROOT_ACCESS'].includes(src.status);
            return isUnderAttack
              ? {
                  ...edge,
                  animated: true,
                  style: { stroke: '#ef4444', strokeWidth: 3 },
                  markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' },
                }
              : {
                  ...edge,
                  animated: false,
                  style: { stroke: '#475569', strokeWidth: 2 },
                  markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' },
                };
          })
        );
      } else {
        return;
      }

      changedNodesArray.forEach((n) => {
        if (n.status === 'ROOT_ACCESS') {
          addLocalLog('Red Team', `ROOT_ACCESS gained on ${n.id} (${n.ip_address})`, 'critical');
        } else if (n.status === 'COMPROMISED') {
          addLocalLog('Red Team', `${n.id} compromised`, 'warning');
        } else if (n.status === 'EXPOSED') {
          addLocalLog('Red Team', `${n.id} exposed — scan detected`, 'warning');
        } else if (n.status === 'SECURE' && n.scan_rate === 0) {
          addLocalLog('Blue Team', `${n.id} restored to SECURE`, 'info');
        }
      });
    };

    ws.current.onclose = () => {
      addLocalLog('System', 'Disconnected from Simulation', 'critical');
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  const addLocalLog = (source, message, level) => {
    const newLog = {
      id: "local-" + Date.now(),
      time: new Date().toLocaleTimeString(),
      source,
      message,
      level
    };
    setLogs(prev => [newLog, ...prev].slice(0, 50));
  };


  return (
    <div className="app-container">
      <header className="header">
        <div className="brand">
          <ShieldAlert className="brand-logo" size={32} />
          <h1 className="logo">A.R.M.O.R <span className="logo-light">NETWORK MAP</span></h1>
        </div>
        <div className="header-info">
           <p>Watch as the <strong>Red Team (Attacker)</strong> tries to reach the Vault Core,</p>
           <p>while the <strong>Blue Team (Defender)</strong> patches servers in real-time.</p>
           <div style={{ display: 'flex', gap: '12px', marginTop: '8px', justifyContent: 'center' }}>
             <a href="/game_tree.html" target="_blank" rel="noopener noreferrer" style={{
               padding: '6px 16px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)',
               borderRadius: '8px', color: '#ef4444', fontSize: '12px', fontWeight: 700,
               textDecoration: 'none', letterSpacing: '0.5px', pointerEvents: 'auto',
               transition: 'all 0.2s'
             }}>🌳 View A* Game Tree →</a>
             
             <a href="/minimax_tree.html" target="_blank" rel="noopener noreferrer" style={{
               padding: '6px 16px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.4)',
               borderRadius: '8px', color: '#3b82f6', fontSize: '12px', fontWeight: 700,
               textDecoration: 'none', letterSpacing: '0.5px', pointerEvents: 'auto',
               transition: 'all 0.2s'
             }}>🛡️ View Minimax Tree →</a>
           </div>
        </div>
      </header>

      <main className="main-content">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          className="flow-bg"
        >
          <Background color="#334155" gap={25} size={1.5} />
          <Controls />
        </ReactFlow>
      </main>

      <aside className="sidebar">
        <div className="sidebar-header">
          <h2 className="sidebar-title">
            <TerminalSquare size={22} className="text-blue" />
            Active Security Logs
          </h2>
          <p className="sidebar-subtitle">Real-time actions from Database</p>
        </div>
        <div className="sidebar-content">
          {logs.map((log, index) => (
            <div key={log.id || index} className={`log-entry log-${log.level}`}>
              <div className="log-header">
                <span className={`badge badge-${log.source.replace(" ", "")}`}>{log.source}</span>
                <span className="log-time">{log.time}</span>
              </div>
              <div className="log-message">{log.message}</div>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="empty-logs">
              Waiting for network activity...
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

