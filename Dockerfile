FROM python:3.10-slim-buster

WORKDIR /python-docker

RUN pip3 install --upgrade pip
COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .
CMD [ "python3", "-u", "youtrack-slackbot.py"]