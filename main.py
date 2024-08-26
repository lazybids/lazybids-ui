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
from fasthx import Jinja

jinja = Jinja(Jinja2Templates("templates"))
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

def get_db():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()




app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
engine = create_engine("sqlite:///database.db")
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


async def error(request, e):
    return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )

@app.get("/", response_class=HTMLResponse)
@app.get("/index/{str}", response_class=HTMLResponse)
@app.get("/index/{str}/{str2}", response_class=HTMLResponse)
@jinja.page("root.html")
async def root(url:str='', url2:str=''):
    if not(url):
        context = {'mainViewURL':'/datasets'}
    elif not(url2):
        context = {'mainViewURL':f'/{url}'}        
    else:
        context = {'mainViewURL':f'/{url}/{url2}'}     
    return context


@app.get("/datasets")
@jinja.hx("components/datasets.html")
async def datasets(session: Session = Depends(get_db)):
    statement = select(models.Dataset)
    datasets = session.exec(statement).all()
    # for dataset in datasets:
    #     if dataset.taskID:
    #         if dataset.state in ['SUCCESS','FAILURE']:
    #             continue
    #         else:
    #             task = worker.openneuro_download.AsyncResult(dataset.taskID)
    #             dataset.state = task.state
    #             session.add(dataset)
    #             session.commit()
    #     if not(dataset.taskID) and dataset.state != 'SUCCESS':
    #             dataset.state = 'SUCCESS'
    #             session.add(dataset)
    #             session.commit()

    context = {'datasets':datasets}
    return context

@app.get("/dataset_card/{ds_id}")
@jinja.hx("components/dataset_card.html", no_data=True)
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
    context = {'dataset':dataset, 'size':size}
        
    return context


@app.post("/datasets/create", response_class=HTMLResponse)
@jinja.hx("components/redirect_home.html")
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
    return


@functools.lru_cache(maxsize=12)
def get_ds(folder):
    ds = lazybids.Dataset.from_folder(folder, load_scans_in_memory=False)
    return ds

@app.get("/dataset/{ds_id}", response_class=HTMLResponse)
async def get_dataset(request: Request, ds_id:int):
    if not('hx-request' in request.headers.keys()):
        context = {"request": request,'mainViewURL':f"/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context )
    else:
        with Session(engine) as session:
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
        try:
            ds = get_ds(dataset.folder)
        except Exception as e:
            return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )
        
        return templates.TemplateResponse("components/dataset_view.html", context = {"request": request,'dataset':dataset,'meta_data':ds.all_meta_data} )

def to_subject_url(subject_id, ds_id ):
    return f"<a class='btn btn-outline btn-primary btn-xs' href='/dataset/{ds_id}/subject/{subject_id}' hx-target='#main_view'>{subject_id}</a>"

def to_session_url(subject_id,session_id, ds_id ):
    return f"<a class='btn btn-outline btn-secondary btn-xs' href='/dataset/{ds_id}/subject/{subject_id}/session/{session_id}' hx-target='#main_view'>{session_id}</a>"



@app.get("/dataset/{ds_id}/subjects", response_class=HTMLResponse)
@jinja.hx("components/table.html")
async def get_subjects(request: Request, ds_id:int, session: Session = Depends(get_db)):
    if not('hx-request' in request.headers.keys()):
        context = {"request": request,'mainViewURL':f"/dataset/{ds_id}"}
        return templates.TemplateResponse("root.html", context )
    else:
        
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()
        try:
            ds = get_ds(dataset.folder)
            df = pd.DataFrame([s.all_meta_data for s in ds.subjects])
            columns = df.columns.tolist()
            if 'session_id' in df.columns.tolist():
                df['session_id'] = df[['participant_id', 'session_id']].apply(lambda x: to_session_url(x['participant_id'], x['session_id'], ds_id), axis=1)
                columns.remove('session_id')
            df['participant_id'] = df['participant_id'].apply(to_subject_url, ds_id=ds_id)
            columns.remove('participant_id')
            


        except Exception as e:
            return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )
        
        context = {
                   'df' : df.astype(str).to_json(orient='records', default_handler=str),
                   'columns': columns,
                    'ds_id': ds_id,
                    's_id': '',
                    'exp_id': '',
                   }
        return context 


