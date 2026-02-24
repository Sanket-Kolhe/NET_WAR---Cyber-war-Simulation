# 🛡️ Project A.R.M.O.R.
**Autonomous Risk Mitigation & Offensive Response System**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)
![React](https://img.shields.io/badge/React-18.0+-61dafb.svg)
![Status](https://img.shields.io/badge/Status-Active_Development-brightgreen.svg)

> An academic Capstone Project simulating an autonomous, closed-loop cyber-warfare environment to evaluate classical AI algorithms in systems-level network defense.

## 📖 Project Context & Vision
In modern cybersecurity, the speed of automated attacks—such as self-propagating ransomware worms or botnet DDoS strikes—has vastly outpaced human reaction times. When a breach occurs, relying on human security analysts to manually trace the intrusion, identify the compromised node, and write firewall rules is no longer viable. The industry requires autonomous security systems capable of defending networks at machine speed.

**A.R.M.O.R.** acts as a specialized "Cyber Range." It is a gamified simulation engine that virtualizes a corporate network topology. Within this environment, two Artificial Intelligence agents—an Offensive "Red Team" and a Defensive "Blue Team"—engage in a continuous, automated battle for network dominance. This project bridges the gap between theoretical Artificial Intelligence and practical systems engineering, demonstrating how AI can proactively manage operating system resources, analyze network sockets, and isolate threats without human intervention.

## ⚔️ The Simulation Mechanics


The core of A.R.M.O.R. is built upon a deterministic, observable environment where agents compete for control over simulated servers (Nodes).

* **The Virtual Environment:** A centralized backend engine simulates network nodes. Each node possesses an Operating System state, an open port configuration (HTTP, SSH, FTP), dynamic CPU/Memory usage ticks, and a health status (`SECURE`, `COMPROMISED`, `ROOT_ACCESS`).
* **The Red Agent (Offensive AI):** This agent's objective is to navigate the network topology, discover vulnerabilities, and escalate privileges until it captures the central database. It uses heuristic search to find the most valuable targets and planning algorithms to execute multi-step exploits.
* **The Blue Agent (Defensive AI):** Operating as an intelligent Intrusion Detection System (IDS), this agent's goal is to maintain network integrity. It monitors simulated traffic and CPU spikes, using expert system logic to detect anomalies and adversarial search to predict and block the Red Agent's next move.

## 🧠 Core AI Integration (Curriculum Mapping)
This system is strictly engineered to implement foundational Artificial Intelligence paradigms:

* **Uninformed Search (Unit I & II):** The Red Agent utilizes **Breadth-First Search (BFS) / Depth-First Search (DFS)** during its reconnaissance phase to map the unknown network graph and discover target IP addresses.
* **Informed Search & Game Playing (Unit III):** * The Red Agent applies **A* Search** for optimal exploit routing through the network topology.
  * The Blue Agent utilizes the **Minimax Algorithm with Alpha-Beta Pruning** to treat the intrusion as a zero-sum game, predicting attacker movements to preemptively patch nodes or null-route IPs.
* **Logical Agents & Expert Systems (Unit IV & V):** The IDS is powered by a **Propositional Logic Expert System**. It applies forward-chaining rules against live network traffic logs to deduce threat levels (e.g., `IF port_scan_rate > 50/sec THEN Block_IP`).
* **Automated Planning (Unit VI):** The Red Agent utilizes **STRIPS (Goal Stack Planning)** to generate logical exploit chains. It works backward from a primary goal (`Data_Exfiltrated`) to satisfy preconditions (e.g., `Scan -> Bypass_Firewall -> Escalate_Privilege`).

## ⚙️ System Architecture
The project is decoupled into four highly specialized micro-services:
1. **The Engine (Backend):** A Python-based `FastAPI` application handling WebSocket communication and simulating OS-level process scheduling and network state.
2. **The Autonomous Agents:** Independent Python scripts representing the adversarial AIs, interacting with the engine's state asynchronously.
3. **The SIEM Logger (DBMS):** A relational database system acting as a Security Information and Event Management logger, recording every packet sent and defensive maneuver deployed for forensic analysis.
4. **The War Room (Frontend):** A `React.js` command center utilizing graph-visualization libraries to render the live battle state, node health, and attack vectors in real-time.
