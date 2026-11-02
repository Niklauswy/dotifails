// The status line (F-27): «14 elementos · 3 seleccionados» (or «2 de 14 elementos» while filtering) and the free
// space of the disk; an operation in progress shows its text and a bar here.
import QtQuick
import WysunM3

Item {
    id: root

    property var model                      // FolderModel
    property string free
    property string operation               // «Copiando 3 de 12»
    property real progress: -1              // 0…1, or < 0 for none
    readonly property string text: {
        if (!model)
            return "";
        const shown = model.count, total = model.total, chosen = model.selectionCount;
        const items = n => n === 1 ? "1 elemento" : n + " elementos";
        let line = shown === total ? items(total) : shown + " de " + items(total);
        if (chosen > 0)
            line += chosen === 1 ? " · 1 seleccionado" : " · " + chosen + " seleccionados";
        return line;
    }

    implicitHeight: FilesMetrics.statusHeight

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.m3outlineVariant
    }
    Label {
        objectName: "statusText"
        anchors.left: parent.left
        anchors.leftMargin: FilesMetrics.pagePadding
        anchors.verticalCenter: parent.verticalCenter
        role: "label.medium"
        text: root.text
        color: Theme.m3onSurfaceVariant
    }
    Row {
        anchors.centerIn: parent
        visible: root.operation !== ""
        spacing: Theme.spacing.small ?? 0

        Label {
            objectName: "operationText"
            anchors.verticalCenter: parent.verticalCenter
            role: "label.medium"
            text: root.operation
            color: Theme.m3onSurface
        }
        LinearProgress {
            anchors.verticalCenter: parent.verticalCenter
            width: FilesMetrics.filterWidth / 2
            value: Math.max(0, root.progress)
            indeterminate: root.progress < 0
        }
    }
    Label {
        objectName: "freeText"
        anchors.right: parent.right
        anchors.rightMargin: FilesMetrics.pagePadding
        anchors.verticalCenter: parent.verticalCenter
        role: "label.medium"
        text: root.free
        color: Theme.m3onSurfaceVariant
    }
}
