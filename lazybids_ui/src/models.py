from dotenv import load_dotenv, dotenv_values 
load_dotenv()
from pydantic import BaseModel, validator
from enum import Enum
from typing import Optional, List, Union
import os
import shutil
from sqlmodel import Field, Session, SQLModel, create_engine
from pathlib import Path
from lazybids_ui.src.random_image import generateCharacter
import uuid
import functools
import lazybids
from fastapi import BackgroundTasks
from sqlmodel import Session, select
import openneuro



engine = create_engine("sqlite:///database.db", pool_size=20, max_overflow=30)
@functools.lru_cache(maxsize=int(os.getenv("DATASET_CACHE_SIZE")))
def get_ds(folder):
    ds = lazybids.Dataset.from_folder(folder, load_scans_in_memory=False)
    return ds

def get_db():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()

class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

def openneuro_download_task(database_id: str, version: str, data_dir: str, job_id: str):
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





class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    folder: str
    OpenNeuroID: Optional[str]
    OpenNeuroVersion: Optional[str]
    description: Optional[str]
    icon: Optional[str]
    taskID: Optional[str]
    state: Optional[JobStatus]

def update_job_status(session: Session, job_id: str, status: JobStatus):
    statement = select(Dataset).where(Dataset.taskID == job_id)
    dataset = session.exec(statement).first()
    if dataset:
        dataset.state = status
        session.add(dataset)
        session.commit()
        
async def get_job_status(job_id: str):
    session = next(get_db())
    statement = select(Dataset).where(Dataset.taskID == job_id)
    dataset = session.exec(statement).first()
    if dataset:
        return {"job_id": job_id, "status": dataset.state}
    return {"job_id": job_id, "status": "Not found"}

class DatasetCreate(BaseModel):
    name: str
    folder: Optional[str]
    DatabaseID: Optional[str]
    Version: Optional[str]
    CopyFolder: Optional[bool]
    icon: Optional[str]

    @validator('DatabaseID', pre=True, always=True)
    def check_a_or_b(cls, DatabaseID, values):
        if not values.get('folder') and not DatabaseID:
            raise ValueError('either a or b is required')
        elif values.get('folder') and DatabaseID:
            raise ValueError('Both server-folder and OpenNeuro database ID provided, provide either folder, or OpenNeuro databaseID not both.')
        return DatabaseID

    def createDataset(self, zipfile: Union[Path, None] = None, background_tasks: BackgroundTasks = None):
        task_id = None
        data_dir = os.path.join(os.getenv("LAZYBIDS_DATA_PATH"), f"{self.DatabaseID}-{self.name}")
        if self.DatabaseID:
            os.makedirs(data_dir)
            task_id = str(uuid.uuid4())
            self.folder = data_dir
            if background_tasks:
                background_tasks.add_task(
                    openneuro_download_task,
                    self.DatabaseID,
                    self.Version or 'latest',
                    data_dir,
                    task_id
                )
        elif self.folder:
            if self.CopyFolder:
                shutil.copytree(self.folder, data_dir)
                self.folder = data_dir
        elif zipfile:
            os.makedirs(data_dir)
            shutil.unpack_archive(zipfile, data_dir)
            self.folder = data_dir
        if self.icon:
            icon_path = './static/'+str(uuid.uuid4())+os.path.split(self.icon)[-1]
            shutil.copy(self.icon, icon_path)
            self.icon = f"<img src='{icon_path}' alt='Dataset icon' width='200' height='200'>"
        else:
            self.icon = generateCharacter()
        dataset = Dataset(
            folder=self.folder,
            name=self.name,
            OpenNeuroID=self.DatabaseID,
            OpenNeuroVersion=self.Version,
            taskID=task_id,
            icon=self.icon,
            state='PENDING' if self.DatabaseID else None
        )
        return dataset


SQLModel.metadata.create_all(engine)



