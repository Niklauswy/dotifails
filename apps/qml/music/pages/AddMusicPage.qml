// AddMusic page of Wysun Music (filled in by its own part of the plan).
import QtQuick
import WysunM3

FocusScope {
    property var app
    property string route
    readonly property string kind: "downloads"
    property real scrollOffset: 0

    Label {
        anchors.centerIn: parent
        role: "title.large"
        text: parent.route
    }
}
