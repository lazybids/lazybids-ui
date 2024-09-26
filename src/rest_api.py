from typing import Optional, Union, List
from fastapi import APIRouter, Request, Header, Form, UploadFile, Depends
from fastapi.responses import FileResponse
import lazybids
from . import models
from .models import get_ds, engine
import tempfile
import os
from sqlmodel import Session, select

router = APIRouter(prefix="/api")

@router.get("/datasets", tags=["RESTAPI"])
async def get_datasets(session: Session = Depends(models.get_db)):
    statement = select(models.Dataset)
    datasets = session.exec(statement).all()
    return datasets

@router.get("/dataset/{ds_id}", response_model=lazybids.Dataset, response_model_exclude_unset=True, 
            response_model_exclude_none=True, response_model_exclude=["scans", "subjects", "sessions"], tags=["RESTAPI"])
async def get_dataset(ds_id:int, session: Session = Depends(models.get_db)):
    with Session(engine) as session:
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()     
    ds = get_ds(dataset.folder)
    return ds

@router.get("/dataset/{ds_id}/subjects", response_model=List[lazybids.Subject], response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])
async def get_subjects(ds_id:int, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return [ lazybids.Subject(s.all_meta_data) for s in ds.subjects.values()]

@router.get("/dataset/{ds_id}/subjects/{sub_id}", response_model=lazybids.Subject, response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])
async def get_subject(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].all_meta_data

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions", response_model=List[lazybids.Session], response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])
async def get_sessions(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return [s.all_meta_data for s in ds.subjects[sub_id].sessions.values()]

@router.get("/dataset/{ds_id}/subjects/{sub_id}/scans",  response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])
async def get_subject_scans(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return [s.all_meta_data for s in ds.subjects[sub_id].scans]

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions/{ses_id}", response_model=lazybids.Session, response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])#, response_model_exclude=["parent", "sessions", "scans"])
async def get_session(ds_id:int, sub_id:str, ses_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].sessions[ses_id].all_meta_data

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions/{ses_id}/scans",  response_model_exclude_unset=True, 
            response_model_exclude_none=True, tags=["RESTAPI"])
async def get_session_scans(ds_id:int, sub_id:str, ses_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return [s.all_meta_data for s in ds.subjects[sub_id].sessions[ses_id].scans]


def short_fname(fname):
    return os.path.split(str(fname))[-1]


@router.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse)
async def session_get_scan_file(request: Request, ds_id:int, s_id:str, ses_id:str, scan_id:str, fname:str, session: Session = Depends(models.get_db)):

    scans = await get_subject_scans(ds_id, s_id, session)
    scan = [s for s in scans if s.name==scan_id][0]
    file_path = [f for f in scan.files if short_fname(f)==fname][0]
    
    if fname.endswith('.gz'):
        import gzip
        import shutil
        tmp_dir = tempfile.mkdtemp()
        unzipped_file_path = os.path.join(tmp_dir, fname[:-3])  # Remove .gz extension
        with gzip.open(file_path, 'rb') as f_in:
            with open(unzipped_file_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return unzipped_file_path

    return file_path


@router.get("/dataset/{ds_id}/subject/{s_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse)
async def subject_get_scan_file(request: Request, ds_id:int, s_id:str, scan_id:str, fname:str, session: Session = Depends(models.get_db)):
    subject = await get_subject(ds_id, s_id, session)
    scan = [s for s in subject.scans.values() if s.name==scan_id][0]
    file_path = [f for f in scan.files if short_fname(f)==fname][0]
    
    if fname.endswith('.gz'):
        import gzip
        import shutil
        tmp_dir = tempfile.mkdtemp()
        unzipped_file_path = os.path.join(tmp_dir, fname[:-3])  # Remove .gz extension
        with gzip.open(file_path, 'rb') as f_in:
            with open(unzipped_file_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return unzipped_file_path

    return file_path
