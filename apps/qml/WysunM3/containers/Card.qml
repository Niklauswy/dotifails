// M3 card: a container for one subject (an album, a file preview, a summary). elevated (surfaceContainerLow,
// level 1), filled (surfaceContainerHighest) or outlined (surface with an outlineVariant edge); medium corner.
// `clickable` adds the state layer and `clicked`.
import QtQuick
import WysunM3

Surface {
    id: root

    property string variant: "elevated"      // elevated | filled | outlined
    property bool clickable
    default property alias content: body.data
    property real padding: Theme.padding.large ?? 0
    readonly property alias body: body

    signal clicked(var mouse)

    radius: Theme.rounding.medium ?? 0
    level: variant === "elevated" ? Metrics.cardElevation + (layer.hovered ? 1 : 0) : 0
    container: variant === "filled" ? Theme.m3surfaceContainerHighest : variant === "outlined" ? Theme.m3surface : Theme.m3surfaceContainerLow
    // Cards keep their container role exact: elevation shows as the shadow.
    color: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContainer) : container
    outline: variant === "outlined" ? Metrics.outlineWidth : 0
    outlineColor: Theme.m3outlineVariant

    Item {
        id: body

        anchors.fill: parent
        anchors.margins: root.padding
        opacity: root.contentOpacity
    }

    StateLayer {
        id: layer

        z: 1
        visible: root.clickable
        radius: root.radius
        disabled: root.disabled || !root.clickable
        onClicked: mouse => root.clicked(mouse)
    }
}
