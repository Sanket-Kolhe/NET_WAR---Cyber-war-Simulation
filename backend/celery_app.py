from celery import Celery
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "net_war",
    broker=redis_url,
    backend=redis_url
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        'simulation-loop-tick': {
            'task': 'celery_app.tick_simulation',
            'schedule': 1.5, # run every 1.5 seconds roughly
        },
    }
)

@celery.task
def tick_simulation():
    from engine.network import NetworkEnvironment
    import json
    import redis
    
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    
    # fetch state
    state_str = r.get("battlefield_state")
    if not state_str:
        battlefield = NetworkEnvironment()
        previous_nodes = {}
    else:
        state_dict = json.loads(state_str)
        battlefield = NetworkEnvironment.from_dict(state_dict)
        previous_nodes = state_dict.get("nodes", {})
        
    battlefield.tick_all_nodes()

    new_state = battlefield.to_dict()
    new_nodes = new_state.get("nodes", {})

    changed_nodes = {}
    for node_id, node_data in new_nodes.items():
        if previous_nodes.get(node_id) != node_data:
            num = node_id.replace("Node_", "")
            changed_nodes[node_id] = {
                "id": node_id,
                "ip_address": f"192.168.1.{num}",
                "os_type": "Database" if node_data.get("is_database") else node_data.get("os"),
                "status": node_data.get("status"),
                "cpu_usage": node_data.get("cpu"),
                "ports": node_data.get("ports", []),
                "blocked_ports": node_data.get("blocked_ports", []),
                "scan_rate": node_data.get("scan_rate", 0),
                "is_database": node_data.get("is_database", False),
            }

    payload = {
        "type": "delta",
        "changed_nodes": changed_nodes,
    }

    # Save back
    r.set("battlefield_state", json.dumps(new_state))

    # Broadcast through Redis Pub/Sub only when there is a real delta
    if changed_nodes:
        r.publish("battlefield_updates", json.dumps(payload))
