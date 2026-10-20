// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/AppList.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import QtQuick.Controls
import "../../" as Wysun
import "../../components" as Components
import "items"

ListView {
    id: root
    property var motion
    signal chosen(var row)
    clip: true
    spacing: Wysun.Appearance.spaceXs
    boundsBehavior: Flickable.StopAtBounds
    highlightMoveDuration: motion ? motion.hover : 0
    onModelChanged: currentIndex = count ? 0 : -1
    onCountChanged: if (count === 0) currentIndex = -1
    onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
    delegate: ResultItem {
        required property var modelData
        required property int index
        width: ListView.view.width
        row: modelData
        motion: root.motion
        selected: root.currentIndex === index
        onClicked: {
            root.currentIndex = index;
            root.chosen(modelData);
        }
    }
    // The list is keyboard-driven from SearchBar; the default Controls
    // scrollbar would bring an unthemed style.
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOff }
}
