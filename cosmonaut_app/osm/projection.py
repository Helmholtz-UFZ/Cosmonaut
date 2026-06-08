"""Reproject routing GeoJSON features to the output CRS.

Shared by the download path (`cosmonaut_app/osm/downloader.py`, streaming) and the
edit path (`cosmonaut_app/street_selector.py`, after street-selection edits), so
both produce the transformed file identically — pyproj projection + the named CRS
header, written atomically — instead of the download using one method and the edit
another. pyproj is exactly what geopandas used underneath, so coordinates match
the previous output (verified: 0 m delta).
"""

import pyproj

from cosmonaut_app.osm.geojson_writer import StreamingGeoJsonWriter


def project_feature(feature, transformer):
    """Reproject one EPSG:4326 GeoJSON LineString feature using ``transformer``.

    Drops the top-level ``id`` to match the transformed file sensor-routing reads
    (it keys on ``properties.osmid``).
    """
    coordinates = feature["geometry"]["coordinates"]
    eastings, northings = transformer.transform(
        [lon for lon, lat in coordinates],
        [lat for lon, lat in coordinates],
    )
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [float(easting), float(northing)]
                for easting, northing in zip(eastings, northings)
            ],
        },
        "properties": feature["properties"],
    }


def project_features_to_file(features, dst_path, src_epsg, dst_epsg):
    """Project an in-memory list of features and write the transformed GeoJSON.

    Used by the street-selection edit path, which holds the edited feature set in
    memory (no streaming needed there). Output matches the download's transformed
    file: a named CRS header, reprojected coordinates, atomic write.
    """
    transformer = pyproj.Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)
    with StreamingGeoJsonWriter(dst_path, crs_epsg=dst_epsg) as writer:
        for feature in features:
            writer.write(project_feature(feature, transformer))
