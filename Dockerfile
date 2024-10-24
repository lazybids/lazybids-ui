FROM python:3.10
WORKDIR /code
COPY ./ /code/
RUN pip install --no-cache-dir --upgrade /code/
WORKDIR /code/lazybids_ui
CMD ["fastapi", "run", "main.py", "--port", "80"]