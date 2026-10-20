// Adaptado de caelestia-dots/shell/modules/osd/Content.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Brief, passive OSD: it never takes keyboard focus and never presents a
// second control surface. The host owns the timeout.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

Components.StyledRect {
    id: root

    required property var motion
    property string mode: "volume"
    property real volume: 0
    property bool muted: false
    property real sourceVolume: 0
    property bool sourceMuted: false
    property real brightness: 0
    property bool audioAvailable: true
    property bool brightnessAvailable: true

    readonly property bool showVolume: mode === "volume" || mode === "mute"
    readonly property bool showSource: mode === "source-volume" || mode === "source-mute"
    readonly property bool showBrightness: mode === "brightness"
    readonly property string headerGlyph: showVolume ? volumeGlyph
        : showSource ? (sourceMuted ? "mic_off" : "mic")
        : (brightness < 0.5 ? "brightness_low" : "brightness_high")
    readonly property string volumeGlyph: muted ? "volume_off" : (volume <= 0.001 ? "volume_mute" : "volume_up")
    readonly property string volumeLabel: !audioAvailable ? "Audio no disponible" : muted ? "Silencio" : "Volumen"
    readonly property string sourceLabel: !audioAvailable ? "Micrófono no disponible" : sourceMuted ? "Micrófono silenciado" : "Micrófono"
    readonly property string brightnessLabel: !brightnessAvailable ? "Brillo no disponible" : "Brillo"

    implicitWidth: Math.max(300, layout.implicitWidth + Wysun.Appearance.spaceXl * 2)
    implicitHeight: layout.implicitHeight + Wysun.Appearance.spaceL * 2
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.materialMid
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.materialEdge

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceS

        Row {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                name: root.headerGlyph
                size: Wysun.Appearance.fontTitle
                color: Wysun.Appearance.accent
            }
            Components.StyledText {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - Wysun.Appearance.fontTitle - Wysun.Appearance.spaceS
                text: root.showVolume ? root.volumeLabel : root.showSource ? root.sourceLabel : root.brightnessLabel
                color: Wysun.Appearance.textStrong
                font.pixelSize: Wysun.Appearance.fontHeading
                elide: Text.ElideRight
                motion: root.motion
            }
        }

        RowLayout {
            visible: root.showVolume
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: root.audioAvailable ? Math.round(root.volume * 100) + "%" : "Sin PipeWire"
                color: root.audioAvailable ? Wysun.Appearance.text : Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontBody
                motion: root.motion
            }
        }
        LevelBar {
            visible: root.showVolume
            Layout.fillWidth: true
            value: root.volume
            available: root.audioAvailable
            motion: root.motion
        }

        RowLayout {
            visible: root.showSource
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: root.audioAvailable ? Math.round(root.sourceVolume * 100) + "%" : "Sin PipeWire"
                color: root.audioAvailable ? Wysun.Appearance.text : Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontBody
                motion: root.motion
            }
        }
        LevelBar {
            visible: root.showSource
            Layout.fillWidth: true
            value: root.sourceVolume
            available: root.audioAvailable
            motion: root.motion
        }

        RowLayout {
            visible: root.showBrightness
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: root.brightnessAvailable ? Math.round(root.brightness * 100) + "%" : "Sin backlight"
                color: root.brightnessAvailable ? Wysun.Appearance.text : Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontBody
                motion: root.motion
            }
        }
        LevelBar {
            visible: root.showBrightness
            Layout.fillWidth: true
            value: root.brightness
            available: root.brightnessAvailable
            motion: root.motion
        }
    }
}
