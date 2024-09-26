import html 
import shutil
import tempfile
from pathlib import Path
import os
from PIL import Image
from py7zr import unpack_7zarchive
shutil.register_unpack_format('7zip', ['.7z'], unpack_7zarchive)
from typing import Optional, Union
from fastapi import FastAPI, Request, Header, Form, UploadFile, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import lazybids
from dotenv import load_dotenv, dotenv_values 
# loading variables from .env file
load_dotenv()

import pandas as pd
from typing import List
import functools

import asyncio

from src import models, worker

import datetime
from sqlmodel import Field, Session, SQLModel, create_engine, select

import hashlib

from pretty_html_table import build_table

from src.models import get_db, engine, get_ds
from src import rest_api

from scalar_fastapi import get_scalar_api_reference
from fastapi import FastAPI

tags_metadata = [
    {
        "name": "RESTAPI",
        "description": "API to interact with the datasets.",
        "externalDocs": {
            "description": "LazyBIDS external docs",
            "url": "https://github.com/roelant001/lazybids",
        },
    },
    {
        "name": "HTML",
        "description": "'API' to interact with the web interface, using HTML and HTMX.",
        "externalDocs": {
            "description": "HTML external docs",
            "url": "https://htmx.org/",
        },
    },
]

app = FastAPI(openapi_tags=tags_metadata)


app.include_router(rest_api.router)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

from fastapi.middleware.cors import CORSMiddleware
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )

async def error(request, e):
    return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )

@app.get("/", response_class=HTMLResponse, tags=["HTML"])
@app.get("/index/{str}", response_class=HTMLResponse, tags=["HTML"])
@app.get("/index/{str}/{str2}", response_class=HTMLResponse, tags=["HTML"])
async def root(request: Request, url:str='', url2:str=''):
    if not(url):
        context = {'mainViewURL':'/datasets'}
    elif not(url2):
        context = {'mainViewURL':f'/{url}'}        
    else:
        context = {'mainViewURL':f'/{url}/{url2}'}     
    context['request'] = request
    return templates.TemplateResponse("root.html", context)


@app.get("/datasets", tags=["HTML"])
async def datasets(request: Request, session: Session = Depends(get_db)):
    context = {'datasets':await rest_api.get_datasets(session), 'request':request}
    return templates.TemplateResponse("components/datasets.html", context)

@app.get("/dataset_card/{ds_id}", tags=["HTML"])
def dataset_card(request: Request, ds_id:int,session: Session = Depends(get_db)):
    statement = select(models.Dataset).where(models.Dataset.id==ds_id)
    dataset = session.exec(statement).first()
    if dataset.taskID:
        if dataset.state in ['SUCCESS','FAILURE']:
            print('ready')
        else:
            task = worker.openneuro_download.AsyncResult(dataset.taskID)
            dataset.state = task.state
            session.add(dataset)
            session.commit()
    if not(dataset.taskID) and dataset.state != 'SUCCESS':
            dataset.state = 'SUCCESS'
            session.add(dataset)
            session.commit()

     
    folder = Path(dataset.folder)
    size = f"{sum(f.stat().st_size for f in folder.glob('**/*') if f.is_file())/2**30:.2f}"
    context = {'dataset':dataset, 'size':size, 'request':request}
        
    return templates.TemplateResponse("components/dataset_card.html", context)


@app.post("/datasets/create", response_class=HTMLResponse, tags=["HTML"])
async def create_dataset(request: Request, 
                         name: str = Form(...), 
                         folder: Optional[str] = Form(None), 
                         DatabaseID: Optional[str] = Form(None),
                         Version: Optional[str] = Form(None), 
                         CopyFolder: Optional[str] = Form(None),
                         icon: Union[UploadFile, None] = None, 
                         zipfile:Union[UploadFile, None] = None,
                         session: Session = Depends(get_db)):
                         
    tmp_zipfile_path = None
    my_icon = None
    if zipfile:
        tmp_zipfile_path = os.path.join(tempfile.mkdtemp(), zipfile.filename)
        with open(tmp_zipfile_path, "wb+") as file_object:
            shutil.copyfileobj(zipfile.file, file_object)    
    if icon:
        tmp_icon_path = os.path.join(tempfile.mkdtemp(), icon.filename)
        with open(tmp_icon_path, "wb+") as file_object:
            shutil.copyfileobj(icon.file, file_object)  
        try:
            im = Image.open(tmp_icon_path)
            im.verify()
            my_icon = tmp_icon_path
            # do stuff
        except IOError:
            os.remove(tmp_icon_path)
            # filename not an image file
            return error(request, 'Icon file not supported')
    print('create dataset create')
    datasetCreation = models.DatasetCreate(name=name,
                                   folder=folder,
                                   DatabaseID=DatabaseID,
                                   Version=Version,
                                   CopyFolder=CopyFolder=='on',
                                   icon=my_icon)
    print('create dataset')
    dataset = datasetCreation.createDataset(zipfile=tmp_zipfile_path)
    
    session.add(dataset)
    session.commit()
    print('return dataset')
    return templates.TemplateResponse("components/redirect_home.html", context = {'request':request})




