import React, { useEffect, useRef } from 'react';

// ═══ NETWORK TOPOLOGY ═══
// Matches backend/engine/network.py adjacency list
const NETWORK = {
  Node_1:  { os: "Windows", role: "Gateway",      depth: 0, neighbors: ["Node_2", "Node_3", "Node_4"] },
  Node_2:  { os: "Linux",   role: "DMZ Server α", depth: 1, neighbors: ["Node_5", "Node_6"] },
  Node_3:  { os: "Windows", role: "DMZ Server β", depth: 1, neighbors: ["Node_6", "Node_7"] },
  Node_4:  { os: "Linux",   role: "DMZ Server γ", depth: 1, neighbors: ["Node_8", "Node_9"] },
  Node_5:  { os: "Windows", role: "Web App",      depth: 2, neighbors: ["Node_10"] },
  Node_6:  { os: "Linux",   role: "API Gateway",  depth: 2, neighbors: ["Node_10", "Node_11"] },
  Node_7:  { os: "Windows", role: "Auth Server",  depth: 2, neighbors: ["Node_11", "Node_12"] },
  Node_8:  { os: "Linux",   role: "App Server",   depth: 2, neighbors: ["Node_12", "Node_13"] },
  Node_9:  { os: "Windows", role: "CMS Portal",   depth: 2, neighbors: ["Node_14"] },
  Node_10: { os: "Linux",   role: "Log Collector", depth: 3, neighbors: ["Node_15"] },
  Node_11: { os: "Windows", role: "Service Bus",   depth: 3, neighbors: ["Node_15", "Node_16"] },
  Node_12: { os: "Linux",   role: "Task Queue",    depth: 3, neighbors: ["Node_16"] },
  Node_13: { os: "Windows", role: "Config Store",  depth: 3, neighbors: ["Node_16", "Node_17"] },
  Node_14: { os: "Linux",   role: "Scheduler",     depth: 3, neighbors: ["Node_17"] },
  Node_15: { os: "Windows", role: "Admin Panel",   depth: 4, neighbors: ["Node_18"] },
  Node_16: { os: "Linux",   role: "Data Pipeline", depth: 4, neighbors: ["Node_18", "Node_19"] },
  Node_17: { os: "Windows", role: "Backup Server", depth: 4, neighbors: ["Node_19"] },
  Node_18: { os: "Linux",   role: "Core Engine",   depth: 5, neighbors: ["Node_20"] },
  Node_19: { os: "Windows", role: "Key Vault",     depth: 5, neighbors: ["Node_20"] },
  Node_20: { os: "Database", role: "Vault Core",    depth: 6, neighbors: [] },
};

const OS_VULN = { Linux: 1.2, Windows: 1.0, Database: 0.8 };
const DB_DEPTH = 6;

function computeVuln(nodeId) {
  const n = NETWORK[nodeId];
  let v = OS_VULN[n.os] || 1.0;
  v += 0.2 * n.depth;
  return v;
}

function runAStar() {
  const start = "Node_1";
  const openSet = [{ f: 0, g: 0, node: start, path: [start] }];
  const visited = new Set();
  const allEvaluated = [];

  while (openSet.length > 0) {
    openSet.sort((a, b) => a.f - b.f);
    const current = openSet.shift();
    if (visited.has(current.node)) continue;
    visited.add(current.node);
    if (current.node === "Node_20") {
      return { optimalPath: current.path, allEvaluated };
    }
    for (const neighbor of NETWORK[current.node].neighbors) {
      if (visited.has(neighbor)) continue;
      const vuln = computeVuln(neighbor);
      const hop = Math.max(0, DB_DEPTH - NETWORK[neighbor].depth);
      const g = current.g + 1;
      const h = hop / vuln;
      const f = g + h;
      allEvaluated.push({
        node: neighbor, parent: current.node,
        g, h: parseFloat(h.toFixed(2)), f: parseFloat(f.toFixed(2)),
        vuln: parseFloat(vuln.toFixed(2)), hop
      });
      openSet.push({ f, g, node: neighbor, path: [...current.path, neighbor] });
    }
  }
  return { optimalPath: [start], allEvaluated };
}

