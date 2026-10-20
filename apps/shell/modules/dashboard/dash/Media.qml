// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Media.qml; services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../" as Dashboard
import "../Logic.js" as Logic

// Compact "now playing" card for Inicio. With no player it invites the user to
// open Wysun Music instead of showing an empty control row.
Dashboard.Card {
    id: root
    property var media: null
    property var controller: null
    property var motion
    readonly property var player: media ? media.active : null
    implicitHeight: layout.implicitHeight + padding * 2

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Wysun.Appearance.spaceS
        RowLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceM
            Components.StyledRect {
                Layout.preferredWidth: Wysun.Appearance.spaceXl * 3
                Layout.preferredHeight: Layout.preferredWidth
                radius: Wysun.Appearance.radiusM
                color: Wysun.Appearance.selection
                clip: true
                Image {
                    id: cover
                    anchors.fill: parent
                    source: root.media ? root.media.artwork : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: false
                }
                Components.MaterialIcon {
                    anchors.centerIn: parent
                    visible: cover.status !== Image.Ready
                    name: "music_note"
                    size: Wysun.Appearance.fontTitle
                    color: Wysun.Appearance.selectionText
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Components.StyledText {
                    Layout.fillWidth: true
                    text: root.player ? root.media.title : "Sin reproducción"
                    font.pixelSize: Wysun.Appearance.fontHeading
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
                Components.StyledText {
                    Layout.fillWidth: true
                    text: root.player ? (root.media.artist || Logic.playerLabel(root.player)) : "Tu música, a un clic"
                    color: Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                    elide: Text.ElideRight
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: Wysun.Appearance.spaceS
            Dashboard.IconButton {
                glyph: "skip_previous"; label: "Anterior"; motion: root.motion
                enabled: !!root.player && !!root.player.canControl && !!root.player.canGoPrevious
                onClicked: root.media.previous()
            }
            Dashboard.IconButton {
                glyph: root.player && root.player.isPlaying ? "pause" : "play_arrow"
                label: root.player && root.player.isPlaying ? "Pausar" : "Reproducir"
                prominent: true; motion: root.motion
                enabled: !!root.player && !!root.player.canControl && !!root.player.canTogglePlaying
                onClicked: root.media.toggle()
            }
            Dashboard.IconButton {
                glyph: "skip_next"; label: "Siguiente"; motion: root.motion
                enabled: !!root.player && !!root.player.canControl && !!root.player.canGoNext
                onClicked: root.media.next()
            }
        }
    }
}
