"""
FastAPI routes - REST endpoints + WebSocket for live migration streaming.

Endpoints:
  POST   /api/migrate              - upload files + start migration
  GET    /api/migrate/{job_id}     - get full result
  GET    /api/migrate/{job_id}/status  - lightweight status poll
  GET    /api/migrate/{job_id}/download - download ZIP
  WS     /ws/{job_id}             - live hook event stream
"""
import asyncio
import json
import logging
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response

from ..agent import migration_agent as agent
from ..hooks.hook_engine import hook_engine
from ..tools.file_store import file_store
from .models import (
    JobCreatedResponse,
    JobStatusResponse,
    MigrationResultResponse,
    JavaFileResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── POST /api/migrate ─────────────────────────────────────────────────────────

@router.post("/migrate", response_model=JobCreatedResponse)
async def start_migration(
    background_tasks: BackgroundTasks,
    files: Optional[List[UploadFile]] = File(default=None, description=".NET source files (.cs, .csproj, .json)"),
    directory_path: Optional[str] = Form(default=None, description="Local directory path to migrate"),
    api_key: str = Form(default="", description="Groq/OpenRouter API key (optional for Ollama)"),
    model: str   = Form(default="qwen/qwen3-coder:free", description="LLM model name (Ollama: llama3.2, Groq: llama-3.3-70b-versatile, OpenRouter free: qwen/qwen3-coder:free)"),
):
    """
    Upload .NET files or select a local folder and kick off an async migration job.
    Returns a job_id immediately; use /ws/{job_id} for live progress.
    """
    # Filter out empty files if any
    uploaded_files = [f for f in files if f.filename] if files else []

    if not uploaded_files and not directory_path:
        raise HTTPException(status_code=400, detail="Either source files or a local directory path must be provided.")

    if not model.strip():
        raise HTTPException(status_code=400, detail="Model name is required")

    if directory_path:
        import os
        if not os.path.exists(directory_path):
            raise HTTPException(status_code=400, detail=f"Local directory path does not exist: {directory_path}")
        if not os.path.isdir(directory_path):
            raise HTTPException(status_code=400, detail=f"Specified path is not a directory: {directory_path}")

    # Create job
    job_id = agent.create_job()

    # Store uploaded files if any, extracting zip files if uploaded
    import io
    import zipfile
    from pathlib import Path

    has_dot_net_files = False
    allowed_exts = {".cs", ".csproj", ".json", ".xml", ".config", ".txt"}
    ignored_dirs = {"bin", "obj", ".git", ".vs", "migrated-java", "__pycache__", "node_modules"}

    for upload in uploaded_files:
        filename = upload.filename or "unnamed.cs"
        raw = await upload.read()
        
        if filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for zinfo in zf.infolist():
                        if zinfo.is_dir():
                            continue
                        
                        # Check if any path segment is in ignored_dirs
                        parts = Path(zinfo.filename).parts
                        if any(p.lower() in ignored_dirs for p in parts):
                            continue
                            
                        ext = Path(zinfo.filename).suffix.lower()
                        if ext in allowed_exts:
                            try:
                                content = zf.read(zinfo.filename).decode("utf-8", errors="replace")
                            except Exception:
                                content = zf.read(zinfo.filename).decode("latin-1", errors="replace")
                            
                            file_store.store_input(job_id, zinfo.filename, content)
                            logger.info("Extracted from zip: %s (%d chars) → job %s", zinfo.filename, len(content), job_id)
                            
                            if ext in {".cs", ".csproj"}:
                                has_dot_net_files = True
            except zipfile.BadZipFile:
                file_store.cleanup(job_id)
                raise HTTPException(status_code=400, detail=f"Uploaded file {filename} is not a valid zip archive.")
        else:
            # Normal file
            ext = Path(filename).suffix.lower()
            if ext in allowed_exts:
                try:
                    content = raw.decode("utf-8", errors="replace")
                except Exception:
                    content = raw.decode("latin-1", errors="replace")
                
                file_store.store_input(job_id, filename, content)
                logger.info("Uploaded: %s (%d bytes) → job %s", filename, len(raw), job_id)
                
                if ext in {".cs", ".csproj"}:
                    has_dot_net_files = True

    # Validate that we actually have .NET source files to migrate
    if uploaded_files and not has_dot_net_files:
        file_store.cleanup(job_id)
        raise HTTPException(
            status_code=400,
            detail="Validation failed: The uploaded files or zip archive do not contain any .NET source code (.cs or .csproj files)."
        )

    # Launch migration pipeline in background
    background_tasks.add_task(
        agent.run_migration,
        job_id=job_id,
        api_key=api_key.strip(),
        model=model.strip(),
        directory_path=directory_path,
    )

    return JobCreatedResponse(job_id=job_id)


# ── GET /api/migrate/{job_id}/status ─────────────────────────────────────────

@router.get("/migrate/{job_id}/status", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """Lightweight status poll - progress percentage and current step."""
    job = agent.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        error=job.error,
    )


# ── GET /api/migrate/{job_id} ─────────────────────────────────────────────────

@router.get("/migrate/{job_id}", response_model=MigrationResultResponse)
async def get_result(job_id: str):
    """Return full migration output once the job is complete."""
    job = agent.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status.value == "error":
        raise HTTPException(status_code=500, detail=job.error or "Migration failed")

    if job.status.value != "complete":
        raise HTTPException(status_code=202, detail="Migration still in progress")

    output = job.output
    return MigrationResultResponse(
        job_id=job_id,
        status=job.status.value,
        analysis=output.analysis,
        java_files=[JavaFileResponse(filename=f.filename, content=f.content) for f in output.java_files],
        test_files=[JavaFileResponse(filename=f.filename, content=f.content) for f in output.test_files],
        pom_xml=output.pom_xml,
        application_yml=output.application_yml,
        notes=output.notes,
        total_java_files=len(output.java_files),
        total_test_files=len(output.test_files),
    )


# ── GET /api/migrate/{job_id}/download ───────────────────────────────────────

@router.get("/migrate/{job_id}/download")
async def download_zip(job_id: str):
    """Stream the packaged Maven project ZIP for download."""
    job = agent.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.status.value != "complete":
        raise HTTPException(status_code=400, detail="Migration not yet complete")
    if not job.zip_bytes:
        raise HTTPException(status_code=500, detail="ZIP not available")

    return Response(
        content=job.zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="migrated-app-{job_id[:8]}.zip"',
        },
    )


