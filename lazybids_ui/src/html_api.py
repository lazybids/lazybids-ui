from fastapi import APIRouter, Request, Depends, Form, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional, Union
from . import models, rest_api
import pandas as pd
from pretty_html_table import build_table
import os
import shutil
import tempfile
import uuid
from PIL import Image
from pathlib import Path 

router = APIRouter(prefix="/html", tags=["HTML"])

templates = Jinja2Templates(directory="templates")

# Helper functions
def to_subject_url(subject_id, ds_id):
    return f"<a class='btn btn-outline btn-primary btn-xs' href='/html/dataset/{ds_id}/subject/{subject_id}' hx-target='#main_view'>{subject_id}</a>"

def to_session_url(subject_id, session_id, ds_id):
    return f"<a class='btn btn-outline btn-secondary btn-xs' href='/html/dataset/{ds_id}/subject/{subject_id}/session/{session_id}' hx-target='#main_view'>{session_id}</a>"

def to_file_url(ds_id, s_id, ses_id, scan_id, file_names):
    output = ''
    for file_name in file_names:
        file_name = os.path.split(file_name)[-1]
        if ses_id:
            output += f"""<div class="flex mr-6"><a class='btn btn-outline btn-accent btn-xs' href='/api/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scan/{scan_id}/files/{file_name}'>
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                {file_name}
            </a></div>"""
        else:
            output += f"""<div class="flex items-center mr-6"><a class='btn btn-outline btn-accent btn-xs' href='/api/dataset/{ds_id}/subject/{s_id}/scan/{scan_id}/files/{file_name}'>
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                {file_name}
            </a></div>"""
    return output

async def error(request, e):
    return templates.TemplateResponse("components/error.html", context={"request": request, 'error': e})

# Routes
@router.get("/datasets", response_class=HTMLResponse)
async def datasets(request: Request, session: Session = Depends(models.get_db)):
    # Refresh the session to ensure we have the latest data
    session.expire_all()
    context = {'datasets': await rest_api.get_datasets(session), 'request': request}
    return templates.TemplateResponse("components/datasets.html", context)

@router.get("/dataset_card/{ds_id}", response_class=HTMLResponse)
async def dataset_card(request: Request, ds_id: int, session: Session = Depends(models.get_db)):
    statement = select(models.Dataset).where(models.Dataset.id == ds_id)
    dataset = session.exec(statement).first()
    if not dataset:
        return None
    if dataset.taskID:
        if dataset.state in [models.JobStatus.SUCCESS, models.JobStatus.FAILURE]:
            print('ready')
        else:
            task = await models.get_job_status(dataset.taskID)
            dataset.state = task['status']
            session.add(dataset)
            session.commit()
    if not dataset.taskID and dataset.state != models.JobStatus.SUCCESS:
        dataset.state = models.JobStatus.SUCCESS
        session.add(dataset)
        session.commit()
    folder = Path(dataset.folder)
    size = f"{sum(f.stat().st_size for f in folder.glob('**/*') if f.is_file())/2**30:.2f}"
    context = {'dataset': dataset, 'ds_id':ds_id, 'size':size, 'request':request}

    return templates.TemplateResponse("components/dataset_card.html", context)

