import html 
from typing import Optional
from fastapi import FastAPI, Request, Header, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import lazybids


from typing import List

import asyncio

import src.models as models
from src.random_image import generateCharacter
import datetime
from sqlmodel import Field, Session, SQLModel, create_engine, select

import hashlib

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
engine = create_engine("sqlite:///database.db")
templates = Jinja2Templates(directory="templates")




@app.get("/", response_class=HTMLResponse)
async def root(request: Request):

    context = {"request": request,}
    return templates.TemplateResponse("root.html", context )


@app.get("/datasets", response_class=HTMLResponse)
async def datasets(request: Request):
    with Session(engine) as session:
        statement = select(models.Dataset)
        datasets = session.exec(statement).all()
    print(datasets)
    context = {"request": request,'datasets':datasets}
    return templates.TemplateResponse("components/datasets.html", context )

@app.get("/dataset/create", response_class=HTMLResponse)
async def create_dataset(request: Request,):
    with Session(engine) as session:
        example_dataset = models.Dataset(name='test',folder='./example/dataset',icon=generateCharacter())
        session.add(example_dataset)
        session.commit()
    #
    # return datasets(request)


@app.get("/dataset/{ds_id}", response_class=HTMLResponse)
async def get_dataset(request: Request, ds_id:int):
    with Session(engine) as session:
        statement = select(models.Dataset).where(models.Dataset.id==ds_id)
        dataset = session.exec(statement).first()
    try:
        ds = lazybids.Dataset.from_folder(dataset.folder, load_scans_in_memory=False)
    except Exception as e:
        return templates.TemplateResponse("components/error.html", context = {"request": request,'error':e} )

# @app.get("/search", response_class=HTMLResponse)
# async def root(request: Request, search_text: str):

#     # Initialize beanie with the Product document class
#     my_search = search_text
#     res = search_youtube('Best '+str(my_search)+' 2024')
#     res2 = search_youtube('Best '+str(my_search)+' 2023')
    
#     yts = []
#     for i in res['items']+res2['items']:
#         if i['id']['kind'] == 'youtube#video':
#             yts.append(models.YTVideo(**{'id': i['id']['videoId'],
#                                 'title': html.unescape(i['snippet']['title']),
#                             'channel':i['snippet']['channelTitle'],'my_search':my_search}))
#     context = {"request": request, 'yts': yts}
#     return templates.TemplateResponse("components/yt_carousel.html", context )

# @app.get("/yt_products/{yt_id}/{my_search}", response_class=HTMLResponse)
# async def yt_products(request: Request, yt_id:str, my_search:str='Cordless vacuum'):
#     try:
#         transcript = YouTubeTranscriptApi.get_transcript( yt_id)
#     except:
#         return templates.TemplateResponse("components/products_empty.html", {"request": request} )
#     task = get_productList_from_transcript.delay(transcript, my_search)  
#     print(f'Spawned process for {task.id}')
#     return templates.TemplateResponse("components/products_delayed.html", {"request": request, 'mytask':{"id":str(task.id)},'delay':500})

# @app.get("/yt_products_status/{task_id}", response_class=HTMLResponse)
# async def yt_products_status(request: Request, task_id:str):
#     print(f'got status request for {task_id}')
#     task = get_productList_from_transcript.AsyncResult(task_id)
#     if task.state == 'FAILURE':
#         return templates.TemplateResponse("components/products_empty.html", {"request": request} )
#     elif task.state == 'PENDING':
        
#         return templates.TemplateResponse("components/products_delayed.html", {"request": request, 'mytask':{"id":str(task_id)},'delay':2500} )
#     elif task.state == 'SUCCESS':
#         if not(task.result):
#             return templates.TemplateResponse("components/products_empty.html", {"request": request} )
#         products = models.ProductsList(products=task.result[1]['products'], transcript=str(task.result[0]))
#         context = {"request": request, 'products': products}
#         return templates.TemplateResponse("components/products.html", context )
#     else:
#         return templates.TemplateResponse("components/products_delayed.html", {"request": request,'mytask':{"id":str(task_id)},'delay':2500}  )