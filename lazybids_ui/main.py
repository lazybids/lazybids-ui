# Standard library imports
import shutil

# Third-party imports
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from py7zr import unpack_7zarchive
from scalar_fastapi import get_scalar_api_reference

# Local imports
from lazybids_ui.src import models, rest_api, html_api

# Try to register 7zip unpacking format, ignore if already registered
try:
    shutil.register_unpack_format('7zip', ['.7z'], unpack_7zarchive)
except shutil.RegistryError:
    pass  # Format is already registered, so we can ignore this error

# Load environment variables
load_dotenv()

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
app.include_router(html_api.router)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

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

# Add a new endpoint to check job status
@app.get("/job_status/{job_id}", tags=["HTML"])
async def check_job_status(job_id: str):
    return await models.get_job_status(job_id)

@app.get("/", response_class=HTMLResponse, tags=["HTML"])
@app.get("/index/{str}", response_class=HTMLResponse, tags=["HTML"])
@app.get("/index/{str}/{str2}", response_class=HTMLResponse, tags=["HTML"])
async def root(request: Request, url: str = '', url2: str = ''):
    if not url:
        context = {'mainViewURL': '/html/datasets'}
    elif not url2:
        context = {'mainViewURL': f'/html/{url}'}        
    else:
        context = {'mainViewURL': f'/html/{url}/{url2}'}     
    context['request'] = request
    return templates.TemplateResponse("root.html", context)

def run():
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