@router.post("/datasets/create", response_class=HTMLResponse)
async def create_dataset(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    folder: Optional[str] = Form(None),
    DatabaseID: Optional[str] = Form(None),
    Version: Optional[str] = Form(None),
    CopyFolder: Optional[str] = Form(None),
    icon: Union[UploadFile, None] = None,
    zipfile: Union[UploadFile, None] = None,
    session: Session = Depends(models.get_db)
):
    tmp_zipfile_path = None
    my_icon = None
    if zipfile:
        tmp_zipfile_path = os.path.join(tempfile.mkdtemp(), zipfile.filename)
        with open(tmp_zipfile_path, "wb+") as file_object:
            shutil.copyfileobj(zipfile.file, file_object)    
    if icon:
        print(icon)
        tmp_icon_path = os.path.join(tempfile.mkdtemp(), icon.filename)
        with open(tmp_icon_path, "wb+") as file_object:
            shutil.copyfileobj(icon.file, file_object)  
        try:
            im = Image.open(tmp_icon_path)
            im.verify()
            my_icon = tmp_icon_path
        except IOError:
            os.remove(tmp_icon_path)
            return error(request, 'Icon file not supported')
    else:
        print('no icon')
    print('create dataset create')
    datasetCreation = models.DatasetCreate(
        name=name,
        folder=folder,
        DatabaseID=DatabaseID,
        Version=Version,
        CopyFolder=CopyFolder == 'on',
        icon=my_icon
    )
    print('create dataset')
    dataset = datasetCreation.createDataset(zipfile=tmp_zipfile_path)
    
    session.add(dataset)
    session.commit()

    if DatabaseID:
        job_id = str(uuid.uuid4())
        dataset.taskID = job_id
        dataset.state = models.JobStatus.PENDING
        session.add(dataset)
        session.commit()

        background_tasks.add_task(
            models.start_openneuro_download,
            background_tasks,
            DatabaseID,
            Version or 'latest',
            dataset.folder,
            job_id
        )

    print('return dataset')
    return templates.TemplateResponse("components/redirect_home.html", context={'request': request})

@router.get("/dataset/{ds_id}", response_class=HTMLResponse)
async def get_dataset(request: Request, ds_id: int, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context)
    else:
        dataset = await rest_api.get_dataset(ds_id)
        statement = select(models.Dataset).where(models.Dataset.id == ds_id)
        ds = session.exec(statement).first()
        context = {"request": request, 'dataset_id': ds_id, 'dataset': dataset, 'meta_data': dataset.all_meta_data, 'ds': ds}
        return templates.TemplateResponse("components/dataset_view.html", context=context)

@router.delete("/dataset/{ds_id}", response_class=HTMLResponse)
async def delete_dataset(request: Request, ds_id: int, session: Session = Depends(models.get_db)):
    await rest_api.delete_dataset(ds_id, session)
    return templates.TemplateResponse("components/redirect_home.html", context={'request': request})

@router.get("/dataset/{ds_id}/subjects", response_class=HTMLResponse)
async def get_subjects(request: Request, ds_id: int, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context)
    else:
        subjects = await rest_api.get_subjects(ds_id)
        df = pd.DataFrame([subject.all_meta_data for subject in subjects.values()])
        columns = df.columns.tolist()
        if ('session_id' in df.columns.tolist()) and df['session_id'].any():
            df['session_id'] = df[['participant_id', 'session_id']].apply(lambda x: to_session_url(x['participant_id'], x['session_id'], ds_id), axis=1)
            columns.remove('session_id')
        df['participant_id'] = df['participant_id'].apply(to_subject_url, ds_id=ds_id)
        columns.remove('participant_id')
            
        context = {
            'df': df.astype(str).to_json(orient='records', default_handler=str),
            'columns': columns,
            'show_sessions': (('session_id' in df.columns.tolist()) and df['session_id'].any()),
            'ds_id': ds_id,
            's_id': '',
            'ses_id': '',
            'request': request
        }
        return templates.TemplateResponse("components/table.html", context)

@router.get("/dataset/{ds_id}/subject/{s_id}", response_class=HTMLResponse)
async def get_subject(request: Request, ds_id: int, s_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}"}
        return templates.TemplateResponse("root.html", context)
    else:
        dataset = await rest_api.get_dataset(ds_id)
        subjects = await rest_api.get_subjects(ds_id, session)
        subject = [s for s in subjects.values() if s.participant_id == s_id][0]
        return templates.TemplateResponse("components/subject_view.html", 
                                          context={"request": request,
                                                   'dataset': dataset,
                                                   'ds_id': ds_id,
                                                   'meta_data': subject.all_meta_data})

