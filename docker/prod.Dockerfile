# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV MPLCONFIGDIR /python_docker/cosmonaut/.config/matplotlib

RUN useradd -m -u 1000 appuser

RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install git libpq-dev gcc g++ libgdal-dev gdal-bin && \
    pip install --upgrade pip wheel setuptools && pip install poetry

WORKDIR /python_docker/cosmonaut

RUN mkdir -p $MPLCONFIGDIR && chmod 777 $MPLCONFIGDIR

ENV PYTHONPATH=/python_docker/cosmonaut/
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY poetry.lock pyproject.toml /python_docker/cosmonaut/

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

USER 1000

COPY . .

COPY .env_prod .env

RUN chown -R 1000:1000 /python_docker/cosmonaut

USER appuser

CMD gunicorn --timeout 120 -w 4 -b 0.0.0.0:$FLASK_PORT cosmonaut_app.wsgi:app;
