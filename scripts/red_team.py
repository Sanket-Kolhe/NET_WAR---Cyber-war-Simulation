import time
import requests

API_URL = "http://localhost:8000/api"

def print_action(msg):
    print(f"[RED TEAM] {msg}")

def run_attacker_ai():
    print_action("Initializing AI Attack Sequence...")
    time.sleep(1)

    # Phase 1: Reconnaissance (Unit II: Uninformed Search - BFS Concept)
    print_action("Executing network scan (BFS)...")
    response = requests.post(f"{API_URL}/scan")
    if response.status_code == 200:
        data = response.json()
        discovered_nodes = data.get("discovered_nodes", [])
        print_action(f"Discovered {len(discovered_nodes)} nodes on the subnet.")
    else:
        print_action("Scan failed.")
        return

    # Phase 2: Exploitation & Planning (Unit VI: Planning - Sequential kill chain)
    for node in discovered_nodes:
        # We assume the AI logic identified standard nodes vs the Database
        if node['os_type'] != 'Database':
            print_action(f"Targeting intermediate node {node['id']} ({node['ip_address']})")
            time.sleep(1) # Synthesize delay for visual effect on frontend
            
            attack_response = requests.post(f"{API_URL}/attack", json={"target_node_id": node['id']})
            if attack_response.status_code == 200:
                print_action(f"SUCCESS: Compromised {node['ip_address']}")
            else:
                print_action(f"FAILED: Could not breach {node['ip_address']}")
    
    # Final Phase: The Objective
    print_action("Lateral movement complete. Initiating final strike on Database Server...")
    time.sleep(3)
    db_node = next((n for n in discovered_nodes if n['os_type'] == 'Database'), None)
    
    if db_node:
        attack_response = requests.post(f"{API_URL}/attack", json={"target_node_id": db_node['id']})
        if attack_response.status_code == 200:
            print_action(f"CRITICAL SUCCESS: Database ({db_node['ip_address']}) compromised! Data Exfiltration started.")
        else:
            print_action("Failed to breach Database.")

if __name__ == "__main__":
    run_attacker_ai()
