// A full-bleed tile of Explorar: the collection's artwork (or its role colour) under a scrim with its kind and
// title. Opens the collection.
import QtQuick
import WysunM3

Item {
    id: root

    property var app
    readonly property string collectionId: model.id

    objectName: "explore-" + collectionId
    implicitHeight: MusicMetrics.cardCover * 0.9
    activeFocusOnTab: true
    Keys.onReturnPressed: app.navigate("collection:" + collectionId, true)

    Cover {
        anchors.fill: parent
        sources: model.covers
        shape: "squircle"
        fill: model.kind === "favorites" ? Theme.m3tertiaryContainer : model.kind === "artist" ? Theme.m3secondaryContainer : Theme.m3primaryContainer
        placeholderIcon: ""
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.rounding.large ?? 0
        gradient: Gradient {
            GradientStop {
                position: 0.35
                color: Qt.alpha(Theme.m3scrim, 0)
            }
            GradientStop {
                position: 1
                color: Qt.alpha(Theme.m3scrim, 0.7)
            }
        }
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.padding.medium ?? 0

        Label {
            role: "label.medium"
            text: (model.label ?? "").toUpperCase()
            color: Theme.m3inverseOnSurface
            opacity: 0.85
        }
        Label {
            width: parent.width
            role: "title.medium"
            text: model.title
            color: Theme.m3inverseOnSurface
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }

    StateLayer {
        radius: Theme.rounding.large ?? 0
        tint: Theme.m3inverseOnSurface
        focused: root.activeFocus
        onClicked: root.app.navigate("collection:" + root.collectionId, true)
    }
}
