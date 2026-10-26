// An expressive M3 shape (cookie, flower, sunny...) holding an icon or artwork: the "emblem" next to a title or
// in an empty state. Uses M3Shapes when the runtime has it; otherwise a rounded square with the extraLarge corner
// (one warning on stderr), and also under the software scene graph, where MaterialShape's geometry does not
// draw. `morphOnHover` morphs to `hoverShape` with the default spatial spring.
import QtQuick
import WysunM3

Item {
    id: root

    property string shape: "cookie"          // cookie | cookie4 | cookie12 | squircle | circle | flower | sunny | clover | pill | gem | burst | puffy
    property string hoverShape: "flower"
    property bool morphOnHover
    property real size: Metrics.emblemSize
    property color color: Theme.m3primaryContainer
    property string icon
    property color iconColor: Theme.m3onPrimaryContainer
    property real iconSize: Math.round(size * 0.43)
    default property alias content: holder.data
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var usingShapes: _software ? false : body.status === Loader.Ready ? true : body.status === Loader.Error ? false : undefined
    readonly property real fallbackRadius: Theme.rounding.extraLarge ?? 0
    readonly property bool hovered: hover.hovered

    readonly property var _names: ({
            cookie: "Cookie9Sided",
            cookie4: "Cookie4Sided",
            cookie12: "Cookie12Sided",
            squircle: "Square",
            circle: "Circle",
            flower: "Flower",
            sunny: "Sunny",
            clover: "Clover4Leaf",
            pill: "Pill",
            gem: "Gem",
            burst: "SoftBurst",
            puffy: "Puffy"
        })

    implicitWidth: size
    implicitHeight: size
    width: implicitWidth
    height: implicitHeight

    HoverHandler {
        id: hover

        enabled: root.morphOnHover
    }

    Loader {
        id: body

        anchors.fill: parent
        active: !root._software
        source: Qt.resolvedUrl("CookieShape.qml")
        onLoaded: {
            item.shapeName = Qt.binding(() => root._names[root.shape] ?? "Cookie9Sided");
            item.hoverShapeName = Qt.binding(() => root._names[root.hoverShape] ?? item.shapeName);
            item.hovered = Qt.binding(() => root.morphOnHover && root.hovered);
            item.color = Qt.binding(() => root.color);
            item.animationDuration = Qt.binding(() => Motion.ms("defaultSpatial"));
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.usingShapes === false
        radius: root.shape === "circle" || root.shape === "pill" ? Theme.fullRadius(height) : root.fallbackRadius
        color: root.color
    }

    Item {
        id: holder

        anchors.fill: parent

        Icon {
            anchors.centerIn: parent
            name: root.icon
            size: root.iconSize
            filled: true
            color: root.iconColor
        }
    }
}
