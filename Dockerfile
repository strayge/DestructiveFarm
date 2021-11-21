FROM python:3-slim

WORKDIR /app

COPY ./server/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./client/start_sploit.py /app/start_sploit.py
COPY ./server /app/server
WORKDIR /app/server

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=standalone.py
ENV FLAGS_DATABASE=/app/server/data/flags.sqlite
ENTRYPOINT ["python", "-m", "flask", "run", "--host", "0.0.0.0", "--with-threads" ]