# ── WebSocket /ws/{job_id} ────────────────────────────────────────────────────

@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    Live event stream for a migration job.
    Receives JSON payloads: { event, job_id, message, data }
    """
    await websocket.accept()
    logger.info("WebSocket connected for job %s", job_id)

    # Verify job exists
    job = agent.get_job(job_id)
    if not job:
        await websocket.send_text(json.dumps({
            "event": "ERROR",
            "message": f"Job {job_id} not found",
        }))
        await websocket.close()
        return

    # Send initial state
    await websocket.send_text(json.dumps({
        "event": "CONNECTED",
        "job_id": job_id,
        "message": f"Connected - job status: {job.status.value}",
        "data": {"status": job.status.value, "progress": job.progress},
    }))

    # If already complete, send final state immediately
    if job.status.value == "complete":
        await websocket.send_text(json.dumps({
            "event": "MIGRATION_COMPLETE",
            "job_id": job_id,
            "message": "Migration already complete",
            "data": {"status": "complete", "progress": 100},
        }))
        await websocket.close()
        return

    # Register live callback
    async def ws_callback(payload: dict):
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            pass

    hook_engine.add_ws_callback(job_id, ws_callback)

    try:
        # Keep connection alive until job completes or client disconnects
        while True:
            job = agent.get_job(job_id)
            if job and job.status.value in ("complete", "error"):
                break
            # Ping to detect disconnect
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Normal - just keep waiting
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    finally:
        hook_engine.remove_ws_callback(job_id, ws_callback)
        try:
            await websocket.close()
        except Exception:
            pass
