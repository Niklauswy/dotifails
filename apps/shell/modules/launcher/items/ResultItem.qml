// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/items/{AppItem,ActionItem,CalcItem,SchemeItem,VariantItem,WallpaperItem}.qml,
// commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../../../" as Wysun
import "../../../components" as Components

Button {
    id: root
    required property var row
    property var motion
    property bool selected: false

    implicitHeight: Wysun.Appearance.spaceXl * 2 + Wysun.Appearance.spaceM
    padding: Wysun.Appearance.spaceS
    Accessible.name: row.name + (row.description ? ". " + row.description : "")
    activeFocusOnTab: false

    background: Components.StyledRect {
        motion: root.motion
        radius: Wysun.Appearance.radiusM
        color: root.down ? Wysun.Appearance.pressed
            : root.selected ? Wysun.Appearance.selection
            : root.hovered ? Wysun.Appearance.hover : "transparent"
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth : 0
        border.color: Wysun.Appearance.focus
    }

    contentItem: RowLayout {
        spacing: Wysun.Appearance.spaceM
        Image {
            Layout.preferredWidth: Wysun.Appearance.spaceXl + Wysun.Appearance.spaceM
            Layout.preferredHeight: Wysun.Appearance.spaceXl + Wysun.Appearance.spaceM
            visible: root.row.kind === "apps" || root.row.kind === "wallpaper"
            source: root.row.kind === "apps"
                ? Quickshell.iconPath(root.row.entry.icon, "image-missing")
                : root.row.path ? "file://" + encodeURI(root.row.path).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
            sourceSize.width: Wysun.Appearance.spaceXl * 4
            sourceSize.height: Wysun.Appearance.spaceXl * 3
            asynchronous: true
            cache: false
            fillMode: Image.PreserveAspectFit
            Accessible.ignored: true
        }
        Components.MaterialIcon {
            visible: root.row.kind !== "apps" && root.row.kind !== "wallpaper"
            name: root.row.id === "power" || root.row.id === "lock" ? "power_settings_new" : "dashboard"
            size: Wysun.Appearance.fontTitle
            color: root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.muted
        }
        ColumnLayout {
            spacing: Wysun.Appearance.spaceXs / 2
            Layout.fillWidth: true
            Components.StyledText {
                Layout.fillWidth: true
                text: root.row.name || ""
                font.pixelSize: Wysun.Appearance.fontBody
                color: root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.textStrong
                elide: Text.ElideRight
            }
            Components.StyledText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.row.description || ""
                font.pixelSize: Wysun.Appearance.fontSmall
                color: root.row.invalid ? Wysun.Appearance.danger
                    : root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.muted
                elide: Text.ElideRight
            }
        }
        Components.StyledText {
            visible: root.row.current === true
            text: "Activo"
            font.pixelSize: Wysun.Appearance.fontSmall
            color: root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.accent
        }
    }
}