@app.get("/dataset/{ds_id}/subject/{s_id}", response_class=HTMLResponse)
#@jinja.hx("components/subject_view.html")
async def get_subject(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    #try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}"}
            return templates.TemplateResponse("root.html", context )
        else:
            with Session(engine) as session:
                statement = select(models.Dataset).where(models.Dataset.id==ds_id)
                dataset = session.exec(statement).first()
                ds = get_ds(dataset.folder)
                subject = [s for s in ds.subjects if s.participant_id==s_id][0]
                

                


        return templates.TemplateResponse("components/subject_view.html", 
                                          context = {"request": request,
                                                     'dataset':dataset,
                                                     'meta_data':subject.all_meta_data} )
    
    # except Exception as e:
    #     return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )



@app.get("/dataset/{ds_id}/subject/{s_id}/sessions", response_class=HTMLResponse)
@jinja.hx("components/table.html")
async def get_sessions(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/sessions"}
            return templates.TemplateResponse("root.html", context )
        else:
            
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
        
            ds = get_ds(dataset.folder)
            subject = [s for s in ds.subjects if s.participant_id==s_id][0]
            df = pd.DataFrame([s.all_meta_data for s in subject.experiments])

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
                    'exp_id': '',
                    'scans': False
                    }
            return context 
    
    except Exception as e:
        return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )



@app.get("/dataset/{ds_id}/subject/{s_id}/session/{exp_id}", response_class=HTMLResponse)
#@jinja.hx("components/subject_view.html")
async def get_session(request: Request, ds_id:int, s_id:str, exp_id:str, session: Session = Depends(get_db)):
    #try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{exp_id}"}
            return templates.TemplateResponse("root.html", context )
        else:
            with Session(engine) as session:
                statement = select(models.Dataset).where(models.Dataset.id==ds_id)
                dataset = session.exec(statement).first()
                ds = get_ds(dataset.folder)
                subject = [s for s in ds.subjects if s.participant_id==s_id][0]
                experiment = [e for e in subject.experiments if e.session_id==exp_id][0]
                print(s_id)
                experiment.participant_id = s_id
            

            
            return templates.TemplateResponse("components/experiment_view.html", 
                                            context = {"request": request,
                                                        'dataset':dataset,
                                                        'meta_data':experiment.all_meta_data} )
    
    # except Exception as e:
    #     return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )

    
