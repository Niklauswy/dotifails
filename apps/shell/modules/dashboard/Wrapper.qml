// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

Item {
    id: root
    required property var motion
    property var controller: null
    property string monitorName: ""
    property bool live: true
    property bool sampling: visible
    property var fixtureProviders: null
    readonly property var providers: live ? liveProvider.item : fixtureProviders
    property alias currentIndex: content.currentIndex

    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight

    Loader {
        id: liveProvider
        active: root.live && root.sampling
        source: "LiveProviders.qml"
        onLoaded: {
            item.enabled = Qt.binding(function() { return root.sampling; });
            item.monitorName = Qt.binding(function() { return root.monitorName; });
        }
    }

    Content {
        id: content
        anchors.fill: parent
        motion: root.motion
        controller: root.controller
        monitorName: root.monitorName
        metrics: root.providers ? root.providers.metrics : null
        media: root.providers ? root.providers.media : null
        workspaces: root.providers ? root.providers.workspaces : []
        windows: root.providers ? root.providers.windows : []
    }
}
