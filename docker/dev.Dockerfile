# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV MPLCONFIGDIR=/python_docker/cosmonaut/.config/matplotlib

RUN useradd -m -u 1000 appuser && \
    apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install git libpq-dev gcc g++ libgdal-dev gdal-bin rclone && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip wheel setuptools && \
    pip install uv && \
    mkdir -p $MPLCONFIGDIR && chmod 777 $MPLCONFIGDIR && \
    mkdir -p /python_docker/cosmonaut/.config && chmod 777 /python_docker/cosmonaut/.config && \
    mkdir -p /python_docker/cosmonaut/assets && chmod 777 /python_docker/cosmonaut/assets

    
WORKDIR /python_docker/cosmonaut

ENV PYTHONPATH=/python_docker/cosmonaut/
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY --chown=1000:1000 pyproject.toml uv.lock /python_docker/cosmonaut/

RUN uv export --format requirements-txt --no-hashes > /tmp/lock-reqs.txt \
    && uv pip install --system -r /tmp/lock-reqs.txt

COPY --chown=1000:1000 . .

COPY --chown=1000:1000 .env .env

RUN chown -R 1000:1000 /python_docker/cosmonaut

USER appuser

CMD if [ "$GUNICORN" = 1 ] ; then \
        gunicorn --preload -w 4 -b 0.0.0.0:$FLASK_PORT --timeout 600 cosmonaut_app.wsgi:app; \
    else \
        python3 -m cosmonaut_app.app; \
    fi