@app.get("/dataset/{ds_id}", response_class=HTMLResponse, tags=["HTML"])
async def get_dataset(request: Request, ds_id:int):
    if not('hx-request' in request.headers.keys()):
        context = {"request": request,'mainViewURL':f"/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context )
    else:
        dataset = await rest_api.get_dataset(ds_id)
        
        context = {"request": request,'dataset_id':ds_id,'dataset':dataset,'meta_data':dataset.all_meta_data}
        return templates.TemplateResponse("components/dataset_view.html", context=context )

def to_subject_url(subject_id, ds_id ):
    return f"<a class='btn btn-outline btn-primary btn-xs' href='/dataset/{ds_id}/subject/{subject_id}' hx-target='#main_view'>{subject_id}</a>"

def to_session_url(subject_id,session_id, ds_id ):
    return f"<a class='btn btn-outline btn-secondary btn-xs' href='/dataset/{ds_id}/subject/{subject_id}/session/{session_id}' hx-target='#main_view'>{session_id}</a>"



@app.get("/dataset/{ds_id}/subjects", response_class=HTMLResponse, tags=["HTML"])
async def get_subjects(request: Request, ds_id:int, session: Session = Depends(get_db)):
    if not('hx-request' in request.headers.keys()):
        context = {"request": request,'mainViewURL':f"/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context )
    else:
        
        subjects = await rest_api.get_subjects(ds_id)
        df = pd.DataFrame(subjects)
        columns = df.columns.tolist()
        if 'session_id' in df.columns.tolist():
            df['session_id'] = df[['participant_id', 'session_id']].apply(lambda x: to_session_url(x['participant_id'], x['session_id'], ds_id), axis=1)
            columns.remove('session_id')
        df['participant_id'] = df['participant_id'].apply(to_subject_url, ds_id=ds_id)
        columns.remove('participant_id')
            
        context = {
                   'df' : df.astype(str).to_json(orient='records', default_handler=str),
                   'columns': columns,
                    'ds_id': ds_id,
                    's_id': '',
                    'ses_id': '',
                    'request':request
                   }
        return templates.TemplateResponse("components/table.html", context)  


@app.get("/dataset/{ds_id}/subject/{s_id}", response_class=HTMLResponse, tags=["HTML"])
async def get_subject(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    #try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}"}
            return templates.TemplateResponse("root.html", context )
        else:
            dataset = await rest_api.get_dataset(ds_id)
            subjects = await rest_api.get_subjects(ds_id, session)
            subject = lazybids.Subject([s for s in subjects if s.participant_id==s_id][0])
                
        return templates.TemplateResponse("components/subject_view.html", 
                                          context = {"request": request,
                                                     'dataset':dataset,
                                                     'meta_data':subject} )
    
    # except Exception as e:
    #     return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )



@app.get("/dataset/{ds_id}/subject/{s_id}/sessions", response_class=HTMLResponse, tags=["HTML"])
async def get_sessions(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/sessions"}
            return templates.TemplateResponse("root.html", context )
        else:
            subject = await rest_api.get_subject(ds_id, s_id)
            df = pd.DataFrame([s.all_meta_data for s in subject.sessions.values()])
            if not len(df)>0:
                return ''

            if 'session_id' in df.columns.tolist():
                df['participant_id'] = subject.participant_id
                df['session_id'] = df[['participant_id', 'session_id']].apply(lambda x: to_session_url(x['participant_id'], x['session_id'], ds_id), axis=1)
            columns = df.columns.tolist()
            columns.remove('participant_id')
            columns.remove('session_id')


            
            context = {
                    'df' : df.astype(str).to_json(orient='records', default_handler=str),
                    'columns': columns,
                    'ds_id': ds_id,
                    's_id': s_id,
                    'ses_id': '',
                    'scans': False,
                    'request':request
                    }
            return templates.TemplateResponse("components/table.html", context) 
    
    except Exception as e:
        return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )



@app.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}", response_class=HTMLResponse, tags=["HTML"])
async def get_session(request: Request, ds_id:int, s_id:str, ses_id:str, session: Session = Depends(get_db)):

    if not('hx-request' in request.headers.keys()):
        context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{ses_id}"}
        return templates.TemplateResponse("root.html", context )
    else:
        
        dataset = await rest_api.get_dataset(ds_id)
        ses = await rest_api.get_session(ds_id, s_id, ses_id)
        ses.participant_id = s_id
        
        return templates.TemplateResponse("components/session_view.html", 
                                        context = {"request": request,
                                                    'dataset':dataset,
                                                    'meta_data':ses.all_meta_data} )


    
@app.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans", response_class=HTMLResponse, tags=["HTML"])
async def get_scans(request: Request, ds_id:int, s_id:str, ses_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            ses = await rest_api.get_session(ds_id, s_id, ses_id)
            df = pd.DataFrame([s.all_meta_data for s in ses.scans.values()])     
            if not(len(df)>0):
                return ''       
            columns = df.columns.tolist()
            
            if 'name' in columns:
                columns.remove('name')
           
            context = {
                    "request": request,
                    'df' : df.astype(str).to_json(orient='records', default_handler=str),
                    'ds_id':ds_id,
                    's_id': s_id,
                    'ses_id': ses_id,
                    'columns': columns,
                    'scans': True,
                    }
            return templates.TemplateResponse("components/table.html", context ) 
    

@app.get("/dataset/{ds_id}/subject/{s_id}/scans", response_class=HTMLResponse, tags=["HTML"])
async def get_scans(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            subject = await rest_api.get_subject(ds_id, s_id)
            
            df = pd.DataFrame([s.all_meta_data for s in subject.scans.values()])
            if not(len(df>0)):
                return 'No scans found for this subject'       
            
            columns = df.columns.tolist()
            
            if 'name' in columns:
                columns.remove('name')


            
            context = {
                    "request": request,
                    'df' : df.astype(str).to_json(orient='records', default_handler=str),
                    'ds_id':ds_id,
                    's_id': s_id,
                    'ses_id': '',
                    'columns': columns,
                    'scans': True,
                    }
            return templates.TemplateResponse("components/table.html", context ) 




@app.get("/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans_view", response_class=HTMLResponse, tags=["HTML"])
async def get_scans_view(request: Request, ds_id:int, s_id:str, ses_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{ses_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            ses = await rest_api.get_session(ds_id, s_id, ses_id)
            scans = [{'name': scan.name, 'fname':rest_api.short_fname(scan.files[0])} for scan in ses.scans.values() if scan.files]
            tables = [{'name': scan.name, 'table':build_table(scan.table, 'grey_dark')} for scan in ses.scans.values() if (type(scan.table) == pd.DataFrame)]

            
            context = {
                    'ds_id':ds_id,
                    's_id': s_id,
                    'ses_id': ses_id,
                    'scans': scans,
                    'tables':tables,
                    'request':request
                    }
            return templates.TemplateResponse("components/scans.html", context) 
    

@app.get("/dataset/{ds_id}/subject/{s_id}/scans_view", response_class=HTMLResponse, tags=["HTML"])
async def get_scans_view(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            subject = await rest_api.get_subject(ds_id, s_id)
            
            
            scans = [{'name': scan.name, 'fname':rest_api.short_fname(scan.files[0])} for scan in subject.scans.values()]
            tables = [{'name': scan.name, 'table':build_table(scan.table, 'grey_dark')} for scan in subject.scans.values() if (type(scan.table) == pd.DataFrame)]

            
            context = {
                    'ds_id':ds_id,
                    's_id': s_id,
                    'scans': scans,
                    'tables':tables,
                    'request':request
                    }
            return templates.TemplateResponse("components/scans.html", context) 
    