// A hero tile of Inicio: an eyebrow, a big title and a subtitle on a role colour, with an expressive shape
// (the playing cover in a turning cookie, or a sunny/clover/flower with a symbol). Clicking opens, the
// optional buttons act (pause/resume, lyrics).
import QtQuick
import WysunM3

Surface {
    id: root

    property string eyebrow
    property string title
    property string subtitle
    property string symbol
    property string shape: "sunny"
    property url coverUrl
    property bool coverTile
    property bool spinning
    property color tone: Theme.m3secondaryContainer
    property color onTone: Theme.m3onSecondaryContainer
    property var buttons: []          // [{id, text, icon, type}]

    signal opened
    signal buttonClicked(string id)

    implicitHeight: MusicMetrics.bentoHeight
    radius: Theme.rounding.extraLarge ?? 0
    container: tone
    color: container
    clip: true
    activeFocusOnTab: true
    Keys.onReturnPressed: opened()
    Keys.onSpacePressed: opened()

    Cover {
        visible: root.coverTile
        width: Math.min(parent.height * 0.82, parent.width * 0.42)
        height: width
        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.large ?? 0
        anchors.verticalCenter: parent.verticalCenter
        source: root.coverUrl
        shape: "cookie12"
        spinning: root.spinning
        fill: Qt.alpha(root.onTone, Metrics.stateDragged)
        placeholderColor: root.onTone
    }

    ShapeEmblem {
        visible: !root.coverTile
        size: Math.min(parent.height * 0.6, parent.width * 0.5)
        anchors.right: parent.right
        anchors.rightMargin: -size * 0.12
        anchors.top: parent.top
        anchors.topMargin: -size * 0.12
        shape: root.shape
        color: Qt.alpha(root.onTone, Metrics.stateDragged)
        icon: root.symbol
        iconColor: root.onTone
        morphOnHover: true
        hoverShape: "puffy"
    }

    StateLayer {
        radius: root.radius
        tint: root.onTone
        focused: root.activeFocus
        onClicked: root.opened()
    }

    Column {
        x: Theme.padding.large ?? 0
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.padding.large ?? 0
        width: parent.width * (root.coverTile ? 0.52 : 0.85)
        spacing: Theme.spacing.extraSmall ?? 0

        Label {
            role: "label.medium"
            text: root.eyebrow.toUpperCase()
            color: root.onTone
            opacity: 0.8
        }
        Label {
            width: parent.width
            role: "headline.small"
            text: root.title
            color: root.onTone
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
        }
        Label {
            width: parent.width
            role: "body.medium"
            text: root.subtitle
            color: root.onTone
            opacity: 0.85
            elide: Text.ElideRight
        }
        Row {
            visible: root.buttons.length > 0
            spacing: Theme.spacing.small ?? 0
            topPadding: Theme.spacing.small ?? 0

            Repeater {
                model: root.buttons

                Button {
                    required property var modelData

                    type: modelData.type ?? "tonal"
                    text: modelData.text
                    icon: modelData.icon ?? ""
                    onClicked: root.buttonClicked(modelData.id)
                }
            }
        }
    }

}
