from typing import Optional, Union, List
from fastapi import APIRouter, Request, Header, Form, UploadFile, Depends
from fastapi.responses import FileResponse
import lazybids
from . import models
from .models import get_ds, engine

from sqlmodel import Session, select

router = APIRouter(prefix="/api")

@router.get("/datasets")
async def get_datasets(session: Session = Depends(models.get_db)):
    statement = select(models.Dataset)
    datasets = session.exec(statement).all()
    return datasets

@router.get("/dataset/{ds_id}", response_model=lazybids.Dataset, response_model_exclude_unset=True, 
            response_model_exclude_none=True, response_model_exclude=["scans", "subjects", "sessions"])
async def get_dataset(ds_id:int, session: Session = Depends(models.get_db)):
    with Session(engine) as session:
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()     
    ds = get_ds(dataset.folder)
    return ds

@router.get("/dataset/{ds_id}/subjects", response_model=List[lazybids.Subject], response_model_exclude_unset=True, 
            response_model_exclude_none=True)#, response_model_exclude=["parent", "sessions", "scans"])
async def get_subjects(ds_id:int, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return [s.all_meta_data for s in ds.subjects]
