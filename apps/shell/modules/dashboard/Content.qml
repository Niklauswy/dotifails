// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Content.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

FocusScope {
    id: root
    property var motion
    property var controller: null
    property var metrics: null
    property var media: null
    property var workspaces: []
    property var windows: []
    property string monitorName: ""
    property alias currentIndex: tabs.currentIndex
    implicitWidth: Wysun.Appearance.spaceXl * 34
    implicitHeight: Wysun.Appearance.spaceXl * 26
    Keys.onPressed: event => {
        if (event.modifiers & Qt.ControlModifier && (event.key === Qt.Key_Right || event.key === Qt.Key_Left)) {
            currentIndex = Math.max(0, Math.min(3, currentIndex + (event.key === Qt.Key_Right ? 1 : -1)));
            event.accepted = true;
        }
    }
    Tabs {
        id: tabs
        anchors { left: parent.left; right: parent.right; top: parent.top }
        motion: root.motion
    }
    // One active pane, matching upstream's deferred-loader policy. Scroll bars
    // keep tall performance/workspace lists reachable on small displays.
    Flickable {
        id: view
        anchors { top: tabs.bottom; bottom: parent.bottom; left: parent.left; right: parent.right; topMargin: Wysun.Appearance.spaceL }
        clip: true
        contentWidth: width
        contentHeight: pane.item?.implicitHeight || 0
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        ScrollBar.vertical: ScrollBar {
            id: scroll
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle { implicitWidth: Wysun.Appearance.spaceXs; radius: width/2; color: scroll.pressed ? Wysun.Appearance.accent : Wysun.Appearance.lineStrong }
            background: Item {}
        }
        Loader {
            id: pane
            width: Math.max(0, view.width - Wysun.Appearance.spaceM)
            sourceComponent: [dashComponent, mediaComponent, performanceComponent, workspaceComponent][root.currentIndex]
            onLoaded: { view.contentY = 0; }
            opacity: 1
            // Retarget the existing fade when tabs change quickly.
            onSourceComponentChanged: { opacity = 0; fade.restart(); }
            Components.Anim { id: fade; target: pane; property: "opacity"; to: 1; motion: root.motion; type: Components.Anim.DefaultEffects }
        }
    }
    Component { id: dashComponent; Dash { metrics: root.metrics; media: root.media; controller: root.controller; motion: root.motion; monitorName: root.monitorName } }
    Component { id: mediaComponent; Media { media: root.media; controller: root.controller; motion: root.motion } }
    Component { id: performanceComponent; Performance { metrics: root.metrics; motion: root.motion } }
    Component { id: workspaceComponent; Workspaces { workspaces: root.workspaces; windows: root.windows; controller: root.controller; motion: root.motion } }
}
