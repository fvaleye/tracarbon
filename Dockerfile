FROM python:3.8-buster

COPY . ./carbon-tracker

# prerequisites
RUN apt-get -y update && apt-get -y install python3 python3-pip

# Python
RUN pip install --upgrade pip && pip install poetry

WORKDIR ./carbon-tracker
