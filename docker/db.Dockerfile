FROM postgres:latest AS db

# Set environment variables
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG POSTGRES_DB

ENV POSTGRES_USER=$POSTGRES_USER
ENV POSTGRES_PASSWORD=$POSTGRES_PASSWORD
ENV POSTGRES_DB=$POSTGRES_DB

# Copy SQL scripts to docker-entrypoint-initdb.d to execute on container start
COPY /docker/init.sql /docker-entrypoint-initdb.d/