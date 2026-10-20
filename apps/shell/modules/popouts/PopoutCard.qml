// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Panels.qml; modules/dashboard/Wrapper.qml; modules/dashboard/Content.qml,
// commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../dashboard" as Dashboard

Components.StyledRect {
    id: root
    required property var controller
    required property var motion
    property string monitorName: ""
    property real contentOpacity: 1
    // The host draws the rounded frame while it morphs; standalone previews
    // keep the card's own frame.
    property bool framed: true
    property bool live: true
    property bool sampling: true
    property var providers: null
    property alias dashboardTab: dashboard.currentIndex

    readonly property string surface: controller ? controller.surface : ""
    readonly property bool dashboardVisible: surface === "dashboard" || surface === "test"
    readonly property string pendingTitle: {
        switch (surface) {
        case "launcher": return "Lanzador";
        case "menu": return "Menú rápido";
        case "windows": return "Ventanas";
        case "session": return "Sesión";
        default: return "Panel";
        }
    }
    readonly property real preferredWidth: dashboardVisible
        ? Math.max(Wysun.Appearance.spaceXl * 18, dashboard.implicitWidth) + Wysun.Appearance.spaceL * 2
        : Wysun.Appearance.spaceXl * 24
    readonly property real preferredHeight: dashboardVisible
        ? header.implicitHeight + dashboard.implicitHeight + Wysun.Appearance.spaceM * 2 + Wysun.Appearance.spaceL * 2
        : header.implicitHeight + Wysun.Appearance.spaceXl * 8 + Wysun.Appearance.spaceL * 2

    radius: Wysun.Appearance.radiusL
    color: framed ? Wysun.Appearance.materialMid : "transparent"
    border.width: framed ? Wysun.Appearance.borderWidth : 0
    border.color: Wysun.Appearance.materialEdge
    clip: framed

    // Consume clicks on the card's empty areas so they cannot dismiss it.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        Accessible.ignored: true
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        opacity: root.contentOpacity
        spacing: Wysun.Appearance.spaceM

        RowLayout {
            id: header
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS

            Components.StyledText {
                Layout.fillWidth: true
                text: "Wysun"
                color: Wysun.Appearance.textStrong
                font.pixelSize: Wysun.Appearance.fontTitle
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                Accessible.role: Accessible.Heading
            }
            Components.StyledText {
                Layout.maximumWidth: root.width / 3
                text: root.monitorName
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
                elide: Text.ElideRight
                Accessible.name: root.monitorName ? "Pantalla " + root.monitorName : ""
            }
            Components.ActionButton {
                objectName: "closePopout"
                motion: root.motion
                compact: true
                glyph: "close"
                label: "Cerrar panel"
                onClicked: root.controller.close()
            }
        }

        // The integrator adds one loader per remaining surface here. They all
        // share this single focused host and controller.
        Dashboard.Wrapper {
            id: dashboard
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.dashboardVisible
            controller: root.controller
            motion: root.motion
            monitorName: root.monitorName
            live: root.live
            sampling: root.sampling && root.dashboardVisible
            fixtureProviders: root.providers
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.dashboardVisible
            spacing: Wysun.Appearance.spaceM

            Item { Layout.fillHeight: true }
            Components.StyledText {
                Layout.fillWidth: true
                text: root.pendingTitle
                color: Wysun.Appearance.textStrong
                font.pixelSize: Wysun.Appearance.fontHeading
                font.weight: Font.DemiBold
                Accessible.role: Accessible.Heading
            }
            Components.StyledText {
                Layout.fillWidth: true
                text: "Este módulo se integrará en una fase posterior. Mientras tanto, Escape o un clic fuera cierran el panel."
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontBody
                wrapMode: Text.WordWrap
            }
            Item { Layout.fillHeight: true }
        }
    }
}