const POSITIONS = {
  Node_1:  { x: 40,  y: 300 },
  Node_2:  { x: 260, y: 80  },
  Node_3:  { x: 260, y: 300 },
  Node_4:  { x: 260, y: 520 },
  Node_5:  { x: 490, y: 20  },
  Node_6:  { x: 490, y: 140 },
  Node_7:  { x: 490, y: 300 },
  Node_8:  { x: 490, y: 460 },
  Node_9:  { x: 490, y: 620 },
  Node_10: { x: 710, y: 20  },
  Node_11: { x: 710, y: 160 },
  Node_12: { x: 710, y: 300 },
  Node_13: { x: 710, y: 440 },
  Node_14: { x: 710, y: 620 },
  Node_15: { x: 930, y: 80  },
  Node_16: { x: 930, y: 280 },
  Node_17: { x: 930, y: 520 },
  Node_18: { x: 1150, y: 160 },
  Node_19: { x: 1150, y: 440 },
  Node_20: { x: 1370, y: 300 },
};

const NODE_W = 170;
const NODE_H = 150;

function getOsIcon(os) {
  if (os === "Linux") return "🐧";
  if (os === "Windows") return "💻";
  if (os === "Database") return "🗄️";
  return "🖥️";
}

export default function GameTree() {
  const svgRef = useRef(null);
  const { optimalPath, allEvaluated } = runAStar();
  const optimalSet = new Set(optimalPath);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    svg.innerHTML = '';
    for (const e of allEvaluated) {
      const fp = POSITIONS[e.parent];
      const tp = POSITIONS[e.node];
      if (!fp || !tp) continue;
      const isOpt = optimalSet.has(e.parent) && optimalSet.has(e.node);
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", fp.x + NODE_W);
      line.setAttribute("y1", fp.y + NODE_H / 2);
      line.setAttribute("x2", tp.x);
      line.setAttribute("y2", tp.y + NODE_H / 2);
      line.classList.add(isOpt ? "gt-line-optimal" : "gt-line-pruned");
      svg.appendChild(line);
    }
  }, []);

  const sorted = [...allEvaluated].sort((a, b) => {
    const aO = optimalSet.has(a.node) ? 0 : 1;
    const bO = optimalSet.has(b.node) ? 0 : 1;
    if (aO !== bO) return aO - bO;
    return a.f - b.f;
  });

  return (
    <div className="gt-wrapper">
      {/* ── Tree Canvas ── */}
      <div className="gt-canvas">
        <div className="gt-container">
          <svg className="gt-lines" ref={svgRef}></svg>

          {Object.entries(NETWORK).map(([nodeId, info]) => {
            const pos = POSITIONS[nodeId];
            const isOnPath = optimalSet.has(nodeId);
            const isTarget = nodeId === "Node_20";
            const isStart  = nodeId === "Node_1";
            const evalData = allEvaluated.find(e => e.node === nodeId);

            let cls = "gt-node";
            let badge = "";
            let badgeCls = "";
            if (isTarget)      { cls += " gt-target";  badge = "🎯 TARGET";  badgeCls = "gt-badge-target"; }
            else if (isStart)  { cls += " gt-start";   badge = "🏁 START";   badgeCls = "gt-badge-start"; }
            else if (isOnPath) { cls += " gt-optimal";  badge = "⭐ OPTIMAL"; badgeCls = "gt-badge-optimal"; }
            else               { cls += " gt-pruned";   badge = "✂️ PRUNED";  badgeCls = "gt-badge-pruned"; }

            return (
              <div key={nodeId} className={cls} style={{ left: pos.x, top: pos.y }}>
                <div className="gt-node-header">
                  <span className="gt-node-icon">{getOsIcon(info.os)}</span>
                  <div>
                    <div className="gt-node-name">{nodeId}</div>
                    <div className="gt-node-role">{info.role}</div>
                  </div>
                </div>
                <span className={`gt-node-badge ${badgeCls}`}>{badge}</span>

                {evalData && (
                  <div className="gt-score-grid">
                    <span className="gt-score-label">g(n):</span><span className="gt-score-value">{evalData.g}</span>
                    <span className="gt-score-label">vuln:</span><span className="gt-score-value">{evalData.vuln}</span>
                    <span className="gt-score-label">dist:</span><span className="gt-score-value">{evalData.hop}</span>
                    <span className="gt-score-label">h(n):</span><span className="gt-score-value">{evalData.h}</span>
                    <div className="gt-score-total">
                      <span>f(n)</span>
                      <span className="gt-fn">{evalData.f}</span>
                    </div>
                  </div>
                )}
                {isStart && !evalData && (
                  <div className="gt-score-grid">
                    <span className="gt-score-label">g(n):</span><span className="gt-score-value">0</span>
                    <span className="gt-score-label">dist:</span><span className="gt-score-value">{DB_DEPTH}</span>
                    <div className="gt-score-total"><span>f(n)</span><span className="gt-fn">START</span></div>
                  </div>
                )}
                {isTarget && !evalData && (
                  <div className="gt-score-grid">
                    <span className="gt-score-label">dist:</span><span className="gt-score-value">0</span>
                    <div className="gt-score-total"><span>f(n)</span><span className="gt-fn">GOAL</span></div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Sidebar ── */}
      <div className="gt-sidebar">
        <h2 className="gt-sidebar-title">🔴 A* Search Algorithm</h2>
        <p className="gt-sidebar-sub">How the Red Team finds the optimal attack path</p>

        <div className="gt-box">
          <div className="gt-box-title">Core Formula</div>
          <div className="gt-formula">f(n) = g(n) + h(n)</div>
          <div className="gt-box-desc">
            <code>g(n)</code> = cost so far (steps taken + detection risk)<br/>
            <code>h(n)</code> = heuristic = <code>distance / vulnerability</code><br/><br/>
            The AI always picks the node with the <strong>lowest f(n)</strong>.
          </div>
        </div>

        <div className="gt-box">
          <div className="gt-box-title">Vulnerability Scores by OS</div>
          <table className="gt-table">
            <thead><tr><th>OS Type</th><th>Base Vuln</th><th>Why</th></tr></thead>
            <tbody>
              <tr><td>🐧 Linux</td><td style={{color:'#22c55e'}}>1.20</td><td>More open ports</td></tr>
              <tr><td>💻 Windows</td><td style={{color:'#eab308'}}>1.00</td><td>Standard config</td></tr>
              <tr><td>🗄️ Database</td><td style={{color:'#ef4444'}}>0.80</td><td>Hardened target</td></tr>
            </tbody>
          </table>
        </div>

        <div className="gt-box">
          <div className="gt-box-title">Path Comparison Table</div>
          <table className="gt-table">
            <thead><tr><th></th><th>Node</th><th>g(n)</th><th>h(n)</th><th>f(n)</th></tr></thead>
            <tbody>
              {sorted.map((e, i) => (
                <tr key={i} className={optimalSet.has(e.node) ? "gt-row-selected" : "gt-row-dimmed"}>
                  <td>{optimalSet.has(e.node) ? '⭐' : ''}</td>
                  <td>{e.node}</td>
                  <td>{e.g}</td>
                  <td>{e.h}</td>
                  <td>{e.f}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="gt-box">
          <div className="gt-box-title">How It Works</div>
          <div className="gt-steps">
            <div className="gt-step"><div className="gt-step-num">1</div><div className="gt-step-text"><strong>Expand:</strong> From the current node, the AI computes f(n) for each neighbor.</div></div>
            <div className="gt-step"><div className="gt-step-num">2</div><div className="gt-step-text"><strong>Select:</strong> It picks the neighbor with the <strong>lowest f(n)</strong>.</div></div>
            <div className="gt-step"><div className="gt-step-num">3</div><div className="gt-step-text"><strong>Prune:</strong> Higher f(n) branches are abandoned (dashed grey lines).</div></div>
            <div className="gt-step"><div className="gt-step-num">4</div><div className="gt-step-text"><strong>Repeat:</strong> Until the Database is reached — the <strong>optimal attack path</strong>.</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}
