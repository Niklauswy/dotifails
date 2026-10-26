// M3 container transform: an element (a card, a list row) grows into the page that shows it, and shrinks back.
// `open(source, component)` starts exactly over `source`; the page stays laid out for the full size while the
// container reveals it. For opening an element into its detail.
import QtQuick
import WysunM3

Item {
    id: root

    property color containerColor: Theme.m3surface
    property real endRadius: 0
    readonly property alias container: box
    readonly property bool opened: _opened
    readonly property bool running: anim.running

    property bool _opened
    property Item _source
    property Item _content

    function open(source: Item, component: Component, properties: var): Item {
        if (anim.running)
            anim.complete();
        _discard();
        const origin = source.mapToItem(root, 0, 0);
        _source = source;
        box.x = origin.x;
        box.y = origin.y;
        box.width = source.width;
        box.height = source.height;
        box.radius = source.radius ?? Theme.rounding.medium;
        box.visible = true;
        const page = component.createObject(box, properties ?? ({}));
        if (!page) {
            box.visible = false;
            return null;
        }
        page.width = Qt.binding(() => root.width);
        page.height = Qt.binding(() => root.height);
        page.x = Qt.binding(() => -box.x);
        page.y = Qt.binding(() => -box.y);
        _content = page;
        _opened = true;
        _animate(0, 0, root.width, root.height, endRadius, 1, true);
        return page;
    }

    function close(): void {
        if (!_opened)
            return;
        if (anim.running)
            anim.complete();
        const origin = _source ? _source.mapToItem(root, 0, 0) : Qt.point(box.x, box.y);
        _opened = false;
        _animate(origin.x, origin.y, _source ? _source.width : box.width, _source ? _source.height : box.height,
                 _source?.radius ?? Theme.rounding.medium, 0, false);
    }

    function _animate(x: real, y: real, w: real, h: real, radius: real, contentOpacity: real, opening: bool): void {
        if (Motion.reduced) {
            box.x = x;
            box.y = y;
            box.width = w;
            box.height = h;
            box.radius = radius;
            if (_content)
                _content.opacity = contentOpacity;
            if (!opening)
                _discard();
            return;
        }
        if (_content && opening)
            _content.opacity = 0;
        xAnim.to = x;
        yAnim.to = y;
        wAnim.to = w;
        hAnim.to = h;
        rAnim.to = radius;
        fadeAnim.target = _content;
        fadeAnim.to = contentOpacity;
        fadeAnim.kind = opening ? "defaultEffects" : "fastEffects";
        pause.duration = opening ? Motion.ms("fastEffects") : 0;
        anim.closing = !opening;
        anim.start();
    }

    function _discard(): void {
        box.visible = false;
        if (_content) {
            _content.destroy();
            _content = null;
        }
    }

    Rectangle {
        id: box

        objectName: "container"
        visible: false
        clip: true
        color: root.containerColor
    }

    ParallelAnimation {
        id: anim

        property bool closing

        onRunningChanged: {
            if (!running && closing)
                root._discard();
        }

        Anim {
            id: xAnim

            target: box
            property: "x"
            kind: "slowSpatial"
        }
        Anim {
            id: yAnim

            target: box
            property: "y"
            kind: "slowSpatial"
        }
        Anim {
            id: wAnim

            target: box
            property: "width"
            kind: "slowSpatial"
        }
        Anim {
            id: hAnim

            target: box
            property: "height"
            kind: "slowSpatial"
        }
        Anim {
            id: rAnim

            target: box
            property: "radius"
            kind: "slowEffects"
        }
        SequentialAnimation {
            PauseAnimation {
                id: pause
            }
            Anim {
                id: fadeAnim

                property: "opacity"
            }
        }
    }
}
