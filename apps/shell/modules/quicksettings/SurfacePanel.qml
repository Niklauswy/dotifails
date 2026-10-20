// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/drawers/ContentWindow.qml, modules/utilities/Wrapper.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Card chrome for the quick settings, notification centre and session menu.
// The Loader destroys the content as soon as the popout is hidden, so a closed
// surface keeps no provider, timer or PipeWire tracker alive.
import QtQuick
import "../../" as Wysun
import "../../components" as Components
import "../notifications" as Notifications
import "../session" as Session

Components.StyledRect {
    id: root

    required property var controller
    required property var motion
    // True while the popout window is visible (including its closing animation).
    property bool hostActive: false
    property real contentOpacity: 1
    // Gallery mode: fixed demo data, no provider process and no device access.
    property bool preview: false
    property var demoEntries: []

    readonly property var surfaces: ["menu", "quicksettings", "notifications", "session"]
    property string current: ""
    readonly property bool owned: current !== ""
    // Preferred size per surface; PopoutGeometry bounds it to the screen.
    readonly property real targetWidth: current === "session" ? Wysun.Appearance.spaceXl * 15
        : current === "notifications" ? Wysun.Appearance.spaceXl * 22 : Wysun.Appearance.spaceXl * 19
    readonly property real targetHeight: current === "session" ? Wysun.Appearance.spaceXl * 21
        : Wysun.Appearance.spaceXl * 27

    function ownsSurface(kind) { return surfaces.indexOf(kind) >= 0; }

    Connections {
        target: root.controller
        function onSurfaceChanged() {
            var kind = root.controller.surface;
            // Closing ("") keeps the content for the exit animation; another popout takes over.
            if (root.ownsSurface(kind)) root.current = kind;
            else if (kind !== "") root.current = "";
        }
    }
    onHostActiveChanged: if (!hostActive) current = ""
    Component.onCompleted: if (ownsSurface(controller.surface)) current = controller.surface

    visible: owned
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.materialMid
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.materialEdge

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }

    Loader {
        id: loader
        anchors.fill: parent
        opacity: root.contentOpacity
        active: root.hostActive && root.owned
        sourceComponent: root.current === "notifications" ? notifications
            : root.current === "session" ? session : quickSettings
        onLoaded: item.forceActiveFocus()
    }

    Component {
        id: quickSettings
        QuickSettings { controller: root.controller; motion: root.motion; preview: root.preview }
    }
    Component {
        id: notifications
        Notifications.NotificationCenter { controller: root.controller; motion: root.motion; preview: root.preview; demoEntries: root.demoEntries }
    }
    Component {
        id: session
        Session.SessionMenu { controller: root.controller; motion: root.motion; preview: root.preview }
    }
}
