import uuid
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
import importlib.util
import sys
import os
from pathlib import Path
from datetime import datetime

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# In-memory job store (consider using a proper database in production)
jobs_store = {}

def get_logger():
    logger = logging.getLogger("uvicorn.error")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def run_upload_events_job(job_id: str):
    logger = get_logger()
    try:
        logger.info(f"Starting upload events job {job_id}")
        jobs_store[job_id]["status"] = "running"
        jobs_store[job_id]["started_at"] = datetime.utcnow().isoformat()
        
        # Import the upload_events module
        upload_events_path = os.path.join(os.path.dirname(__file__), "..", "jobs", "upload_events.py")
        spec = importlib.util.spec_from_file_location("upload_events", upload_events_path)
        upload_events = importlib.util.module_from_spec(spec)
        sys.modules["upload_events"] = upload_events
        spec.loader.exec_module(upload_events)
        
        # Run the main function
        upload_events.main()
        
        jobs_store[job_id].update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": {"status": "success", "message": "Events upload job completed successfully"}
        })
        logger.info(f"Completed upload events job {job_id}")
        
    except Exception as e:
        error_msg = f"Error running upload events job: {str(e)}"
        logger.error(error_msg, exc_info=True)
        jobs_store[job_id].update({
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error": error_msg
        })
        # Re-raise to ensure the background task fails visibly
        raise

@router.post("/upload-events", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def trigger_upload_events(background_tasks: BackgroundTasks):
    """
    Trigger the upload events job as a background task.
    This will sync events from the database to the vector store.
    """
    try:
        job_id = str(uuid.uuid4())
        jobs_store[job_id] = {
            "id": job_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "type": "events_upload"
        }
        
        # Run the job in the background
        background_tasks.add_task(run_upload_events_job, job_id)
        
        return {
            "job_id": job_id,
            "status": "accepted",
            "message": "Events upload job has been queued and will run in the background",
            "check_status": f"/api/jobs/status/{job_id}"
        }
        
    except Exception as e:
        get_logger().error(f"Failed to start upload events job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": f"Failed to start upload events job: {str(e)}"}
        )

@router.get("/status/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str):
    """Check the status of a background job"""
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "Job not found"}
        )
    
    response = {
        "job_id": job_id,
        "status": job["status"],
        "created_at": job["created_at"]
    }
    
    if "started_at" in job:
        response["started_at"] = job["started_at"]
    
    if "completed_at" in job:
        response["completed_at"] = job["completed_at"]
    
    if "result" in job:
        response["result"] = job["result"]
    elif "error" in job:
        response["error"] = job["error"]
    
    return response
