from dotenv import load_dotenv, dotenv_values 
load_dotenv()
from pydantic import BaseModel, validator
from enum import Enum
from typing import Optional, List, Union
import os
import shutil
#import openneuro
from src import worker
from sqlmodel import Field, Session, SQLModel, create_engine
from pathlib import Path
from src.random_image import generateCharacter
import uuid

class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    folder: str
    OpenNeuroID: Optional[str]
    OpenNeuroVersion: Optional[str]
    description: Optional[str]
    icon: Optional[str]
    taskID: Optional[str]
    state: Optional[str]

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
    def createDataset(self, zipfile: Union[Path, None] = None):
        task_id = None
        data_dir = os.path.join(os.getenv("LAZYBIDS_DATA_PATH"), f"{self.DatabaseID}-{self.name}")
        if self.DatabaseID:
            os.makedirs(data_dir)
            task = worker.openneuro_download.delay(self.DatabaseID, self.Version, data_dir)
            task_id = task.id
            self.folder=data_dir
        elif self.folder:
            if self.CopyFolder:
                os.makedirs(data_dir)
                shutil.copy(self.folder,data_dir)
                self.folder = data_dir
        elif zipfile:
            os.makedirs(data_dir)
            shutil.unpack_archive(zipfile, data_dir)
            self.folder = data_dir
        if self.icon:
            icon_path = './static/'+uuid.uuid4()+os.path.split(self.icon)[-1]
            shutil.copy(self.icon, icon_path)
            self.icon = f"<img src='{icon_path}' alt='Dataset icon' width='200' height='200'>"
        else:
            self.icon=generateCharacter()
        dataset = Dataset(folder=self.folder, name=self.name, OpenNeuroID=self.DatabaseID, OpenNeuroVersion=self.Version, taskID=task_id, icon=self.icon)
        return dataset


engine = create_engine("sqlite:///database.db")


SQLModel.metadata.create_all(engine)

