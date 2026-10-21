// Adapted from end-4/dots-hyprland overview/OverviewWidget.qml and OverviewWindow.qml (GPL-3.0).
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
.pragma library

// Usable area of an output in logical pixels: the mode rotated by its
// transform, divided by the output scale, minus the reserved edges
// (left, top, right, bottom) that bars and the frame take away.
function usable(monitor) {
    const scale = monitor.scale || 1;
    const rotated = (monitor.transform || 0) % 2;
    const reserved = monitor.reserved || [0, 0, 0, 0];
    const fullWidth = (rotated ? monitor.height : monitor.width) / scale || 1;
    const fullHeight = (rotated ? monitor.width : monitor.height) / scale || 1;
    return {
        left: reserved[0] || 0, top: reserved[1] || 0,
        width: Math.max(1, fullWidth - (reserved[0] || 0) - (reserved[2] || 0)),
        height: Math.max(1, fullHeight - (reserved[1] || 0) - (reserved[3] || 0))
    };
}

// Hyprland reports window positions in global logical coordinates, monitor
// modes in physical pixels. Rotate the mode before applying the output scale.
function geometry(window, monitor, canvasWidth, canvasHeight) {
    const area = usable(monitor);
    const size = window.size || [area.width, area.height];
    const at = window.at || [(monitor.x || 0) + area.left, (monitor.y || 0) + area.top];
    const width = Math.max(1, Math.min(canvasWidth, size[0] / area.width * canvasWidth));
    const height = Math.max(1, Math.min(canvasHeight, size[1] / area.height * canvasHeight));
    return {
        x: Math.max(0, Math.min(canvasWidth - width, (at[0] - (monitor.x || 0) - area.left) / area.width * canvasWidth)),
        y: Math.max(0, Math.min(canvasHeight - height, (at[1] - (monitor.y || 0) - area.top) / area.height * canvasHeight)),
        width: width, height: height
    };
}

// Position and size for an end-4 style grid: workspace n (1-based) inside a
// group of rows x columns cells.
function cell(workspace, rows, columns) {
    const index = (workspace - 1) % (rows * columns);
    return { row: Math.floor(index / columns), column: index % columns };
}
