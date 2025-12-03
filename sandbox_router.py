from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List

# Prefer Redis+RQ-backed task inspection when available
try:
    from task_queue import get_task_meta, get_task_logs, get_task_artifacts
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

try:
    from execute_router import TASKS
except ImportError:
    TASKS = {}

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class SandboxJobResponse(BaseModel):
    job_id: str
    status: str
    goblin: str
    task: str
    created_at: float


@router.get("/jobs")
async def list_jobs():
    """List sandbox jobs (in-memory TASKS)"""
    try:
        if REDIS_AVAILABLE:
            # Use Redis key pattern to list tasks
            import redis
            import os
            REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(REDIS_URL)
            keys = r.keys("task:*")
            jobs = []
            for key in keys:
                k = key.decode('utf-8')
                if ":logs" in k or ":artifacts" in k:
                    continue
                task_id = k.split(":", 1)[1]
                meta = get_task_meta(task_id)
                jobs.append({
                    "job_id": task_id,
                    "status": meta.get("status"),
                    "goblin": None,
                    "task": None,
                    "created_at": meta.get("created_at"),
                })
            return {"jobs": jobs, "total": len(jobs)}
        else:
            jobs = [
                {
                    "job_id": job_id,
                    "status": info.get("status"),
                    "goblin": info.get("goblin"),
                    "task": info.get("task"),
                    "created_at": info.get("created_at"),
                }
                for job_id, info in TASKS.items()
            ]
            return {"jobs": jobs, "total": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sandbox jobs: {str(e)}")


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Get logs for a sandbox job (mocked chunks)"""
    if REDIS_AVAILABLE:
        logs = get_task_logs(job_id)
        if logs is None:
            raise HTTPException(status_code=404, detail="Job not found")
    else:
        if job_id not in TASKS:
            raise HTTPException(status_code=404, detail="Job not found")

        job = TASKS[job_id]
        logs: List[Dict[str, Any]] = job.get("logs", [])

    # If logs are not present, return simulated logs
    if not logs:
        logs = [
            {"level": "info", "timestamp": job.get("created_at"), "message": f"Task {job_id} started by {job.get('goblin')}"},
            {"level": "info", "timestamp": job.get("created_at") + 1, "message": f"Processing task: {job.get('task')}"},
            {"level": "info", "timestamp": job.get("created_at") + 2, "message": f"Task {job_id} completed"},
        ]

    return {"job_id": job_id, "logs": logs}


@router.get("/jobs/{job_id}/artifacts")
async def get_job_artifacts(job_id: str):
    """Return list of artifact files produced by the job (placeholder)"""
    if REDIS_AVAILABLE:
        artifacts = get_task_artifacts(job_id)
        if artifacts is None:
            raise HTTPException(status_code=404, detail="Job not found")
    else:
        if job_id not in TASKS:
            raise HTTPException(status_code=404, detail="Job not found")

        job = TASKS[job_id]
        artifacts = job.get("artifacts", [])

    return {"job_id": job_id, "artifacts": artifacts}
