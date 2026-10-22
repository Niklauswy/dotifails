import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

// Tinted surface that groups one block of the AI usage panel.
StyledRect {
    id: root

    default property alias content: inner.data
    property real padding: Tokens.padding.large
    property bool interactive
    property color stateColour: Colours.palette.m3onSurface

    signal clicked

    implicitHeight: inner.implicitHeight + padding * 2
    radius: Tokens.rounding.large
    color: Colours.tPalette.m3surfaceContainer

    StateLayer {
        visible: root.interactive
        radius: root.radius
        color: root.stateColour
        onClicked: root.clicked()
    }

    ColumnLayout {
        id: inner

        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Tokens.spacing.small
    }
}
