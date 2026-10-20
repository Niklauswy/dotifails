// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// modules/lock/Media.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt. Wysun no pinta portada,
// imágenes, notificaciones ni metadatos extendidos; la tarjeta es opt-in,
// local y solo muestra título/artista del reproductor MPRIS activo.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../../" as Wysun
import "../../components" as Components

Item {
    id: root

    property bool mediaEnabled: false
    property var motion: null
    readonly property var player: Mpris.players.values.length > 0 ? Mpris.players.values[0] : null
    readonly property string title: player && player.trackTitle ? String(player.trackTitle) : ""
    readonly property string artist: player && player.trackArtist ? String(player.trackArtist) : ""
    readonly property bool available: root.mediaEnabled && root.player !== null && (root.title !== "" || root.artist !== "")
    readonly property bool playing: root.player !== null && root.player.isPlaying === true

    visible: root.available
    implicitHeight: root.available ? card.implicitHeight : 0

    function activate(action) {
        if (!root.player || !root.player.canControl) return;
        if (action === "previous" && root.player.canGoPrevious) root.player.previous();
        else if (action === "next" && root.player.canGoNext) root.player.next();
        else if (action === "toggle" && root.player.canTogglePlaying) root.player.togglePlaying();
    }

    Rectangle {
        id: card
        width: parent.width
        implicitHeight: content.implicitHeight + Wysun.Appearance.spaceM * 2
        radius: Wysun.Appearance.radiusControl
        color: Wysun.Appearance.surface
        border.width: Wysun.Appearance.borderWidth
        border.color: Wysun.Appearance.line

        ColumnLayout {
            id: content
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: Wysun.Appearance.spaceM
            spacing: Wysun.Appearance.spaceXs

            Components.StyledText {
                Layout.fillWidth: true
                text: root.title || "Reproduciendo"
                color: Wysun.Appearance.text
                font.pixelSize: Wysun.Appearance.fontBody
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                motion: root.motion
            }
            Components.StyledText {
                Layout.fillWidth: true
                visible: root.artist !== ""
                text: root.artist
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontSmall
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                motion: root.motion
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Wysun.Appearance.spaceXs
                spacing: Wysun.Appearance.spaceS

                Repeater {
                    model: [
                        { action: "previous", label: "Anterior", enabled: root.player && root.player.canGoPrevious === true },
                        { action: "toggle", label: root.playing ? "Pausa" : "Reproducir", enabled: root.player && root.player.canTogglePlaying === true },
                        { action: "next", label: "Siguiente", enabled: root.player && root.player.canGoNext === true }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        implicitWidth: buttonLabel.implicitWidth + Wysun.Appearance.spaceL * 2
                        implicitHeight: buttonLabel.implicitHeight + Wysun.Appearance.spaceS * 1.5
                        radius: height / 2
                        color: mouse.pressed ? Wysun.Appearance.pressed
                             : (mouse.containsMouse ? Wysun.Appearance.hover : Wysun.Appearance.well)
                        opacity: modelData.enabled ? 1 : 0.45
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.label
                        Accessible.onPressAction: root.activate(modelData.action)

                        Text {
                            id: buttonLabel
                            anchors.centerIn: parent
                            text: modelData.label
                            color: Wysun.Appearance.text
                            font.family: Wysun.Appearance.fontFamily
                            font.pixelSize: Wysun.Appearance.fontSmall
                        }
                        MouseArea {
                            id: mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: modelData.enabled
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activate(modelData.action)
                        }
                    }
                }
            }
        }
    }
}
