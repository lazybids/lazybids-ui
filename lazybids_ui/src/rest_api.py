from typing import Optional, Union, List, Dict
from fastapi import APIRouter, Request, Header, Form, UploadFile, Depends
from fastapi.responses import FileResponse, JSONResponse
import lazybids
from . import models
from .models import get_ds, engine
import tempfile
import os
import shutil
from sqlmodel import Session, select
import asyncio

router = APIRouter(prefix="/api")

@router.get("/datasets", tags=["RESTAPI"])
async def get_datasets(session: Session = Depends(models.get_db)):
    session.expire_all()
    statement = select(models.Dataset)
    datasets = session.exec(statement).all()
    return datasets

@router.get("/dataset/{ds_id}", response_model=lazybids.Dataset,
            response_model_exclude_none=True, response_model_exclude=["scans", "subjects", "sessions"], tags=["RESTAPI"])
async def get_dataset(ds_id:int, session: Session = Depends(models.get_db)):
    with Session(engine) as session:
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()     
    ds = get_ds(dataset.folder)
    return ds

@router.delete("/dataset/{ds_id}", tags=["RESTAPI"])
async def delete_dataset(ds_id:int, session: Session = Depends(models.get_db)):
    with Session(engine) as session:
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()     
    shutil.rmtree(dataset.folder)
    session.delete(dataset)
    session.commit()
    return JSONResponse(status_code=200, content={"status": "success"})

@router.get("/dataset/{ds_id}/subjects", response_model=Dict[str, lazybids.Subject],
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude={"__all__":["sessions", "scans"]})
async def get_subjects(ds_id:int, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects

@router.get("/dataset/{ds_id}/subjects/{sub_id}", response_model=lazybids.Subject,
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude=["sessions", "scans"])
async def get_subject(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id]

@router.get("/dataset/{ds_id}/subjects/{sub_id}/scans", response_model=Dict[str, lazybids.Scan],
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude={"__all__":["table"]})
async def get_subject_scans(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].scans

@router.get("/dataset/{ds_id}/subjects/{sub_id}/scans/{scan_id}", response_model=lazybids.Scan,
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude=["table"])
async def get_subject_scan(ds_id:int, sub_id:str, scan_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].scans[scan_id]


@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions", response_model=Dict[str, lazybids.Session],
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude={"__all__":"scans"})
async def get_sessions(ds_id:int, sub_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].sessions

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions/{ses_id}", response_model=lazybids.Session,
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude=["scans"])
async def get_session(ds_id:int, sub_id:str, ses_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].sessions[ses_id]

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions/{ses_id}/scans",  response_model=Dict[str, lazybids.Scan],
            response_model_exclude_none=True, tags=["RESTAPI"],  response_model_exclude={"__all__":["table"]})
async def get_session_scans(ds_id:int, sub_id:str, ses_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    return ds.subjects[sub_id].sessions[ses_id].scans

@router.get("/dataset/{ds_id}/subjects/{sub_id}/sessions/{ses_id}/scans/{scan_id}", response_model=lazybids.Scan, 
            response_model_exclude_none=True, tags=["RESTAPI"], response_model_exclude=["table"])
async def get_session_scan(ds_id:int, sub_id:str, ses_id:str, scan_id:str, session: Session = Depends(models.get_db)):
    ds = await get_dataset(ds_id, session)
    scan = ds.subjects[sub_id].sessions[ses_id].scans[scan_id]
    return scan



def short_fname(fname):
    return os.path.split(str(fname))[-1]

@router.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse, tags=["RESTAPI"])
async def session_get_scan_file(request: Request, ds_id:int, s_id:str, ses_id:str, scan_id:str, fname:str, session: Session = Depends(models.get_db)):
    scans = await get_session_scans(ds_id, s_id, ses_id, session)
    scan = scans[scan_id]
    try:
        file_path = [f for f in scan.files+scan.metadata_files if short_fname(f)==fname][0]
    except IndexError:
        return JSONResponse(status_code=404, content={"status": "error", "message": "File not found"})

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


@router.get("/dataset/{ds_id}/subject/{s_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse, tags=["RESTAPI"])
async def subject_get_scan_file(request: Request, ds_id:int, s_id:str, scan_id:str, fname:str, session: Session = Depends(models.get_db)):
    scans = await get_subject_scans(ds_id, s_id, session)
    scan = scans[scan_id]
    try:
        file_path = [f for f in scan.files+scan.metadata_files if short_fname(f)==fname][0]
    except IndexError:
        return JSONResponse(status_code=404, content={"status": "error", "message": "File not found"})
    
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

