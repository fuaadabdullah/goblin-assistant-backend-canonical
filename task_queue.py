import os
import redis
import json
import time
from typing import Dict, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

r = redis.from_url(REDIS_URL)


def enqueue_task(task_id: str, payload: Dict[str, Any]) -> str:
    key = f"task:{task_id}"
    r.hset(key, mapping={"status": "queued", "created_at": time.time(), "payload": json.dumps(payload)})
    # Push to queue list (legacy and for simple polling), but RQ will be used for background execution
    r.lpush("tasks:queue", task_id)
    return task_id


def set_task_running(task_id: str):
    key = f"task:{task_id}"
    r.hset(key, mapping={"status": "running", "started_at": time.time()})


def set_task_completed(task_id: str, result: str):
    key = f"task:{task_id}"
    r.hset(key, mapping={"status": "completed", "result": result, "completed_at": time.time()})


def add_task_log(task_id: str, level: str, message: str):
    key = f"task:{task_id}:logs"
    r.rpush(key, json.dumps({"ts": time.time(), "level": level, "message": message}))


def get_task_logs(task_id: str, tail: int = 100):
    key = f"task:{task_id}:logs"
    items = r.lrange(key, -tail, -1)
    return [json.loads(i) for i in items]


def add_task_artifact(task_id: str, artifact: Dict[str, Any]):
    key = f"task:{task_id}:artifacts"
    r.rpush(key, json.dumps(artifact))


def get_task_artifacts(task_id: str):
    key = f"task:{task_id}:artifacts"
    items = r.lrange(key, 0, -1)
    return [json.loads(i) for i in items]


def get_task_meta(task_id: str) -> Dict[str, Any]:
    key = f"task:{task_id}"
    raw = r.hgetall(key)
    if not raw:
        return {}
    decoded = {k.decode('utf-8'): v.decode('utf-8') for k, v in raw.items()}
    return decoded


def clear_task(task_id: str):
    key = f"task:{task_id}"
    r.delete(key)
    r.delete(f"task:{task_id}:logs")
    r.delete(f"task:{task_id}:artifacts")


def process_task(task_id: str):
    """Process a task in a worker process; used by RQ to execute jobs."""
    meta = get_task_meta(task_id)
    if not meta:
        add_task_log(task_id, "error", "Task metadata not found")
        return

    set_task_running(task_id)
    add_task_log(task_id, "info", "Task started")
    # Simulate doing work
    time.sleep(2)
    # Simulate creating artifact
    artifact = {"name": "result.txt", "contents": f"Task {task_id} executed"}
    add_task_artifact(task_id, artifact)
    add_task_log(task_id, "info", "Task completed and artifact created")
    set_task_completed(task_id, result="success")
