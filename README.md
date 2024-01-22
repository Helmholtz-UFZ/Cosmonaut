# UFZ Flask Frontend Dev Repo

This project is a web application built with Dash and Dash Leaflet for transforming and visualizing CSV data for the COSMOPOLITAN Project at UFZ. 
It allows users to upload a CSV file, transforms the data, queries OpenStreetMap for a planed navigation feature, and visualizes the csv-data on a map (NOTE: Visualization doesn't work for bigger files)

## Features

- File upload: Users can upload a CSV file to the application.
- Data transformation: The application transforms the uploaded data from EPSG:31468 to EPSG:4326.
- OSM query: The application queries OpenStreetMap for roads within the convex hull of the uploaded data.
- Data visualization: The application visualizes the uploaded data and the queried OSM data on a map.

## Installation

1. Clone this repository.
2. Install the required Python packages with Poetry: `poetry install`
3. Spawn a new Poetry shell: `poetry shell`
3. Run the application: `python app.py`

## Usage

1. Open the application in a web browser.
2. Drag and drop a CSV file into the upload area or click the upload area to select a file.
3. The application will automatically transform the data, query OSM, and visualize the data on the map.

## Dependencies

- Dash: A Python framework for building analytical web applications.
- Dash Leaflet: An open-source JavaScript library for mobile-friendly interactive maps.
- GeoPandas: A Python library for working with geospatial data.
- PyProj: A Python interface to PROJ (cartographic projections and coordinate transformations library).
