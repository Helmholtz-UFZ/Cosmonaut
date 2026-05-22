window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
                const {
                    selected,
                    zoom,
                    dimmed
                } = context.hideout;
                // Increase base weight to make lines easier to click. Keep adaptive thinning on zoom in.
                const lineWeight = zoom ? Math.max(3, 18 / zoom) : 4; // at zoom=10 -> ~3
                const color = selected.includes(feature.id) ? 'yellow' : 'red';
                const opacity = dimmed ? 0.4 : 0.85;
                return {
                    color: color,
                    weight: lineWeight,
                    opacity: opacity
                };
            }

            ,
        function1: function(feature, context) {
                const {
                    selected,
                    zoom,
                    dimmed
                } = context.hideout;
                const lineWeight = zoom ? Math.max(4, 22 / zoom) : 5;
                const color = selected.includes(feature.id) ? 'orange' : '#ff6666';
                const opacity = dimmed ? 0.5 : 1.0;
                return {
                    color: color,
                    weight: lineWeight,
                    opacity: opacity
                };
            }

            ,
        function2: function(e, ctx) {
            const id = e.layer.feature.id;
            const selected = [...(ctx.hideout.selected || [])];
            const idx = selected.indexOf(id);
            if (idx > -1) {
                selected.splice(idx, 1);
            } else {
                selected.push(id);
            }
            ctx.setProps({
                hideout: {
                    ...ctx.hideout,
                    selected: selected
                }
            });
        }
    }
});