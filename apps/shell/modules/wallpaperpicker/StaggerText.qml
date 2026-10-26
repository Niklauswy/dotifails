pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Text whose letters rise into place one after another each time it changes.
Row {
    id: root

    property string text
    property font font: Tokens.font.headline.small
    property color color: Colours.palette.m3onSurface

    Repeater {
        model: root.text.split("")

        delegate: StyledText {
            id: letter

            required property string modelData
            required property int index

            text: modelData
            font: root.font
            color: root.color
            opacity: 0

            transform: Translate {
                id: shift

                y: letter.height * 0.6
            }

            SequentialAnimation {
                running: true

                PauseAnimation {
                    duration: letter.index * 18 * Tokens.anim.durations.scale
                }
                ParallelAnimation {
                    Anim {
                        target: letter
                        property: "opacity"
                        to: 1
                        type: Anim.DefaultEffects
                    }
                    Anim {
                        target: shift
                        property: "y"
                        to: 0
                        type: Anim.FastSpatial
                    }
                }
            }
        }
    }
}
