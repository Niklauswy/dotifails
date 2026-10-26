// M3 shared axis: pages slide (x, y) or scale (z) along a shared axis while they fade. `forward` goes deeper/next,
// `back` returns. For navigation with a spatial or hierarchical relationship (steps, drill-down).
import QtQuick
import WysunM3

TransitionHost {
    id: root

    property string axis: "x"                // "x" | "y" | "z"

    onAboutToShow: forward => {
        const offset = Theme.spacing.extraLargeIncreased * (forward ? 1 : -1);
        exitX = axis === "x" ? -offset : 0;
        exitY = axis === "y" ? -offset : 0;
        enterX = axis === "x" ? offset : 0;
        enterY = axis === "y" ? offset : 0;
        exitScale = axis === "z" ? (forward ? Metrics.sharedAxisZLarge : Metrics.sharedAxisZSmall) : 1;
        enterScale = axis === "z" ? (forward ? Metrics.sharedAxisZSmall : Metrics.sharedAxisZLarge) : 1;
    }
}
