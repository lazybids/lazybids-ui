from pydantic import BaseModel
from enum import Enum
from typing import Optional, List

from sqlmodel import Field, Session, SQLModel, create_engine
from pathlib import Path

class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    folder: str
    description: Optional[str]
    icon: Optional[str]

engine = create_engine("sqlite:///database.db")


SQLModel.metadata.create_all(engine)


# Now, we can use the response_model parameter using only a base model
# rather than having to use the OpenAISchema class
class Currency(str, Enum):
    dollar = '$'
    euro = '€'

class Argument(BaseModel):
    argument: str
    start_time: float

class Product(BaseModel):
    name: str
    name_wo_brand: str
    brand: str
    price: int
    currency: Currency
    pros: List[str]
    cons: List[str]

class ProductList(BaseModel):
    products: List[Product]

class ProductsList(BaseModel):
    products: List[Product]
    transcript: str
    #transcript_hash: str#Indexed(str, unique=True) # type: ignore


class YTVideo(BaseModel):
    id: str
    title: str
    channel: str
    my_search: str

class Task(BaseModel):
    id: str

class ValuableTranscript(BaseModel):
    valuable: bool