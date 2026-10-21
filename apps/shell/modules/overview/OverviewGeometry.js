// Adapted from end-4/dots-hyprland overview/OverviewWindow.qml (GPL-3.0).
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
.pragma library

// Hyprland reports window positions in global logical coordinates, monitor
// modes in physical pixels. Rotate the mode before applying the output scale.
function geometry(window, monitor, canvasWidth, canvasHeight) {
    const scale = monitor.scale || 1;
    const rotated = (monitor.transform || 0) % 2;
    const sourceWidth = Math.max(1, (rotated ? monitor.height : monitor.width) / scale || 1);
    const sourceHeight = Math.max(1, (rotated ? monitor.width : monitor.height) / scale || 1);
    const size = window.size || [sourceWidth, sourceHeight];
    const at = window.at || [monitor.x || 0, monitor.y || 0];
    const width = Math.max(1, Math.min(canvasWidth, size[0] / sourceWidth * canvasWidth));
    const height = Math.max(1, Math.min(canvasHeight, size[1] / sourceHeight * canvasHeight));
    return {
        x: Math.max(0, Math.min(canvasWidth - width, (at[0] - (monitor.x || 0)) / sourceWidth * canvasWidth)),
        y: Math.max(0, Math.min(canvasHeight - height, (at[1] - (monitor.y || 0)) / sourceHeight * canvasHeight)),
        width: width, height: height
    };
}
