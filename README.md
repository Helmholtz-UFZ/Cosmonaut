# COSMONAUT
# COSmic ray based soil MOisture prediction NAvigation and UTility Tool

This project is a web application built with Dash and Dash Leaflet for transforming and visualizing CSV data for the COSMOPOLITAN Project at UFZ. 
It allows users to upload a CSV file, transforms the data, queries OpenStreetMap for a planed navigation feature, and visualizes the csv-data on a map (NOTE: Visualization doesn`t work for bigger files)

## Features

- File upload: Users can upload a CSV file to the application.
- Data transformation: The application transforms the uploaded data from EPSG:31468 to EPSG:4326.
- OSM query: The application queries OpenStreetMap for roads within the convex hull of the uploaded data.
- Data visualization: The application visualizes the uploaded data and the queried OSM data on a map.
- It makes individual Jobs which are saved into a PostgreSQL DB.
- (Future) Is triggering a route calculation based on User Input of the best roads.

## Installation

1. Clone this repository.
2. Start the Service with `./dev_up.sh mock` or `./dev_up.sh prod`

# DEV:

## TODO`s

- guter commit bevor ich nach valencia gehe. mit note was ich geschafft habe und was ich machen will

### Implement Testing

- unity test
- integration test

- beides machen
- höchstes der Gefühle wäre n Bot der die Webiste komplett testet, inklusive file upload etc

### CAN

- small discreption for list of road types - not super important
- feedback implementation for the agents (ticketsystem?) - not super important

### Other:

- Germany OSM Download ?
- aws bucket mit miniIoServer connecten
- GeoServer für WMS optimisieren
- mockups machen <- für tests gut (Dockerimage)
- laufen auf ufz infrastruktur
- erwartungshaltung fürs styling der SLD klarmachen (?)

## Useful Commands

`./dev_up.sh mock`

`rm -rf cosmonaut_app/work_dir/*`

`psql -U cosmonaut -p 5432 -h localhost -d cosmonaut_db`

- with gunicorn
`gunicorn -w 4 -b 0.0.0.0:$FLASK_PORT cosmonaut_app.wsgi:app`, add `--log-level debug` for detailed debuging.