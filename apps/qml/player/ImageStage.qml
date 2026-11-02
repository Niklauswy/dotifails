// A picture: fit / actual pixels / free zoom anchored at the pointer (wheel, pinch, double click), drag to pan,
// quarter turns. The decode is bounded: the window's size at first, more detail shortly after zooming in; animated
// GIF/WebP play with AnimatedImage. Neighbours are decoded ahead at the same size, so stepping shows them at once.
import QtQuick
import QtQuick.Window
import WysunM3

Item {
    id: root

    property url source
    property int naturalWidth           // as shown (EXIF rotation applied), from the controller
    property int naturalHeight
    property var neighbours: []         // [{url, width, height}]
    readonly property real ratio: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool animated: /\.(gif|webp)$/i.test(String(source))
    readonly property bool ready: (animated ? picture.status : still.status) === Image.Ready
    readonly property bool playing: animated && picture.playing && !picture.paused
    property string mode: "fit"         // fit | actual | zoom
    property real freeScale: 1
    property int turns: 0
    property real offsetX: 0
    property real offsetY: 0
    property real detail: 0             // decode size (longest side, pixels) once zoomed in; 0 = the window's

    readonly property real extentW: turns % 2 ? naturalHeight : naturalWidth
    readonly property real extentH: turns % 2 ? naturalWidth : naturalHeight
    readonly property real actualScale: 1 / ratio
    readonly property real fitScale: extentW > 0 && extentH > 0 ? Math.min(width / extentW, height / extentH, actualScale) : 1
    readonly property real scale: mode === "fit" ? fitScale : mode === "actual" ? actualScale : freeScale
    readonly property real zoomPercent: scale * ratio * 100
    readonly property real minScale: 0.02
    readonly property real maxScale: 32

    signal loaded(int width, int height, int frames)
    signal failed(string message)

    function windowDecode(w, h) {
        // Longest side the window can show, never more than the picture has.
        return Math.ceil(Math.min(Math.max(w, h), Math.max(width, height) * ratio));
    }

    function reset() {
        mode = "fit";
        turns = 0;
        offsetX = offsetY = 0;
        detail = 0;
    }

    function clampOffset(x, y, s) {
        const limitX = Math.max(0, (extentW * s - width) / 2);
        const limitY = Math.max(0, (extentH * s - height) / 2);
        return [Math.max(-limitX, Math.min(limitX, x)), Math.max(-limitY, Math.min(limitY, y))];
    }

    // The point of the picture under `ax, ay`, in picture pixels from its centre (before rotation).
    function pictureAt(ax, ay) {
        const dx = (ax - width / 2 - offsetX) / scale;
        const dy = (ay - height / 2 - offsetY) / scale;
        const a = -turns * Math.PI / 2;
        return [dx * Math.cos(a) - dy * Math.sin(a), dx * Math.sin(a) + dy * Math.cos(a)];
    }

    function zoomTo(s, ax, ay) {
        if (naturalWidth <= 0)
            return;
        s = Math.max(minScale, Math.min(maxScale, s));
        if (ax === undefined) {
            ax = width / 2;
            ay = height / 2;
        }
        const p = pictureAt(ax, ay);
        const a = turns * Math.PI / 2;
        const rx = p[0] * Math.cos(a) - p[1] * Math.sin(a);
        const ry = p[0] * Math.sin(a) + p[1] * Math.cos(a);
        const clamped = clampOffset(ax - width / 2 - rx * s, ay - height / 2 - ry * s, s);
        freeScale = s;
        mode = "zoom";
        offsetX = clamped[0];
        offsetY = clamped[1];
        detailTimer.restart();
    }

    function zoomBy(factor, ax, ay) {
        zoomTo(scale * factor, ax, ay);
    }

    function setMode(m) {
        mode = m;
        offsetX = offsetY = 0;
        detailTimer.restart();
    }

    // Fit <-> 100 %, keeping the point under the pointer when zooming in.
    function toggleFit(ax, ay) {
        if (mode === "fit")
            zoomTo(fitScale < actualScale ? actualScale : Math.min(maxScale, actualScale * 2), ax, ay);
        else
            setMode("fit");
    }

    function rotate(steps) {
        turns = (turns + steps + 4) % 4;
        const clamped = mode === "zoom" ? clampOffset(0, 0, scale) : [0, 0];
        offsetX = clamped[0];
        offsetY = clamped[1];
    }

    function toggleAnimation() {
        if (animated)
            picture.paused = !picture.paused;
    }

    onSourceChanged: reset()
    onWidthChanged: {
        const c = clampOffset(offsetX, offsetY, scale);
        offsetX = c[0];
        offsetY = c[1];
    }

    clip: true

    Timer {
        id: detailTimer

        interval: Theme.duration("normal")
        onTriggered: {
            const want = Math.ceil(Math.max(root.extentW, root.extentH) * root.scale * root.ratio);
            const base = root.windowDecode(root.naturalWidth, root.naturalHeight);
            // Steps of a quarter of the window, so small zoom changes do not decode again.
            const step = Math.max(1, Math.round(base / 4));
            root.detail = want > base ? Math.min(Math.max(root.naturalWidth, root.naturalHeight), Math.ceil(want / step) * step) : 0;
        }
    }

    AnimatedImage {
        id: picture

        readonly property int decode: root.detail > 0 ? root.detail : root.windowDecode(root.naturalWidth, root.naturalHeight)

        x: (root.width - width) / 2 + root.offsetX
        y: (root.height - height) / 2 + root.offsetY
        width: root.naturalWidth * root.scale
        height: root.naturalHeight * root.scale
        rotation: root.turns * 90
        // A plain Image for still pictures: AnimatedImage would hold every frame; one element keeps the code single.
        source: root.animated ? root.source : ""
        visible: root.animated
        smooth: root.scale * root.ratio < 3
        mipmap: root.scale * root.ratio < 0.5
        asynchronous: true
        cache: false
        onStatusChanged: {
            if (!root.animated)
                return;
            if (status === Image.Ready)
                root.loaded(root.naturalWidth, root.naturalHeight, frameCount);
            else if (status === Image.Error)
                root.failed("No se pudo decodificar la imagen");
        }
    }

    Image {
        id: still

        x: picture.x
        y: picture.y
        width: picture.width
        height: picture.height
        rotation: picture.rotation
        source: root.animated ? "" : root.source
        visible: !root.animated
        asynchronous: true
        autoTransform: true
        retainWhileLoading: true
        smooth: picture.smooth
        mipmap: picture.mipmap
        sourceSize: Qt.size(picture.decode, picture.decode)
        onStatusChanged: {
            if (root.animated)
                return;
            if (status === Image.Ready && root.detail === 0)
                root.loaded(root.naturalWidth, root.naturalHeight, 1);
            else if (status === Image.Error)
                root.failed("No se pudo decodificar la imagen");
        }
    }

    // Neighbours decoded ahead with the same key (url + size) the next picture will ask for.
    Repeater {
        model: root.animated ? [] : root.neighbours

        Image {
            required property var modelData

            visible: false
            asynchronous: true
            autoTransform: true
            source: modelData.url
            sourceSize: Qt.size(root.windowDecode(modelData.width, modelData.height), root.windowDecode(modelData.width, modelData.height))
        }
    }

    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => {
            const steps = event.angleDelta.y / 120 || event.pixelDelta.y / 60;
            if (steps)
                root.zoomBy(Math.pow(1.2, steps), point.position.x, point.position.y);
        }
    }

    PinchHandler {
        id: pinch

        property real startScale: 1

        target: null
        onActiveChanged: if (active)
            startScale = root.scale
        onActiveScaleChanged: if (active)
            root.zoomTo(startScale * activeScale, centroid.position.x, centroid.position.y)
    }

    DragHandler {
        id: drag

        property real startX
        property real startY

        target: null
        enabled: root.mode !== "fit"
        cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        onActiveChanged: if (active) {
            startX = root.offsetX;
            startY = root.offsetY;
        }
        onTranslationChanged: {
            const c = root.clampOffset(startX + translation.x, startY + translation.y, root.scale);
            root.offsetX = c[0];
            root.offsetY = c[1];
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: (point) => root.toggleFit(point.position.x, point.position.y)
    }
}
