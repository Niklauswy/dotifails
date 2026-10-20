// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/AudioPopout.qml; modules/osd/Content.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services
ColumnLayout {
    id: root
    required property var hub
    required property var motion
    spacing: Wysun.Appearance.spaceS
    Services.Audio { id: audio; hub: root.hub }
    Services.Brightness { id: brightness; hub: root.hub }
    RowLayout {
        Layout.fillWidth: true
        Components.StyledText {
            Layout.fillWidth: true
            text: audio.available ? (audio.muted ? "Audio silenciado" : "Volumen · " + Math.round(audio.volume * 100) + "%") : audio.error
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
        ControlButton {
            objectName: "muteButton"
            motion: root.motion
            glyph: audio.muted ? "volume_off" : "volume_up"
            label: audio.muted ? "Activar audio" : "Silenciar"
            enabled: audio.available && !root.hub.busy
            onClicked: audio.toggleMuted()
        }
    }
    LevelSlider {
        objectName: "volumeSlider"
        Layout.fillWidth: true
        value: audio.volume * 100
        enabled: audio.available && !root.hub.busy
        Accessible.name: "Volumen"
        onMoved: if (!pressed) audio.setVolume(value / 100)
        onPressedChanged: if (!pressed && enabled) audio.setVolume(value / 100)
    }
    Components.StyledText {
        Layout.fillWidth: true
        text: brightness.available ? "Brillo · " + Math.round(brightness.brightness * 100) + "%" : brightness.error
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }
    LevelSlider {
        objectName: "brightnessSlider"
        Layout.fillWidth: true
        from: 5
        value: brightness.brightness * 100
        enabled: brightness.available && !root.hub.busy
        Accessible.name: "Brillo de pantalla"
        onMoved: if (!pressed) brightness.setBrightness(value / 100)
        onPressedChanged: if (!pressed && enabled) brightness.setBrightness(value / 100)
    }
}
