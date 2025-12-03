import os
import time
import json
from redis import Redis
from rq import Worker, Queue, Connection
from task_queue import r as redis_client, add_task_log, set_task_running, set_task_completed, add_task_artifact

# This worker uses functions to process tasks placed into Redis
# Start with: REDIS_URL=redis://host:port/0 python worker.py

if __name__ == "__main__":
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_conn = Redis.from_url(REDIS_URL)
    q = Queue(connection=redis_conn)

    with Connection(redis_conn):
        w = Worker([q])
        w.work()
