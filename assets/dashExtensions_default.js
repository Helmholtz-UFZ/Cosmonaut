window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
            const {
                selected,
                zoom
            } = context.hideout;
            const lineWeight = zoom ? Math.max(1, 5 / zoom) : 2;
            if (selected.includes(feature.id)) {
                return {
                    color: 'yellow',
                    weight: lineWeight
                };
            }
            return {
                color: 'red',
                weight: lineWeight
            };
        }

    }
});