"""
ARMOR Battle Simulator — scripts/simulate.py
=============================================
Red vs Blue sequential turns. One terminal, easy to read.

RED TEAM: attacks 2 nodes per turn (1 escalation + 1 exploit)
          pivots BFS from deepest owned node
BLUE TEAM: defends 1 node per turn (Expert System top priority)

Run with:  python simulate.py
"""

import time
import requests

API_URL  = "http://localhost:8000/api"

ATTACK_DELAY  = 1.0
DEFENSE_DELAY = 0.2
TURN_PAUSE    = 0.5
WIN_TURNS     = 5

RED   = "\033[91m"
GREEN = "\033[92m"
YEL   = "\033[93m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
RST   = "\033[0m"

STATUS_ICON = {
    "SECURE":      f"{GREEN}✅ SECURE      {RST}",
    "EXPOSED":     f"{YEL}⚠️  EXPOSED     {RST}",
    "COMPROMISED": f"{YEL}🔥 COMPROMISED  {RST}",
    "ROOT_ACCESS": f"{RED}💀 ROOT_ACCESS  {RST}",
}

RULES = [
    {"id": "R1", "sev": 10, "desc": "Database breached — emergency patch",
     "cond": lambda n: n["os_type"] == "Database"
                        and n["status"] in ("COMPROMISED", "ROOT_ACCESS"),
     "act":  "patch"},
    {"id": "R2", "sev": 9,  "desc": "ROOT_ACCESS — full patch",
     "cond": lambda n: n["status"] == "ROOT_ACCESS",
     "act":  "patch"},
    {"id": "R3", "sev": 8,  "desc": "Port scan surge >50/s",
     "cond": lambda n: n.get("scan_rate", 0) > 50,
     "act":  "block_port"},
    {"id": "R4", "sev": 7,  "desc": "Node COMPROMISED",
     "cond": lambda n: n["status"] == "COMPROMISED",
     "act":  "patch"},
    {"id": "R5", "sev": 5,  "desc": "Node EXPOSED",
     "cond": lambda n: n["status"] == "EXPOSED",
     "act":  "kill_process"},
]

# Depth = shortest hops from internet to each node (new branching topology)
DEPTH = {
    "Node_1":  0,
    "Node_2":  1, "Node_3":  1,
    "Node_4":  2, "Node_5":  2, "Node_6":  2,
    "Node_7":  3, "Node_8":  3, "Node_9":  3,
    "Node_10": 4,
}

# ── Helpers ───────────────────────────────────────────────────────────────

def print_board(nodes):
    print(f"\n{CYAN}{'─'*58}{RST}")
    print(f"{BOLD}  {'NODE':<16} {'OS':<10} {'STATUS':<22} CPU{RST}")
    print(f"{CYAN}{'─'*58}{RST}")
    for n in nodes:
        icon   = STATUS_ICON.get(n["status"], n["status"])
        db_tag = " 🗄️ DB" if n["os_type"] == "Database" else ""
        print(f"  {n['id']:<16} {n['os_type']:<10} {icon}  {n['cpu_usage']:>3}%{db_tag}")
    print(f"{CYAN}{'─'*58}{RST}\n")

def rprint(msg): print(f"{RED}  [🔴 RED ] {msg}{RST}")
def bprint(msg): print(f"{CYAN}  [🔵 BLUE] {msg}{RST}")
def info(msg):   print(f"           {msg}")

def get_nodes():
    r = requests.get(f"{API_URL}/nodes")
    return r.json() if r.status_code == 200 else []

# ══════════════════════════════════════════════════════════════════════════
#  RED TEAM — 2 strikes per turn + pivot BFS
#  Strike 1: escalate deepest COMPROMISED → ROOT_ACCESS
#  Strike 2: exploit deepest EXPOSED      → COMPROMISED
#  If nothing to attack: pivot BFS rescan from deepest owned node
# ══════════════════════════════════════════════════════════════════════════

