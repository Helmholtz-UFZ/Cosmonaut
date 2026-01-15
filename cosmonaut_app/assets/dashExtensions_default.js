window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
                const {
                    selected,
                    zoom
                } = context.hideout;
                // Increase base weight to make lines easier to click. Keep adaptive thinning on zoom in.
                const lineWeight = zoom ? Math.max(3, 18 / zoom) : 4; // at zoom=10 -> ~3
                const color = selected.includes(feature.id) ? 'yellow' : 'red';
                return {
                    color: color,
                    weight: lineWeight,
                    opacity: 0.85
                };
            }

            ,
        function1: function(feature, context) {
            const {
                selected,
                zoom
            } = context.hideout;
            const lineWeight = zoom ? Math.max(4, 22 / zoom) : 5;
            const color = selected.includes(feature.id) ? 'orange' : '#ff6666';
            return {
                color: color,
                weight: lineWeight,
                opacity: 1.0
            };
        }

    }
});