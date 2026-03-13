"""
Red Team Attacker AI — scripts/red_team.py
==========================================
Phase 1: BFS Reconnaissance (Unit II)
Phase 2: STRIPS Kill Chain — EXPOSED → COMPROMISED → ROOT_ACCESS
WIN:  Database reaches ROOT_ACCESS
LOSE: Blue Team defends database through full round
"""

import time
import requests

API_URL = "http://localhost:8000/api"

# ── Timing (tune these for faster/slower battles) ──────────────────────────
ATTACK_STEP_DELAY  = 1.5  # seconds between each kill-chain step per node
MOVE_NEXT_DELAY    = 1.5  # seconds before moving to the next node
FINAL_STRIKE_DELAY = 2    # extra pause before hitting the database
ROUND_RESET_DELAY  = 3    # pause between attack rounds

def print_action(msg):
    print(f"[RED TEAM] {msg}")

def full_kill_chain(node: dict) -> str:
    """
    Runs the full 3-step kill chain on a node.
    Returns final status string: 'ROOT_ACCESS', 'DEFENDED', or 'PARTIAL'.
    """
    node_id = node['id']
    ip      = node['ip_address']

    # Hit 1: EXPOSED → COMPROMISED
    print_action(f"⚔️  [{node_id}] Exploit → {ip}...")
    time.sleep(ATTACK_STEP_DELAY)
    r = requests.post(f"{API_URL}/attack", json={"target_node_id": node_id})
    result = r.json() if r.status_code == 200 else {}
    status = result.get("new_status", "UNKNOWN")
    if not result.get("success") or status == "SECURE":
        print_action(f"   → ❌ Blocked by Blue Team on {node_id}")
        return "DEFENDED"
    print_action(f"   → {node_id} is now {status}")

    # Hit 2: COMPROMISED → ROOT_ACCESS (privilege escalation)
    print_action(f"🔺 [{node_id}] Privilege Escalation → {ip}...")
    time.sleep(ATTACK_STEP_DELAY)
    r2 = requests.post(f"{API_URL}/attack", json={"target_node_id": node_id})
    result2 = r2.json() if r2.status_code == 200 else {}
    status2 = result2.get("new_status", "UNKNOWN")
    if not result2.get("success") or status2 == "SECURE":
        print_action(f"   → ❌ Blue Team killed process on {node_id} mid-escalation!")
        return "DEFENDED"
    print_action(f"   → {node_id} is now {status2}")

    if status2 == "ROOT_ACCESS":
        print_action(f"   → 💀 ROOT_ACCESS on {node_id}!")
        return "ROOT_ACCESS"

    return "PARTIAL"


def run_attacker_ai():
    print_action("Initializing AI Attack Sequence...")
    print_action("WIN condition : Database reaches ROOT_ACCESS")
    print_action("LOSE condition: Blue Team defends database through full round\n")
    time.sleep(1)

    round_num = 0

    while True:
        round_num += 1
        print_action(f"\n{'='*55}")
        print_action(f"  ATTACK ROUND {round_num}")
        print_action(f"{'='*55}")

        # ── Phase 1: BFS Recon ────────────────────────────────────────────
        print_action("Running BFS scan...")
        response = requests.post(f"{API_URL}/scan")
        if response.status_code != 200:
            print_action("Scan failed — retrying in 3s")
            time.sleep(3)
            continue

        data             = response.json()
        discovered_nodes = data.get("discovered_nodes", [])
        bfs_order        = data.get("bfs_order", [])
        print_action(f"BFS Order: {' → '.join(bfs_order)}\n")

        # ── Phase 2: Attack intermediate nodes in BFS order ──────────────
        db_node = None
        owned   = 0
        for node in discovered_nodes:
            if node['os_type'] == 'Database':
                db_node = node
                continue
            result = full_kill_chain(node)
            if result == "ROOT_ACCESS":
                owned += 1
            time.sleep(MOVE_NEXT_DELAY)

        # ── Phase 3: Final strike on Database ─────────────────────────────
        if db_node:
            print_action(f"\n{'!'*55}")
            print_action(f"  FINAL TARGET: {db_node['id']} ({db_node['ip_address']})")
            print_action(f"{'!'*55}")
            time.sleep(FINAL_STRIKE_DELAY)
            result = full_kill_chain(db_node)

            if result == "ROOT_ACCESS":
                print_action("\n🚨 RED TEAM WINS — Database fully compromised!")
                print_action("   Data exfiltration in progress. Simulation over.")
                break  # ← RED TEAM WIN — exit
            else:
                print_action(f"\n🛡️  Blue Team defended the database this round!")
                print_action(f"   Nodes owned: {owned}/9. Regrouping in {ROUND_RESET_DELAY}s...")
                time.sleep(ROUND_RESET_DELAY)

    print_action("Attack sequence terminated.")


if __name__ == "__main__":
    try:
        run_attacker_ai()
    except requests.exceptions.ConnectionError:
        print("[RED TEAM] ❌ Cannot connect to backend. Is uvicorn running?")
    except KeyboardInterrupt:
        print("\n[RED TEAM] Attack sequence aborted.")
