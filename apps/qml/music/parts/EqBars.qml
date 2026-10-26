// Three bars that dance while a song plays (still with reduced motion or in pause).
import QtQuick
import WysunM3

Row {
    id: root

    property bool running: true
    property color color: Theme.m3primary

    spacing: Metrics.progressGap / 2
    height: Metrics.chipIconSize

    Repeater {
        model: 3

        Rectangle {
            required property int index
            property real level: 0.5

            anchors.bottom: parent.bottom
            width: Metrics.progressThickness
            height: root.height * level
            radius: width / 2
            color: root.color

            SequentialAnimation on level {
                running: root.running && root.visible && !Motion.reduced
                loops: Animation.Infinite

                Anim {
                    to: 1
                    kind: index === 1 ? "fastEffects" : "defaultEffects"
                }
                Anim {
                    to: 0.3 + 0.2 * index
                    kind: index === 2 ? "fastEffects" : "slowEffects"
                }
            }
        }
    }
}
