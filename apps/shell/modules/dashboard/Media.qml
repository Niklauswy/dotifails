// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Media.qml; modules/dashboard/media/Details.qml; services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "Logic.js" as Logic

ColumnLayout {
    id: root
    property var media: null
    property var controller: null
    property var motion
    readonly property var player: media?.active || null
    spacing: Wysun.Appearance.spaceL
    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceXl
        Components.StyledRect {
            Layout.preferredWidth: Math.min(root.width * .34, Wysun.Appearance.spaceXl * 9)
            Layout.preferredHeight: width
            radius: Wysun.Appearance.radiusL
            color: Wysun.Appearance.selection
            clip: true
            Image { id: cover; anchors.fill: parent; source: root.media?.artwork || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true }
            Components.MaterialIcon { anchors.centerIn: parent; visible: cover.status !== Image.Ready; name: "dashboard"; size: Wysun.Appearance.fontTitle * 2; color: Wysun.Appearance.selectionText }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceM
            Components.StyledText { Layout.fillWidth: true; text: root.player ? root.media.title : "Sin reproducción"; font.pixelSize: Wysun.Appearance.fontTitle; wrapMode: Text.WordWrap }
            Components.StyledText { Layout.fillWidth: true; text: root.player ? [root.media.artist, root.media.album].filter(Boolean).join(" · ") : "Abre Wysun Music o un reproductor compatible."; color: Wysun.Appearance.muted; font.pixelSize: Wysun.Appearance.fontBody; wrapMode: Text.WordWrap }
            Components.StyledText { visible: !!root.player; Layout.fillWidth: true; text: root.player?.identity || "Reproductor"; font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        Components.ActionButton { Layout.fillWidth: true; implicitWidth: 0; glyph: ""; motion: root.motion; label: "Anterior"; enabled: !!root.player?.canControl && !!root.player?.canGoPrevious; onClicked: root.media.previous() }
        Components.ActionButton { Layout.fillWidth: true; implicitWidth: 0; glyph: ""; motion: root.motion; selected: true; label: root.player?.isPlaying ? "Pausar" : "Reproducir"; enabled: !!root.player?.canControl && !!root.player?.canTogglePlaying; onClicked: root.media.toggle() }
        Components.ActionButton { Layout.fillWidth: true; implicitWidth: 0; glyph: ""; motion: root.motion; label: "Siguiente"; enabled: !!root.player?.canControl && !!root.player?.canGoNext; onClicked: root.media.next() }
    }
    Slider {
        id: seek
        Layout.fillWidth: true
        from: 0
        to: Math.max(1, root.player?.length || 0)
        value: root.player?.position || 0
        enabled: !!root.player?.canControl && !!root.player?.canSeek && !!root.player?.lengthSupported && !!root.player?.positionSupported
        Accessible.name: "Posición de reproducción"
        onMoved: if (root.player && enabled) root.player.position = value
        background: Rectangle { x: seek.leftPadding; y: seek.topPadding + (seek.availableHeight-height)/2; implicitHeight: Wysun.Appearance.spaceXs; width: seek.availableWidth; radius: height/2; color: Wysun.Appearance.line; Rectangle { width: seek.visualPosition*parent.width; height: parent.height; radius: height/2; color: Wysun.Appearance.accent } }
        handle: Rectangle { x: seek.leftPadding + seek.visualPosition*(seek.availableWidth-width); y: seek.topPadding + (seek.availableHeight-height)/2; implicitWidth: Wysun.Appearance.spaceL; implicitHeight: implicitWidth; radius: width/2; color: seek.enabled ? Wysun.Appearance.accent : Wysun.Appearance.disabled; border.width: seek.activeFocus ? Wysun.Appearance.focusWidth : 0; border.color: Wysun.Appearance.focus }
    }
    Components.StyledText { text: Logic.timestamp(root.player?.position) + " / " + Logic.timestamp(root.player?.length); font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted }
    Flow {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        Repeater {
            model: root.media?.players || []
            delegate: Components.ActionButton { required property var modelData; glyph: ""; motion: root.motion; label: modelData.identity || "Reproductor"; selected: root.player === modelData; onClicked: root.media.select(modelData) }
        }
    }
    Components.ActionButton { Layout.fillWidth: true; motion: root.motion; glyph: "dashboard"; label: "Abrir Wysun Music"; enabled: !!root.controller; onClicked: root.controller.launch("music") }
}
