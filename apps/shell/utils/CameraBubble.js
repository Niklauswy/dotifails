.pragma library

// Where the camera bubble goes in a recording of `width` x `height`: the same arithmetic as the renderer
// (wysun_recorder/render.py camera_overlay), so what the shell shows before and during the recording is where the
// camera will actually cover the video. tests/qml/check_shell_camera_math.py keeps both equal.
// style: { shape: "circle" | "rounded", size: "small" | "medium" | "large", corner: "top-left" | ... }.

const SIZES = { small: 0.20, medium: 0.28, large: 0.38 };
const CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"];

function even(value) {
    return Math.floor(Math.floor(value) / 2) * 2;
}

// { x, y, width, height, radius } of the bubble inside the recorded area.
function rect(width, height, style) {
    const s = style ?? {};
    const tall = Math.max(2, even(height * (SIZES[s.size] ?? SIZES.medium)));
    const circle = (s.shape ?? "circle") === "circle";
    const wide = circle ? tall : Math.max(2, even(Math.floor(tall * 4 / 3)));
    const margin = Math.max(8, Math.floor(height * 0.035));
    const corner = s.corner ?? "bottom-right";
    const x = corner.endsWith("right") ? width - wide - margin : margin;
    const y = corner.startsWith("bottom") ? height - tall - margin : margin;
    return { x: Math.max(0, x), y: Math.max(0, y), width: wide, height: tall, radius: circle ? wide / 2 : Math.max(4, Math.floor(tall / 8)) };
}

// The corner whose quadrant holds the point (cx, cy) of a `width` x `height` area.
function nearestCorner(cx, cy, width, height) {
    return (cy > height / 2 ? "bottom" : "top") + "-" + (cx > width / 2 ? "right" : "left");
}

// The four corners the renderer knows (it has no free position).
function corners() {
    return CORNERS.slice();
}
