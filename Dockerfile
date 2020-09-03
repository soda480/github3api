FROM python:3.6-alpine AS build-image

ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /github3api

COPY . /github3api/

RUN apk update
RUN apk add git gcc
RUN pip install --upgrade pip
RUN pip install pybuilder==0.11.17
RUN pyb install_dependencies
RUN pyb
RUN pyb publish


FROM python:3.6-alpine

ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /opt/github3api

COPY --from=build-image /github3api/target/dist/github3api-*/dist/github3api-*.tar.gz /opt/github3api

RUN pip install github3api-*.tar.gz

CMD echo 'DONE'
