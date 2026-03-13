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
import { ShieldAlert, ShieldCheck, TerminalSquare, Server, Database, Globe, Network } from 'lucide-react';

// Hardcoded friendly names to make the simulation easier to understand
const NODE_ROLES = {
  1: { role: "Public Gateway", icon: Globe },
  2: { role: "Web Server Alpha", icon: Server },
  3: { role: "Web Server Beta", icon: Server },
  4: { role: "Auth Server", icon: ShieldCheck },
  5: { role: "API Gateway", icon: Network },
  6: { role: "Internal App A", icon: TerminalSquare },
  7: { role: "Internal App B", icon: TerminalSquare },
  8: { role: "Log Server", icon: Server },
  9: { role: "Cache Layer", icon: Server },
  10: { role: "Vault Core", icon: Database },
};

// Custom Node Component for A.R.M.O.R
const ArmorNode = ({ data, id }) => {
  const isHighCpu = data.cpu_usage > 75;
  const isTarget = data.os_type === 'Database';
  const roleInfo = NODE_ROLES[id] || { role: "Server", icon: Server };
  const Icon = roleInfo.icon;

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
           <div className={`status-dot-small ${data.status.toLowerCase()}`}></div>
           <span>{data.status.toUpperCase()}</span>
        </div>

        <div className="node-stats">
          <div className="stat-row">
            <span className="stat-label">CPU Usage</span>
            <div className="stat-bar-container">
              <div className={`stat-bar ${isHighCpu ? 'high' : ''}`} style={{ width: `${data.cpu_usage}%` }}></div>
            </div>
          </div>
        </div>
      </div>

      <Handle type="source" position={Position.Right} style={{ background: '#475569', width: 8, height: 8 }} />
    </div>
  );
};

const nodeTypes = {
  armor: ArmorNode,
};

// Deeper, sprawling layout algorithm
const getInitialLayout = (nodesData) => {
  return nodesData.map((node) => {
    let x, y;
    // node.id is "Node_1", "Node_2" etc — extract the number
    const num = parseInt(node.id.replace('Node_', ''), 10);

    switch(num) {
      case 1:  x = 50;   y = 350; break; // Entry Zone
      case 2:  x = 350;  y = 150; break; // DMZ Zone (Top)
      case 3:  x = 350;  y = 550; break; // DMZ Zone (Bottom)
      case 4:  x = 650;  y = 150; break; // App Layer (Top)
      case 5:  x = 650;  y = 350; break; // App Layer (Middle)
      case 6:  x = 650;  y = 550; break; // App Layer (Bottom)
      case 7:  x = 950;  y = 150; break; // Internal Services (Top)
      case 8:  x = 950;  y = 350; break; // Internal Services (Middle)
      case 9:  x = 950;  y = 550; break; // Internal Services (Bottom)
      case 10: x = 1250; y = 350; break; // Core Vault target
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

  // Matches the new branching topology in backend/engine/network.py
  const connections = [
    // Entry → DMZ
    { source: 'Node_1', target: 'Node_2' },
    { source: 'Node_1', target: 'Node_3' },
    // DMZ → App (cross-links)
    { source: 'Node_2', target: 'Node_4' },
    { source: 'Node_2', target: 'Node_5' },
    { source: 'Node_3', target: 'Node_5' },
    { source: 'Node_3', target: 'Node_6' },
    // App → Internal (multiple paths)
    { source: 'Node_4', target: 'Node_7' },
    { source: 'Node_4', target: 'Node_8' },
    { source: 'Node_5', target: 'Node_8' },
    { source: 'Node_6', target: 'Node_8' },
    { source: 'Node_6', target: 'Node_9' },
    // Internal → Vault (3 paths)
    { source: 'Node_7', target: 'Node_10' },
    { source: 'Node_8', target: 'Node_10' },
    { source: 'Node_9', target: 'Node_10' },
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

  // Convert backend nodes dict to a flat array with ip_address injected
  const enrichNodes = (nodesDict) =>
    Object.entries(nodesDict).map(([id, data]) => ({
      ...data,
      id,
      ip_address: `192.168.1.${id.replace('Node_', '')}`,
    }));

  useEffect(() => {
    // ── Connect to the CORRECT WebSocket path ─────────────────────────────
    ws.current = new WebSocket('ws://localhost:8000/ws/combat');

    ws.current.onopen = () => {
      addLocalLog('System', 'Connected to ARMOR Simulation Network', 'info');
    };

    ws.current.onmessage = (event) => {
      // Backend broadcasts: { nodes: { Node_1: {...}, ... }, edges: [...] }
      const message = JSON.parse(event.data);

      // Skip BFS scan replies (they have bfs_order not nodes)
      if (!message.nodes) return;

      const nodesArray = enrichNodes(message.nodes);

      setNodes((nds) => {
        if (nds.length === 0) {
          // First message — do full layout init
          const layout = getInitialLayout(nodesArray);
          setEdges(getInitialEdges(nodesArray));
          return layout;
        }
        // Subsequent messages — just update data in-place
        return nds.map((node) => {
          const updated = nodesArray.find((n) => n.id === node.id);
          if (updated) return { ...node, data: updated };
          return node;
        });
      });

      // Animate edges red when source is under attack
      setEdges((eds) =>
        eds.map((e) => {
          const src = message.nodes[e.source];   // e.source is already "Node_1" etc.
          const isUnderAttack =
            src && ['EXPOSED', 'COMPROMISED', 'ROOT_ACCESS'].includes(src.status);
          return isUnderAttack
            ? { ...e, animated: true,  style: { stroke: '#ef4444', strokeWidth: 3 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' } }
            : { ...e, animated: false, style: { stroke: '#475569', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' } };
        })
      );

      // Add a log entry whenever a node changes to a bad state
      nodesArray.forEach((n) => {
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
