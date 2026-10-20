// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import Quickshell
import "../../" as Wysun
import "../../services" as Services
import "../../components" as Components
import "services" as LocalServices
import "Logic.js" as Logic

Components.StyledRect {
    id: root
    required property var controller
    required property var motion
    property bool active: controller.surface === "launcher"
    property string errorMessage: ""
    property alias apps: apps
    property alias actions: actions
    property alias schemes: schemes
    property alias variants: variants
    property alias content: content

    signal copied(string result)

    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.materialMid
    visible: active
    clip: true

    function fail(message) {
        errorMessage = message;
        if (controller.surface !== "launcher" && controller.show) controller.show("launcher");
    }

    function activate(row) {
        if (!row) return;
        if (row.completion) {
            content.query = row.completion;
            content.searchItem.forceActiveFocus();
            return;
        }
        switch (row.kind) {
        case "apps":
            apps.launch(row.entry);
            break;
        case "actions":
            actions.launch(row.id);
            break;
        case "scheme":
            if (!schemes.busy) schemes.select(row.id);
            break;
        case "variant":
            if (!schemes.busy) schemes.selectVariant(row.id);
            break;
        case "wallpaper":
            if (!schemes.busy) schemes.selectWallpaper(row.path);
            break;
        case "calc":
            if (row.invalid) {
                fail(row.description);
                return;
            }
            Quickshell.clipboardText = row.value;
            copied(row.value);
            controller.close();
            break;
        }
    }

    onActiveChanged: {
        if (active) {
            errorMessage = "";
            schemes.reload();
            Qt.callLater(content.reset);
        }
    }
    Component.onCompleted: {
        if (active) {
            schemes.reload();
            Qt.callLater(content.reset);
        }
    }

    Services.Apps {
        id: apps
        onAccepted: root.controller.close()
        onFailed: message => root.fail(message)
    }
    Services.Actions {
        id: actions
        onAccepted: root.controller.close()
        onFailed: message => root.fail(message)
    }
    Services.Schemes {
        id: schemes
        onFinished: root.controller.close()
        onFailed: message => root.fail(message)
    }
    LocalServices.M3Variants { id: variants }

    Content {
        id: content
        anchors.fill: parent
        launcher: root
    }
}