def red_team_turn(nodes, owned_nodes):
    pivot = (max(owned_nodes, key=lambda nid: DEPTH.get(nid, 0))
             if owned_nodes else "Node_1")

    db_targets  = [n for n in nodes if n["os_type"] == "Database"
                   and n["status"] in ("EXPOSED", "COMPROMISED")]
    compromised = sorted(
        [n for n in nodes if n["status"] == "COMPROMISED" and n["os_type"] != "Database"],
        key=lambda n: DEPTH.get(n["id"], 0), reverse=True)
    exposed     = sorted(
        [n for n in nodes if n["status"] == "EXPOSED" and n["os_type"] != "Database"],
        key=lambda n: DEPTH.get(n["id"], 0), reverse=True)

    # Nothing exposed anywhere — trigger pivot BFS rescan
    if not db_targets and not compromised and not exposed:
        label = f"{pivot} (foothold)" if pivot != "Node_1" else "Node_1 (internet)"
        rprint(f"No targets. Pivot BFS from {label}...")
        r = requests.post(f"{API_URL}/scan", json={"start_node": pivot})
        if r.status_code == 200:
            js  = r.json()
            bfs = js.get("bfs_order", [])
            piv = js.get("pivot", pivot)
            rprint(f"BFS from [{piv}]: {' → '.join(bfs)}")
        return False, owned_nodes

    red_wins = False

    def attack(target):
        nonlocal owned_nodes, red_wins
        nid  = target["id"]
        stat = target["status"]
        desc = ("EXPLOIT → COMPROMISED" if stat == "EXPOSED"
                else "ESCALATE → ROOT_ACCESS")
        rprint(f"[pivot:{pivot}] {nid} — {desc}")
        time.sleep(ATTACK_DELAY)
        r  = requests.post(f"{API_URL}/attack", json={"target_node_id": nid})
        js = r.json() if r.status_code == 200 else {}
        if js.get("success"):
            ns = js.get("new_status", "?")
            rprint(f"  → {nid} now {ns}")
            if ns == "ROOT_ACCESS":
                owned_nodes = owned_nodes | {nid}
                rprint(f"  → 💀 {nid} OWNED (depth={DEPTH.get(nid,0)}, total={len(owned_nodes)})")
                # ── KEY FIX: immediately scan from this new foothold ──────
                # Exposes neighbors of the newly owned node so Red Team can
                # push deeper without waiting for "zero targets" to rescan.
                rprint(f"  → Scanning outward from new foothold {nid}...")
                sr = requests.post(f"{API_URL}/scan", json={"start_node": nid})
                if sr.status_code == 200:
                    exposed_now = sr.json().get("exposed_this_scan", [])
                    rprint(f"  → New targets exposed: {exposed_now}")
                if target["os_type"] == "Database":
                    red_wins = True
        else:
            rprint(f"  → {nid} already patched")


    # Strike 1: escalate deepest COMPROMISED (database if available)
    s1 = None
    if db_targets and db_targets[0]["status"] == "COMPROMISED":
        s1 = db_targets[0]
    elif compromised:
        s1 = compromised[0]

    if s1:
        attack(s1)
        if red_wins:
            return True, owned_nodes

    # Re-fetch nodes after strike1 (scan may have exposed new deeper nodes)
    fresh = get_nodes()
    fresh_exposed = sorted(
        [n for n in fresh if n["status"] == "EXPOSED" and n["os_type"] != "Database"],
        key=lambda n: DEPTH.get(n["id"], 0), reverse=True
    )
    fresh_db = [n for n in fresh if n["os_type"] == "Database"
                and n["status"] in ("EXPOSED", "COMPROMISED")]

    # Strike 2: exploit deepest EXPOSED (skip s1 node, prefer deeper nodes)
    skip = {s1["id"]} if s1 else set()
    pool = []
    if fresh_db and fresh_db[0]["status"] == "EXPOSED":
        pool.append(fresh_db[0])
    pool += [n for n in fresh_exposed if n["id"] not in skip]

    if pool:
        attack(pool[0])
        if red_wins:
            return True, owned_nodes

    return False, owned_nodes


# ══════════════════════════════════════════════════════════════════════════
#  BLUE TEAM — Expert System (1 response/turn) + Minimax proactive
#  Responds to the top-severity threat only; emergencies (sev>=9) get
#  immediate treatment regardless of turn budget.
# ══════════════════════════════════════════════════════════════════════════

def blue_team_turn(nodes):
    alerts = []
    for n in nodes:
        for rule in RULES:
            if rule["cond"](n):
                alerts.append((rule["sev"], rule, n))
    alerts.sort(key=lambda x: x[0], reverse=True)

    if not alerts:
        # Minimax: harden the most at-risk SECURE-bound node
        ORDER = ["EXPOSED", "COMPROMISED", "ROOT_ACCESS"]
        cands = [n for n in nodes if n["status"] in ORDER]
        if cands:
            worst = max(cands, key=lambda n: ORDER.index(n["status"]))
            bprint(f"[MINIMAX] Preemptive hardening → {worst['id']}")
            requests.post(f"{API_URL}/patch", json={"target_node_id": worst["id"]})
            info(f"📦 Patch → {worst['id']}")
        else:
            bprint("All nodes SECURE. Monitoring...")
        return

    handled = set()
    for sev, rule, node in alerts:
        if len(handled) >= 1 and sev < 9:
            break   # only 1 normal action per turn; emergencies (sev>=9) always fire
        nid = node["id"]
        if nid in handled:
            continue
        act = rule["act"]
        bprint(f"[Rule {rule['id']} | sev={sev}] {rule['desc']} → {nid}")
        if act == "patch":
            requests.post(f"{API_URL}/patch", json={"target_node_id": nid})
            info(f"  📦 Patch → {nid}")
        elif act == "kill_process":
            requests.post(f"{API_URL}/kill_process", json={"target_node_id": nid})
            info(f"  🔪 Kill → {nid}")
        elif act == "block_port":
            port = 22 if node.get("os_type") in ("Linux", "Database") else 3389
            requests.post(f"{API_URL}/block_port", json={"target_node_id": nid, "port": port})
            info(f"  🔒 Port {port} blocked on {nid}")
        handled.add(nid)
        time.sleep(DEFENSE_DELAY)

# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{CYAN}{'═'*58}")
    print(f"   A.R.M.O.R  —  RED vs BLUE  (Pivot BFS + 2-strike Red)")
    print(f"{'═'*58}{RST}")
    print(f"  {RED}Red Team{RST}  wins → Database reaches ROOT_ACCESS")
    print(f"  {CYAN}Blue Team{RST} wins → All nodes SECURE for {WIN_TURNS} clean turns")
    print(f"{CYAN}{'═'*58}{RST}\n")

    # ── Reset backend state ───────────────────────────────────────────────
    # The backend keeps running between runs; reset ensures all nodes start SECURE.
    print(f"{BOLD}Resetting battlefield...{RST}")
    rr = requests.post(f"{API_URL}/reset")
    if rr.status_code != 200:
        print("❌ Backend not reachable. Run: uvicorn main:app --reload")
        return
    print(f"✅ All nodes reset to SECURE.\n")

    # ── Initial BFS recon from internet entry point ───────────────────────
    print(f"{BOLD}Phase 1: BFS Reconnaissance from Node_1...{RST}")
    r = requests.post(f"{API_URL}/scan", json={"start_node": "Node_1"})
    if r.status_code != 200:
        print("❌ Scan failed.")
        return

    js  = r.json()
    bfs = js.get("bfs_order", [])
    print(f"BFS from Node_1: {' → '.join(bfs)}\n")
    time.sleep(1)

    turn         = 0
    secure_turns = 0
    owned_nodes  = set()

    while True:
        turn  += 1
        nodes  = get_nodes()
        if not nodes:
            print("❌ Lost backend connection.")
            break

        print(f"\n{BOLD}━━━ TURN {turn} {'━'*42}{RST}")
        if owned_nodes:
            pivot = max(owned_nodes, key=lambda nid: DEPTH.get(nid, 0))
            print(f"     {RED}Red foothold: {sorted(owned_nodes)} | Pivot: {pivot}{RST}")
        print_board(nodes)

        # Red Team
        print(f"{BOLD}🔴 RED TEAM (2 strikes):{RST}")
        red_wins, owned_nodes = red_team_turn(nodes, owned_nodes)
        if red_wins:
            nodes = get_nodes()
            print_board(nodes)
            print(f"\n{RED}{BOLD}🚨  RED TEAM WINS — Database compromised! 🚨{RST}\n")
            break

        time.sleep(TURN_PAUSE)
        nodes = get_nodes()

        # Blue Team
        print(f"\n{BOLD}🔵 BLUE TEAM (1 response):{RST}")
        blue_team_turn(nodes)

        # Reclaim — if Blue patched an owned node all the way back to SECURE
        nodes = get_nodes()
        reclaimed = {nid for nid in owned_nodes
                     if any(n["id"] == nid and n["status"] == "SECURE" for n in nodes)}
        if reclaimed:
            owned_nodes -= reclaimed
            bprint(f"Reclaimed {sorted(reclaimed)} — Red Team loses these footholds!")

        time.sleep(TURN_PAUSE)

        # Win check
        nodes = get_nodes()
        if all(n["status"] == "SECURE" for n in nodes):
            secure_turns += 1
            bprint(f"Network clean! ({secure_turns}/{WIN_TURNS})")
            if secure_turns >= WIN_TURNS:
                print_board(nodes)
                print(f"\n{GREEN}{BOLD}🏆  BLUE TEAM WINS — Network secured! 🏆{RST}\n")
                break
        else:
            secure_turns = 0

        time.sleep(0.3)

    print(f"{BOLD}Simulation ended after {turn} turns.{RST}\n")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Backend not running. Start: uvicorn main:app --reload")
    except KeyboardInterrupt:
        print(f"\n{BOLD}Simulation aborted.{RST}")
