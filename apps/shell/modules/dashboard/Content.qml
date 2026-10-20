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
    property int currentIndex: 0

    implicitWidth: Wysun.Appearance.spaceXl * 34
    implicitHeight: Wysun.Appearance.spaceXl * 26
    focus: true

    Keys.onPressed: event => {
        if (event.key === Qt.Key_Right && (event.modifiers & Qt.ControlModifier)) {
            root.currentIndex = Math.min(root.tabCount - 1, root.currentIndex + 1);
            event.accepted = true;
        } else if (event.key === Qt.Key_Left && (event.modifiers & Qt.ControlModifier)) {
            root.currentIndex = Math.max(0, root.currentIndex - 1);
            event.accepted = true;
        }
    }

    readonly property int tabCount: 4

    Tabs {
        id: tabs
        anchors { left: parent.left; right: parent.right; top: parent.top }
        motion: root.motion
        currentIndex: root.currentIndex
        onSelected: index => root.currentIndex = index
    }

    Flickable {
        id: view
        anchors { top: tabs.bottom; bottom: parent.bottom; left: parent.left; right: parent.right; topMargin: Wysun.Appearance.spaceL }
        clip: true
        contentWidth: width
        contentHeight: pane.item ? pane.item.implicitHeight : 0
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick

        ScrollBar.vertical: ScrollBar {
            id: scroll
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle {
                implicitWidth: Wysun.Appearance.spaceXs
                radius: width / 2
                color: scroll.pressed ? Wysun.Appearance.accent : Wysun.Appearance.lineStrong
            }
            background: Item {}
        }

        Loader {
            id: pane
            width: Math.max(0, view.width - Wysun.Appearance.spaceM)
            sourceComponent: root.currentIndex === 0 ? dashComponent
                : root.currentIndex === 1 ? mediaComponent
                : root.currentIndex === 2 ? performanceComponent
                : workspaceComponent
            onLoaded: {
                view.contentY = 0;
                opacity = 0;
                fade.restart();
            }
            onSourceComponentChanged: opacity = 0
            Components.Anim {
                id: fade
                target: pane
                property: "opacity"
                to: 1
                motion: root.motion
                type: Components.Anim.DefaultEffects
            }
        }
    }

    Component {
        id: dashComponent
        Dash { metrics: root.metrics; media: root.media; controller: root.controller; motion: root.motion; monitorName: root.monitorName }
    }
    Component {
        id: mediaComponent
        Media { media: root.media; controller: root.controller; motion: root.motion }
    }
    Component {
        id: performanceComponent
        Performance { metrics: root.metrics; motion: root.motion }
    }
    Component {
        id: workspaceComponent
        Workspaces { workspaces: root.workspaces; windows: root.windows; controller: root.controller; motion: root.motion }
    }
}
