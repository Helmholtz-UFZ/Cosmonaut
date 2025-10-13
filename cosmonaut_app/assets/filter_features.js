// Dash clientside callback for filtering GeoJSON features by selected road types

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    client_filter: {
        /**
         * Filter GeoJSON features by selected road types.
         * @param {Array} selectedRoads - The selected road types from the dropdown.
         * @param {Object} geojsonData - The full GeoJSON data.
         * @returns {Object} Filtered GeoJSON FeatureCollection.
         */
        filterGeoJSON: function(selectedRoads, geojsonData) {
            if (!geojsonData || !geojsonData.features) {
                return window.dash_clientside.no_update;
            }
            if (!selectedRoads || selectedRoads.length === 0) {
                // If nothing selected, show all features
                return geojsonData;
            }
            // Filter features by selected road types
            const filtered = geojsonData.features.filter(
                feature => selectedRoads.includes(feature.properties.highway)
            );
            return {
                ...geojsonData,
                features: filtered
            };
        }
    }
});