@app.get("/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans", response_class=HTMLResponse)
@jinja.hx("components/table.html")
async def get_scans(request: Request, ds_id:int, s_id:str, exp_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
            ds = get_ds(dataset.folder)
            print(s_id)
            subject = [s for s in ds.subjects if s.participant_id==s_id][0]
            experiment = [e for e in subject.experiments if e.session_id==exp_id][0]
            df = pd.DataFrame([s.all_meta_data for s in experiment.scans.values()])

            
            columns = df.columns.tolist()
            
            if 'name' in columns:
                columns.remove('name')


            
            context = {
                    'df' : df.astype(str).to_json(orient='records', default_handler=str),
                    'ds_id':ds_id,
                    's_id': s_id,
                    'exp_id': exp_id,
                    'columns': columns,
                    'scans': True,
                    }
            return context 
    

@app.get("/dataset/{ds_id}/subject/{s_id}/scans", response_class=HTMLResponse)
@jinja.hx("components/table.html")
async def get_scans(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
            ds = get_ds(dataset.folder)
            print(s_id)
            subject = [s for s in ds.subjects if s.participant_id==s_id][0]
            
            df = pd.DataFrame([s.all_meta_data for s in subject.scans.values()])

            
            columns = df.columns.tolist()
            
            if 'name' in columns:
                columns.remove('name')


            
            context = {
                    'df' : df.astype(str).to_json(orient='records', default_handler=str),
                    'ds_id':ds_id,
                    's_id': s_id,
                    'exp_id': '',
                    'columns': columns,
                    'scans': True,
                    }
            return context 

def short_fname(fname):
    return os.path.split(str(fname))[-1]

@app.get("/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse)
async def get_scans(request: Request, ds_id:int, s_id:str, exp_id:str, scan_id:str, fname:str, session: Session = Depends(get_db)):

    statement = select(models.Dataset).where(models.Dataset.id==ds_id)
    dataset = session.exec(statement).first()
    ds = get_ds(dataset.folder)
    print(s_id)
    subject = [s for s in ds.subjects if s.participant_id==s_id][0]
    experiment = [e for e in subject.experiments if e.session_id==exp_id][0]
    scan = [s for s in experiment.scans.values() if s.name==scan_id][0]
    

    return [f for f in scan.files if short_fname(f)==fname][0]


@app.get("/dataset/{ds_id}/subject/{s_id}/scan/{scan_id}/files/{fname}", response_class=FileResponse)
async def get_scans(request: Request, ds_id:int, s_id:str, scan_id:str, fname:str, session: Session = Depends(get_db)):

    statement = select(models.Dataset).where(models.Dataset.id==ds_id)
    dataset = session.exec(statement).first()
    ds = get_ds(dataset.folder)
    print(s_id)
    subject = [s for s in ds.subjects if s.participant_id==s_id][0]
    scan = [s for s in subject.scans.values() if s.name==scan_id][0]

    return [f for f in scan.files if short_fname(f)==fname][0]


@app.get("/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans_view", response_class=HTMLResponse)
@jinja.hx("components/scans.html")
async def get_scans(request: Request, ds_id:int, s_id:str, exp_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
            ds = get_ds(dataset.folder)
            print(s_id)
            subject = [s for s in ds.subjects if s.participant_id==s_id][0]
            experiment = [e for e in subject.experiments if e.session_id==exp_id][0]
            scans = [{'name': scan.name, 'fname':short_fname(scan.files[0])} for scan in experiment.scans.values() if scan.files]
            tables = [{'name': scan.name, 'table':build_table(scan.table, 'grey_dark')} for scan in experiment.scans.values() if (type(scan.table) == pd.DataFrame)]

            
            context = {
                    'ds_id':ds_id,
                    's_id': s_id,
                    'exp_id': exp_id,
                    'scans': scans,
                    'tables':tables,
                    }
            return context 
    

@app.get("/dataset/{ds_id}/subject/{s_id}/scans_view", response_class=HTMLResponse)
@jinja.hx("components/scans.html")
async def get_scans(request: Request, ds_id:int, s_id:str, session: Session = Depends(get_db)):
    # try:
        if not('hx-request' in request.headers.keys()):
            context = {"request": request,'mainViewURL':f"/dataset/{ds_id}/subject/{s_id}/session/{exp_id}/scans"}
            return templates.TemplateResponse("root.html", context )
        else:
            
            statement = select(models.Dataset).where(models.Dataset.id==ds_id)
            dataset = session.exec(statement).first()
            ds = get_ds(dataset.folder)
            print(s_id)
            subject = [s for s in ds.subjects if s.participant_id==s_id][0]
            
            scans = [{'name': scan.name, 'fname':short_fname(scan.files[0])} for scan in subject.scans.values()]
            tables = [{'name': scan.name, 'table':build_table(scan.table, 'grey_dark')} for scan in subject.scans.values() if (type(scan.table) == pd.DataFrame)]

            
            context = {
                    'ds_id':ds_id,
                    's_id': s_id,
                    'scans': scans,
                    'tables':tables,
                    }
            return context 
    