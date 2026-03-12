import time
import requests

API_URL = "http://localhost:8000/api"

def print_action(msg):
    print(f"[BLUE TEAM] {msg}")

def run_defender_ai():
    print_action("Initializing IDS (Intrusion Detection System)...")
    print_action("Monitoring network traffic...")

    while True:
        try:
            # Poll the current network state
            # (In the final version, this could also use WebSockets for real-time pushing instead of polling)
            response = requests.get(f"{API_URL}/nodes")
            
            if response.status_code == 200:
                nodes = response.json()
                
                # Check for anomalies (Unit 4/5: Expert System Rules)
                for node in nodes:
                    if node['status'] == 'Infected' or node['cpu_usage'] > 80:
                        print_action(f"ANOMALY DETECTED: Node {node['id']} ({node['ip_address']}) exhibiting malicious behavior.")
                        print_action("Analyzing threat vector...")
                        
                        time.sleep(1.5) # Simulate AI calculation time (Minimax/Logic processing)
                        
                        if node['os_type'] == 'Database':
                            print_action("CRITICAL: Database is under attack! Deploying emergency countermeasures!")
                        else:
                            print_action(f"Executing automated remediation on Node {node['id']}...")
                            
                        # Send the patch command to the server
                        patch_response = requests.post(f"{API_URL}/patch", json={"target_node_id": node['id']})
                        
                        if patch_response.status_code == 200:
                            print_action(f"SUCCESS: Node {node['id']} restored to a safe state.")
                        else:
                            print_action(f"ERROR: Failed to patch Node {node['id']}.")
                            
        except requests.exceptions.ConnectionError:
            print_action("Connection to ARMOR Command Server lost.")
            break
            
        time.sleep(2) # Poll every 2 seconds

if __name__ == "__main__":
    run_defender_ai()
