"""
In-memory job store for pipeline tasks.

Each job represents one batch (directory of videos). Jobs run in a
background thread to keep the FastAPI event loop free.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


JobStatus = Literal["queued", "running", "done", "failed"]


@dataclass
class JobProgress:
    layer: str
    status: str
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Job:
    id: str
    batch_path: str
    video_glob: str
    status: JobStatus
    created_at: str
    updated_at: str
    videos: list[str] = field(default_factory=list)
    progress: list[JobProgress] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_id": Path(self.batch_path).name,
            "batch_path": self.batch_path,
            "video_glob": self.video_glob,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "videos": self.videos,
            "progress": [
                {"layer": p.layer, "status": p.status,
                 "error": p.error, "timestamp": p.timestamp}
                for p in self.progress
            ],
            "error": self.error,
        }


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, batch_path: str, video_glob: str) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        job = Job(
            id=uuid.uuid4().hex,
            batch_path=batch_path,
            video_glob=video_glob,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update_status(self, job_id: str, status: JobStatus, error: str | None = None):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = datetime.now(timezone.utc).isoformat()
                if error:
                    job.error = error

    def add_progress(self, job_id: str, layer: str, status: str, error: str | None = None):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.progress.append(JobProgress(layer=layer, status=status, error=error))
                job.updated_at = datetime.now(timezone.utc).isoformat()

    def set_videos(self, job_id: str, videos: list[str]):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.videos = videos


# Singleton store shared across the app
job_store = JobStore()
