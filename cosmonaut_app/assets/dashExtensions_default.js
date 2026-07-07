window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
                const {
                    selected,
                    dimmed
                } = context.hideout;
                const isMarked = selected.includes(feature.id);
                const color = isMarked ? '#f9a825' : '#d32f2f';
                const opacity = dimmed ? 0.6 : 0.85;
                return {
                    color: color,
                    weight: 3,
                    opacity: opacity,
                    dashArray: isMarked ? '6, 4' : null
                };
            }

            ,
        function1: function(feature, context) {
                const {
                    selected,
                    dimmed
                } = context.hideout;
                const isMarked = selected.includes(feature.id);
                if (dimmed) {
                    const color = isMarked ? '#f9a825' : '#d32f2f';
                    return {
                        color: color,
                        weight: 3,
                        opacity: 0.6,
                        dashArray: isMarked ? '6, 4' : null
                    };
                }
                const color = isMarked ? '#ffb300' : '#ff6666';
                return {
                    color: color,
                    weight: 4,
                    opacity: 1.0,
                    dashArray: isMarked ? '6, 4' : null
                };
            }

            ,
        function2: function(e, ctx) {
            // Streets are only clickable on the street-selection page. Without this
            // guard, clicks on any other page would silently mark roads that
            // "Remove clicked roads" later deletes. Guard on the URL, NOT on
            // ctx.hideout.dimmed: event handlers keep a snapshot of hideout from
            // binding time and never see server-side hideout updates (verified —
            // the style functions DO read hideout dynamically, events don't).
            if (!window.location.pathname.includes('street-selection')) {
                return;
            }
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