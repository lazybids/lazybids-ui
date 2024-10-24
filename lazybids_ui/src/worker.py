import asyncio
from fastapi import BackgroundTasks
import openneuro
from src.models import get_db, update_job_status, JobStatus
from sqlmodel import Session, select
from enum import Enum



async def openneuro_download_task(database_id: str, version: str, data_dir: str, job_id: str):
    # Get database session
    session = next(get_db())
    
    try:
        # Update job status to RUNNING
        update_job_status(session, job_id, JobStatus.RUNNING)
        
        if version and version != 'latest':
            openneuro.download(dataset=database_id, target_dir=data_dir, tag=version)
        else:
            openneuro.download(dataset=database_id, target_dir=data_dir)
        
        # Update job status to SUCCESS
        update_job_status(session, job_id, JobStatus.SUCCESS)
    except Exception as e:
        # Update job status to FAILURE
        update_job_status(session, job_id, JobStatus.FAILURE)
        # You might want to log the error here
        print(f"Error in openneuro_download_task: {str(e)}")



async def start_openneuro_download(background_tasks: BackgroundTasks, database_id: str, version: str, data_dir: str, job_id: str):
    # Initialize job status as PENDING
    session = next(get_db())
    
    
    # Add the task to background tasks
    background_tasks.add_task(openneuro_download_task, database_id, version, data_dir, job_id)

    return {"job_id": job_id, "status": JobStatus.PENDING}

