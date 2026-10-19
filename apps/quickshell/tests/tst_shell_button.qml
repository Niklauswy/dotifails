pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import ".."

Window {
    id: fixture
    width: 180
    height: 96
    visible: true
    property int primaryCalls: 0
    property int secondaryCalls: 0
    Flickable {
        anchors.fill: parent
        contentWidth: width + 80
        contentHeight: height
        Loader {
            x: 16; y: 16; width: 120; height: 40
            sourceComponent: ShellButton {
                objectName: "primaryButton"
                preferences: ({ palette: { foreground: "#d2e4e8", accent: "#79c9dc", surface: "#15272e" } })
                text: "Wysun"
                secondaryActionEnabled: true
                onClicked: fixture.primaryCalls++
                onSecondaryClicked: fixture.secondaryCalls++
            }
        }
    }
}
