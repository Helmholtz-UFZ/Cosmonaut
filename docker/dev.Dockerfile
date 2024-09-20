# syntax=docker/dockerfile:1

FROM python:3.10.12-slim

ENV MPLCONFIGDIR /python_docker/cosmonaut/.config/matplotlib

RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install git libpq-dev gcc g++ libgdal-dev gdal-bin
RUN pip install --upgrade pip wheel setuptools && pip install poetry

WORKDIR /python_docker/cosmonaut

RUN mkdir -p $MPLCONFIGDIR && chmod 777 $MPLCONFIGDIR

ENV PYTHONPATH=/python_docker/cosmonaut/
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY poetry.lock pyproject.toml /python_docker/cosmonaut/

RUN poetry config virtualenvs.create false 
RUN poetry install --no-interaction --no-ansi

USER 1000

COPY . .

CMD if [ "$GUNICORN" = 1 ] ; then \
        gunicorn -w 4 -b 0.0.0.0:$FLASK_PORT cosmonaut_app.wsgi:app; \
    else \
        python3 /python_docker/cosmonaut/cosmonaut_app/app.py; \
    fi

