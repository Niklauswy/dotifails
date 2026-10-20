// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/osd/Content.qml, modules/bar/popouts/AudioPopout.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// PipeWire is observed directly; the Python provider is not used for audio or
// brightness, so multimedia keys and external changes share the same source.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

SectionCard {
    id: root

    property var previewData: null
    readonly property bool demo: previewData !== null
    readonly property real level: demo ? (previewData.volume || 0) : audio.volume
    readonly property bool muted: demo ? (previewData.muted || false) : audio.muted
    readonly property real micLevel: demo ? (previewData.sourceVolume || 0) : audio.sourceVolume
    readonly property bool micMuted: demo ? (previewData.sourceMuted || false) : audio.sourceMuted
    readonly property real lightLevel: demo ? (previewData.brightness || 0) : brightness.value
    readonly property bool audioReady: demo || audio.available
    readonly property bool brightnessReady: demo || brightness.available

    title: "Sonido y pantalla"
    subtitle: demo ? "Vista previa" : (audio.sinkName.length > 0 ? audio.sinkName : "Salida predeterminada")

    Services.Audio { id: audio; enabled: !root.demo }
    Services.Brightness { id: brightness; enabled: !root.demo }

    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        Components.StyledText {
            Layout.fillWidth: true
            text: !root.audioReady ? audio.error : root.muted ? "Audio silenciado" : "Volumen · " + Math.round(root.level * 100) + "%"
            color: root.audioReady ? Wysun.Appearance.text : Wysun.Appearance.muted
            font.pixelSize: Wysun.Appearance.fontBody
            wrapMode: Text.WordWrap
            motion: root.motion
        }
        ControlButton {
            objectName: "muteButton"
            motion: root.motion
            glyph: root.muted ? "volume_off" : "volume_up"
            label: root.muted ? "Activar audio" : "Silenciar"
            description: "Silencia o reactiva la salida predeterminada de PipeWire"
            enabled: root.audioReady && !root.demo
            onClicked: audio.toggleMuted()
        }
    }
    LevelSlider {
        objectName: "volumeSlider"
        Layout.fillWidth: true
        value: root.level * 100
        enabled: root.audioReady && !root.demo
        Accessible.name: "Volumen de salida"
        Accessible.description: "0 a 100 por ciento"
        onMoved: {
            if (!root.demo) audio.setVolume(value / 100);
            value = Qt.binding(function() { return root.level * 100; });
        }
    }

    Components.StyledText {
        Layout.fillWidth: true
        text: !root.audioReady ? "Micrófono no disponible" : root.micMuted ? "Micrófono silenciado" : "Micrófono · " + Math.round(root.micLevel * 100) + "%"
        color: root.audioReady ? Wysun.Appearance.muted : Wysun.Appearance.disabled
        font.pixelSize: Wysun.Appearance.fontSmall
        wrapMode: Text.WordWrap
        motion: root.motion
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        LevelSlider {
            objectName: "microphoneSlider"
            Layout.fillWidth: true
            value: root.micLevel * 100
            enabled: root.audioReady && !root.demo
            Accessible.name: "Volumen del micrófono"
            onMoved: {
                if (!root.demo) audio.setSourceVolume(value / 100);
                value = Qt.binding(function() { return root.micLevel * 100; });
            }
        }
        ControlButton {
            objectName: "microphoneMuteButton"
            motion: root.motion
            label: root.micMuted ? "Activar micrófono" : "Silenciar micrófono"
            enabled: root.audioReady && !root.demo
            onClicked: audio.toggleSourceMuted()
        }
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Wysun.Appearance.borderWidth
        color: Wysun.Appearance.line
    }

    Components.StyledText {
        Layout.fillWidth: true
        text: !root.brightnessReady ? brightness.error : "Brillo · " + Math.round(root.lightLevel * 100) + "%"
        color: root.brightnessReady ? Wysun.Appearance.text : Wysun.Appearance.muted
        font.pixelSize: Wysun.Appearance.fontBody
        wrapMode: Text.WordWrap
        motion: root.motion
    }
    LevelSlider {
        objectName: "brightnessSlider"
        Layout.fillWidth: true
        from: 5
        value: root.lightLevel * 100
        enabled: root.brightnessReady && !root.demo
        Accessible.name: "Brillo de pantalla"
        Accessible.description: "5 a 100 por ciento"
        onMoved: {
            if (!root.demo) brightness.setBrightness(value / 100);
            value = Qt.binding(function() { return root.lightLevel * 100; });
        }
    }
    Components.StyledText {
        visible: !root.brightnessReady && brightness.error.length > 0
        Layout.fillWidth: true
        text: brightness.error
        color: Wysun.Appearance.disabled
        font.pixelSize: Wysun.Appearance.fontSmall
        wrapMode: Text.WordWrap
        motion: root.motion
    }
}
