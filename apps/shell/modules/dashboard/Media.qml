// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Media.qml; modules/dashboard/media/Details.qml; services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "Logic.js" as Logic

// "Música": the active MPRIS player, offline. Artwork only comes from file://
// URLs published by the player; there is no remote lookup.
ColumnLayout {
    id: root
    property var media: null
    property var controller: null
    property var motion
    readonly property var player: media ? media.active : null
    readonly property bool canSeek: !!player && !!player.canControl && !!player.canSeek
        && !!player.lengthSupported && !!player.positionSupported
    spacing: Wysun.Appearance.spaceL

    // MPRIS positions do not notify while playing; ask for a fresh read.
    Timer {
        interval: 1000
        repeat: true
        running: root.visible && !!root.player && !!root.player.isPlaying
        onTriggered: if (root.player && typeof root.player.positionChanged === "function") root.player.positionChanged()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceXl
        Components.StyledRect {
            Layout.preferredWidth: Math.min(root.width * 0.34, Wysun.Appearance.spaceXl * 9)
            Layout.preferredHeight: Layout.preferredWidth
            radius: Wysun.Appearance.radiusL
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
                size: Wysun.Appearance.fontTitle * 2
                color: Wysun.Appearance.selectionText
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: root.player ? root.media.title : "Sin reproducción"
                font.pixelSize: Wysun.Appearance.fontTitle
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                Accessible.role: Accessible.Heading
            }
            Components.StyledText {
                Layout.fillWidth: true
                text: root.player ? [root.media.artist, root.media.album].filter(Boolean).join(" · ")
                    : "Abre Wysun Music o un reproductor compatible."
                color: Wysun.Appearance.muted
                font.pixelSize: Wysun.Appearance.fontBody
                wrapMode: Text.WordWrap
            }
            Components.StyledText {
                visible: !!root.player
                Layout.fillWidth: true
                text: Logic.playerLabel(root.player)
                font.pixelSize: Wysun.Appearance.fontSmall
                color: Wysun.Appearance.accent
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceXs
        Slider {
            id: seek
            Layout.fillWidth: true
            from: 0
            to: Math.max(1, root.player ? (root.player.length || 0) : 0)
            value: root.player ? (root.player.position || 0) : 0
            enabled: root.canSeek
            focusPolicy: Qt.TabFocus
            Accessible.name: "Posición de reproducción"
            onMoved: if (root.canSeek) root.player.position = value
            background: Rectangle {
                x: seek.leftPadding
                y: seek.topPadding + (seek.availableHeight - height) / 2
                implicitHeight: Wysun.Appearance.spaceXs
                height: implicitHeight
                width: seek.availableWidth
                radius: height / 2
                color: Wysun.Appearance.line
                Rectangle {
                    width: seek.visualPosition * parent.width
                    height: parent.height
                    radius: height / 2
                    color: seek.enabled ? Wysun.Appearance.accent : Wysun.Appearance.disabled
                }
            }
            handle: Rectangle {
                x: seek.leftPadding + seek.visualPosition * (seek.availableWidth - width)
                y: seek.topPadding + (seek.availableHeight - height) / 2
                implicitWidth: Wysun.Appearance.spaceL
                implicitHeight: implicitWidth
                radius: width / 2
                color: seek.enabled ? Wysun.Appearance.accent : Wysun.Appearance.disabled
                border.width: seek.activeFocus ? Wysun.Appearance.focusWidth * 2 : 0
                border.color: Wysun.Appearance.focus
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Components.StyledText {
                text: Logic.timestamp(root.player ? root.player.position : undefined)
                font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted
            }
            Item { Layout.fillWidth: true }
            Components.StyledText {
                text: Logic.timestamp(root.player ? root.player.length : undefined)
                font.pixelSize: Wysun.Appearance.fontSmall; color: Wysun.Appearance.muted
            }
        }
    }

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: Wysun.Appearance.spaceM
        IconButton {
            glyph: "skip_previous"; label: "Anterior"; motion: root.motion
            enabled: !!root.player && !!root.player.canControl && !!root.player.canGoPrevious
            onClicked: root.media.previous()
        }
        IconButton {
            glyph: root.player && root.player.isPlaying ? "pause" : "play_arrow"
            label: root.player && root.player.isPlaying ? "Pausar" : "Reproducir"
            prominent: true; motion: root.motion
            enabled: !!root.player && !!root.player.canControl && !!root.player.canTogglePlaying
            onClicked: root.media.toggle()
        }
        IconButton {
            glyph: "skip_next"; label: "Siguiente"; motion: root.motion
            enabled: !!root.player && !!root.player.canControl && !!root.player.canGoNext
            onClicked: root.media.next()
        }
    }

    Flow {
        Layout.fillWidth: true
        visible: !!root.media && root.media.players.length > 1
        spacing: Wysun.Appearance.spaceS
        Repeater {
            model: root.media ? root.media.players : []
            delegate: Components.ActionButton {
                required property var modelData
                glyph: "music_note"
                motion: root.motion
                label: Logic.playerLabel(modelData)
                selected: root.player === modelData
                onClicked: root.media.select(modelData)
            }
        }
    }
    Components.ActionButton {
        Layout.fillWidth: true
        motion: root.motion
        glyph: "library_music"
        label: "Abrir Wysun Music"
        enabled: !!root.controller
        onClicked: root.controller.launch("music")
    }
}
