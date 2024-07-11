from celery import Celery
import os
celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

import openneuro

@celery.task(name="openneuro_download")
def openneuro_download(DatabaseID, Version, data_dir):
    if Version and not(Version=='latest'):
        openneuro.download(dataset=DatabaseID, target_dir=data_dir, tag=Version)
    else:
        openneuro.download(dataset=DatabaseID, target_dir=data_dir)