// A container surface: a colour role, tonal elevation (level 0-5 tints the container with surfaceTint) and a
// soft shadow of stacked layers for raised ones, an optional outline, and the disabled look (10 % container,
// contents at `contentOpacity`).
import QtQuick

Rectangle {
    id: root

    property color container: Theme.m3surface
    property int level: 0
    property int outline: 0
    property color outlineColor: Theme.m3outlineVariant
    property bool disabled
    readonly property real contentOpacity: disabled ? Metrics.disabledContent : 1
    readonly property int _level: Math.max(0, Math.min(5, level))

    color: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContainer) : Qt.tint(container, Qt.alpha(Theme.m3surfaceTint, Metrics.elevationTint[_level]))
    border.width: outline
    border.color: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledOutline) : outlineColor

    Repeater {
        model: root.disabled ? 0 : root._level

        Rectangle {
            required property int index

            z: -1
            anchors.fill: parent
            anchors.margins: -(index + 1)
            anchors.bottomMargin: -(index + 1) * 2
            radius: root.radius + index + 1
            color: Qt.alpha(Theme.m3shadow, Metrics.shadowLayerOpacity)
        }
    }
}