@router.get("/dataset/{ds_id}/subject/{s_id}/sessions", response_class=HTMLResponse)
async def get_sessions(request: Request, ds_id: int, s_id: str, session: Session = Depends(models.get_db)):
    try:
        if 'hx-request' not in request.headers.keys():
            context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}/sessions"}
            return templates.TemplateResponse("root.html", context)
        else:
            subject = await rest_api.get_subject(ds_id, s_id)
            df = pd.DataFrame([s.all_meta_data for s in subject.sessions.values()])
            if not len(df) > 0:
                return 'No sessions found for this subject'

            if 'session_id' in df.columns.tolist():
                df['participant_id'] = subject.participant_id
                df['session_id'] = df[['participant_id', 'session_id']].apply(lambda x: to_session_url(x['participant_id'], x['session_id'], ds_id), axis=1)
                df['participant_id'] = df['participant_id'].apply(to_subject_url, ds_id=ds_id)
            columns = df.columns.tolist()
            columns.remove('participant_id')
            columns.remove('session_id')

            context = {
                'df': df.astype(str).to_json(orient='records', default_handler=str),
                'columns': columns,
                'ds_id': ds_id,
                's_id': s_id,
                'ses_id': '',
                'show_sessions': (('session_id' in df.columns.tolist()) and df['session_id'].any()),
                'scans': False,
                'request': request
            }
            return templates.TemplateResponse("components/table.html", context)
    
    except Exception as e:
        return templates.TemplateResponse("components/error.html", context={"request": request, 'error': e})

@router.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}", response_class=HTMLResponse)
async def get_session(request: Request, ds_id: int, s_id: str, ses_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}/session/{ses_id}"}
        return templates.TemplateResponse("root.html", context)
    else:
        dataset = await rest_api.get_dataset(ds_id)
        ses = await rest_api.get_session(ds_id, s_id, ses_id)
        ses.participant_id = s_id
        
        return templates.TemplateResponse("components/session_view.html", 
                                          context={"request": request,
                                                   'dataset': dataset,
                                                   'ds_id': ds_id,
                                                   'meta_data': ses.all_meta_data})

