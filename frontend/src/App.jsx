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
  if (isTarget) statusClass = 'status-Target';
  if (data.status === 'Infected') statusClass = 'status-Infected'; // Override if infected!

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
    
    // Deeper network architecture up to 10
    switch(node.id) {
      case 1: x = 50;  y = 350; break; // Entry Zone
      case 2: x = 350; y = 150; break; // DMZ Zone (Top)
      case 3: x = 350; y = 550; break; // DMZ Zone (Bottom)
      case 4: x = 650; y = 150; break; // App Layer (Top)
      case 5: x = 650; y = 350; break; // App Layer (Middle)
      case 6: x = 650; y = 550; break; // App Layer (Bottom)
      case 7: x = 950; y = 150; break; // Internal Services (Top)
      case 8: x = 950; y = 350; break; // Internal Services (Middle)
      case 9: x = 950; y = 550; break; // Internal Services (Bottom)
      case 10: x = 1250; y = 350; break; // Core Vault target
      default: x = 0; y = 0;
    }

    return {
      id: node.id.toString(),
      type: 'armor',
      position: { x, y },
      data: node
    };
  });
};

const getInitialEdges = (nodesData) => {
  const edges = [];
  
  // Define strict paths: The attack maze
  const connections = [
    // Entry to DMZ
    { source: '1', target: '2' },
    { source: '1', target: '3' },
    { source: '1', target: '5' },
    
    // DMZ to App
    { source: '2', target: '4' },
    { source: '2', target: '5' },
    { source: '3', target: '5' },
    { source: '3', target: '6' },
    
    // App to Internal
    { source: '4', target: '7' },
    { source: '4', target: '8' },
    { source: '5', target: '8' },
    { source: '6', target: '8' },
    { source: '6', target: '9' },
    
    // Internal to Core Vault
    { source: '7', target: '10' },
    { source: '8', target: '10' },
    { source: '9', target: '10' }
  ];

  connections.forEach((conn) => {
    edges.push({
      id: `e${conn.source}-${conn.target}`,
      source: conn.source,
      target: conn.target,
      type: 'smoothstep',
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#475569',
      },
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

  const fetchLogs = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/api/logs');
      if (response.ok) {
        const data = await response.json();
        setLogs(prevLogs => {
          const localLogs = prevLogs.filter(l => l.source === 'System' && typeof l.id === 'string');
          return [...localLogs, ...data];
        });
      }
    } catch (e) {
        console.error("Fetch logs failed:", e);
    }
  }, []);

  useEffect(() => {
    fetchLogs(); 
    
    ws.current = new WebSocket('ws://localhost:8000/ws');
    
    ws.current.onopen = () => {
      addLocalLog('System', 'Connected to the Simulation Network', 'info');
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'init') {
        const layoutNodes = getInitialLayout(message.data);
        setNodes(layoutNodes);
        setEdges(getInitialEdges(message.data));
      } else if (message.type === 'update') {
        
        fetchLogs();

        setNodes((nds) => {
            return nds.map((node) => {
                const updateData = message.data.find(d => d.id.toString() === node.id);
                if (updateData) {
                    return { ...node, data: updateData };
                }
                return node;
            });
        });
        
        // Edge animations: Turn edge red and animate if source is infected
        setEdges((eds) => eds.map(e => {
            const sourceNode = message.data.find(n => n.id.toString() === e.source);
            if (sourceNode && (sourceNode.status === 'Infected' || sourceNode.status === 'Scanning')) {
                return { 
                  ...e, 
                  animated: true, 
                  style: { stroke: '#ef4444', strokeWidth: 3 },
                  markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' }
                };
            }
            return { 
              ...e, 
              animated: false, 
              style: { stroke: '#475569', strokeWidth: 2 },
              markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' }
            };
        }));

      }
    };

    ws.current.onclose = () => {
      addLocalLog('System', 'Disconnected from Simulation', 'critical');
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [fetchLogs]);

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
