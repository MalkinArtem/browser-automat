FROM python:3.11.5
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN python -m pip install -r requirements.txt

COPY . /app
CMD ["python", "main.py"]