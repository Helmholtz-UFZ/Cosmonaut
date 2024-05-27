window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
            const {
                selected
            } = context.hideout;
            if (selected.includes(feature.id)) {
                return {
                    color: 'yellow',
                    weight: 5
                }
            }
            return {
                color: 'red',
                weight: 5
            }
        }

    }
});