# COSMONAUT
# COSmic ray based soil MOisture prediction NAvigation and UTility Tool

This project is a web application built with Dash and Dash Leaflet for transforming and visualizing CSV data for the COSMOPOLITAN Project at UFZ. 
It allows users to upload a CSV file, transforms the data, queries OpenStreetMap for a planed navigation feature, and visualizes the csv-data on a map (NOTE: Visualization doesn't work for bigger files)

## NOTE (to me and John [and all others])

The image overlay is not the best solution. We need to think about using a WNSTileServer (eg. Terracotta)

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


#
# TODO's

verschiedene SLD-file bereitstellen, welche vom user ausgewählt werden kann
logik in viewer einbauen
Postgres rdy machen (lokale instnaz mit docker) (python package: sqlalchemy)

# Ablauf

datei hochladen, zoom auf region, hintergrund (osm) daten laden /runterladen, user kann auswählen welche straßen, higliten, user nachfrage ob zufrieden, dann start rouute berechnen

straßenselektor für die region

erwartungshaltung fürs styling der SLD klarmachen

# Geoserver

aws bucket mit miniIoServer connecten
GeoServer connecten
mockups machen <- für tests gut (Dockerimage)
laufen auf ufz infrastruktur
und dann mit dockers
dockercontainer von dennen

2 funktionen safe und delete für minioapi file class
.env file
developer env und set up für server zu machen



# CAN

small discreption for list of road types - not super important
feedback implementation for the agents (ticketsystem?) - not super important
unify the .json - important

Für CAN die OSM abfrage lesen (nodes wieder zurück als list ausgeben):
```
# Read GeoJSON file into a new DataFrame
new_data = gpd.read_file(osm_file_path)

# Convert strings back to lists
import ast
new_data['nodes'] = new_data['nodes'].apply(ast.literal_eval)
```

Check amount of highway=track which have maxspeed value
# QR CODE für Gmaps navigation

# Germany OSM Download