@router.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans", response_class=HTMLResponse)
async def get_scans(request: Request, ds_id: int, s_id: str, ses_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans"}
        return templates.TemplateResponse("root.html", context)
    else:
        ses = await rest_api.get_session(ds_id, s_id, ses_id)
        df = pd.DataFrame([s.all_meta_data for s in ses.scans.values()])     
        if not len(df) > 0:
            return ''       
        columns = df.columns.tolist()
        if 'name' in columns:
            columns.remove('name')
        if 'table' in columns:
            columns.remove('table')
        if 'participant_id' in columns:
            columns.remove('participant_id')
        if 'session_id' in columns:
            columns.remove('session_id')
        if 'files' in columns:
            df['files'] = df[['files', 'name']].apply(lambda x: to_file_url(ds_id, s_id, ses_id, x['name'], x['files']), axis=1)
            columns.remove('files')
        if 'metadata_files' in columns:
            df['metadata_files'] = df[['metadata_files', 'name']].apply(lambda x: to_file_url(ds_id, s_id, ses_id, x['name'], x['metadata_files']), axis=1)
            columns.remove('metadata_files')
        context = {
            "request": request,
            'df': df.astype(str).to_json(orient='records', default_handler=str),
            'ds_id': ds_id,
            's_id': s_id,
            'ses_id': ses_id,
            'show_sessions': (('session_id' in df.columns.tolist()) and df['session_id'].any()),
            'columns': columns,
            'scans': True,
        }
        return templates.TemplateResponse("components/table.html", context)

@router.get("/dataset/{ds_id}/subject/{s_id}/scans", response_class=HTMLResponse)
async def get_scans(request: Request, ds_id: int, s_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/scans"}
        return templates.TemplateResponse("root.html", context)
    else:
        subject = await rest_api.get_subject(ds_id, s_id)
        
        df = pd.DataFrame([s.all_meta_data for s in subject.scans.values()])
        if not len(subject.scans) > 0 or not len(df) > 0:
            return 'No scans found for this subject'       
        
        columns = df.columns.tolist()
        
        if 'name' in columns:
            columns.remove('name')
        if 'table' in columns:
            columns.remove('table')
        if 'participant_id' in columns:
            columns.remove('participant_id')
        if 'session_id' in columns:
            columns.remove('session_id')
        if 'files' in columns:
            df['files'] = df[['files', 'name']].apply(lambda x: to_file_url(ds_id, s_id, ses_id, x['name'], x['files']), axis=1)
            columns.remove('files')
        if 'metadata_files' in columns:
            df['metadata_files'] = df[['metadata_files', 'name']].apply(lambda x: to_file_url(ds_id, s_id, ses_id, x['name'], x['metadata_files']), axis=1)
            columns.remove('metadata_files')

        context = {
            "request": request,
            'df': df.astype(str).to_json(orient='records', default_handler=str),
            'ds_id': ds_id,
            's_id': s_id,
            'ses_id': '',
            'columns': columns,
            'show_sessions': (('session_id' in df.columns.tolist()) and df['session_id'].any()),
            'scans': True,
        }
        return templates.TemplateResponse("components/table.html", context)

@router.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans_view", response_class=HTMLResponse)
async def get_scans_view(request: Request, ds_id: int, s_id: str, ses_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans"}
        return templates.TemplateResponse("root.html", context)
    else:
        ses = await rest_api.get_session(ds_id, s_id, ses_id)
        image_extensions = [
            ".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"
        ]
        scans = [{'name': scan.name, 'fname': rest_api.short_fname(scan.files[0])} for scan in ses.scans.values() if scan.files and not(os.path.splitext(scan.files[0])[1] in image_extensions)]
        images = [{'name': scan.name, 'fname': rest_api.short_fname(scan.files[0])} for scan in ses.scans.values() if scan.files and os.path.splitext(scan.files[0])[1] in image_extensions]
        tables = [{'name': scan.name, 'table': build_table(scan.table, 'grey_dark')} for scan in ses.scans.values() if not(scan.table.empty)]

        context = {
            'ds_id': ds_id,
            's_id': s_id,
            'ses_id': ses_id,
            'scans': scans,
            'images': images,
            'tables': tables,
            'request': request
        }
        return templates.TemplateResponse("components/scans.html", context)

@router.get("/dataset/{ds_id}/subject/{s_id}/scans_view", response_class=HTMLResponse)
async def get_scans_view(request: Request, ds_id: int, s_id: str, session: Session = Depends(models.get_db)):
    if 'hx-request' not in request.headers.keys():
        context = {"request": request, 'mainViewURL': f"/html/dataset/{ds_id}/subject/{s_id}/scans"}
        return templates.TemplateResponse("root.html", context)
    else:
        subject = await rest_api.get_subject(ds_id, s_id)
        image_extensions = [
            ".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"
        ]
        scans = [{'name': scan.name, 'fname': rest_api.short_fname(scan.files[0])} for scan in subject.scans.values() if scan.files and not(os.path.splitext(scan.files[0])[1] in image_extensions)]
        images = [{'name': scan.name, 'fname': rest_api.short_fname(scan.files[0])} for scan in subject.scans.values() if scan.files and os.path.splitext(scan.files[0])[1] in image_extensions]
        tables = [{'name': scan.name, 'table': build_table(scan.table, 'grey_dark')} for scan in subject.scans.values() if not(scan.table.empty)]

        context = {
            'ds_id': ds_id,
            's_id': s_id,
            'scans': scans,
            'images': images,
            'tables': tables,
            'request': request
        }
        return templates.TemplateResponse("components/scans.html", context)

@router.get("/dataset/{ds_id}/edit", response_class=HTMLResponse)
async def edit_dataset_form(request: Request, ds_id: int, session: Session = Depends(models.get_db)):
    try:
        statement = select(models.Dataset).where(models.Dataset.id == ds_id)
        dataset = session.exec(statement).first()
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        context = {
            "request": request,
            "dataset": dataset,
        }

        return templates.TemplateResponse("components/edit_dataset.html", context)
    
    except Exception as e:
        return templates.TemplateResponse("components/error.html", context={"request": request, "error": str(e)})
