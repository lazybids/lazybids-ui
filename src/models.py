from pydantic import BaseModel, validator
from enum import Enum
from typing import Optional, List, Union
import os
import shutil
import openneuro
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

class DatasetCreate(BaseModel):
    name: str
    folder: Optional[str]
    DatabaseID: Optional[str]
    Version: Optional[str]
    CopyFolder: Optional[bool]
    icon: Optional[]

    @validator('DatabaseID', pre=True, always=True)
    def check_a_or_b(cls, DatabaseID, values):
        if not values.get('folder') and not DatabaseID:
            raise ValueError('either a or b is required')
        elif values.get('folder') and DatabaseID:
            raise ValueError('Both server-folder and OpenNeuro database ID provided, provide either folder, or OpenNeuro databaseID not both.')
        return DatabaseID
    def initialize(self, zipfile: Union[Path, None] = None):
        data_dir = os.path.join(os.getenv("LAZYBIDS_DATA_PATH"), f"{self.DatabaseID}-{self.name}")
        if self.DatabaseID:
            os.makedirs(data_dir)
            if self.Version:
                openneuro.download(dataset=self.DatabaseID, target_dir=data_dir, version=self.Version)
            else:
                openneuro.download(dataset=self.DatabaseID, target_dir=data_dir)
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
            shutil.copy(self.icon, './static/'+uuid.uuid4()+os.path.split(self.icon)[-1])
            self.icon = "<img src='img_girl.jpg' alt='Girl in a jacket' width='500' height='600'>"
        else:
            self.icon=generateCharacter()
        return Dataset(folder=self.folder, name=self.name, OpenNeuroID=self.DatabaseID, OpenNeuroVersion=self.Version)


engine = create_engine("sqlite:///database.db")


SQLModel.metadata.create_all(engine)


# Now, we can use the response_model parameter using only a base model
# rather than having to use the OpenAISchema class
# class Currency(str, Enum):
#     dollar = '$'
#     euro = '€'

# class Argument(BaseModel):
#     argument: str
#     start_time: float

# class Product(BaseModel):
#     name: str
#     name_wo_brand: str
#     brand: str
#     price: int
#     currency: Currency
#     pros: List[str]
#     cons: List[str]

# class ProductList(BaseModel):
#     products: List[Product]

# class ProductsList(BaseModel):
#     products: List[Product]
#     transcript: str
#     #transcript_hash: str#Indexed(str, unique=True) # type: ignore


# class YTVideo(BaseModel):
#     id: str
#     title: str
#     channel: str
#     my_search: str

# class Task(BaseModel):
#     id: str

# class ValuableTranscript(BaseModel):
#     valuable: bool