pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// SSH connections: saved profiles plus the hosts declared in ~/.ssh/config.
PageBase {
    id: root

    property var rows: []
    property string status: ""
    property bool failed: false

    function load(): void {
        DesktopBridge.call("ssh.state", {}, data => root.rows = data.rows, message => {
            root.status = message;
            root.failed = true;
        });
    }

    function edit(row: var): void {
        nState.selectedSsh = row;
        nState.openSubPage(1);
    }

    title: "SSH"
    Component.onCompleted: load()
    onVisibleChanged: if (visible && rows.length)
        load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Conexiones guardadas"
        }

        Repeater {
            model: root.rows

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: false
                icon: modelData.imported ? "dns" : "terminal"
                text: modelData.name
                subtext: (modelData.user ? modelData.user + "@" : "") + modelData.host + " · " + modelData.port + (modelData.imported ? " · ~/.ssh/config" : "")
                trailingIcon: "chevron_right"
                onClicked: root.edit(modelData)
            }
        }

        RowButton {
            first: root.rows.length === 0
            last: true
            icon: "add"
            text: "Añadir conexión"
            subtext: "Host, usuario y puerto"
            onClicked: root.edit(null)
        }

        StatusLine {
            text: root.status
            error: root.failed
        }
    }
}
