FROM python:3.10-slim-buster

WORKDIR /python-docker

ENV TZ=Europe/Paris
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip3 install --upgrade pip
COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt
VOLUME config
COPY . .
CMD [ "python3", "-u", "youtrack-slackbot.py"]
