// A titled block of a gallery page: title-medium heading, a body-medium note and a wrapping row of samples.
import QtQuick
import WysunM3

Column {
    id: root

    property string title
    property string note
    default property alias samples: flow.data

    width: parent ? parent.width : 0
    spacing: Theme.spacing.medium ?? 0

    Label {
        role: "title.medium"
        text: root.title
    }

    Label {
        width: parent.width
        visible: root.note !== ""
        role: "body.medium"
        text: root.note
        color: Theme.m3onSurfaceVariant
        wrapMode: Text.Wrap
    }

    Flow {
        id: flow

        width: parent.width
        spacing: Theme.spacing.medium ?? 0
    }
}
