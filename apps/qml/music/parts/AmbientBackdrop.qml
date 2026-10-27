// The artwork as an ambient backdrop: the cover blurred, slightly saturated and enlarged, tinted with its dominant
// colour and faded into the surface. Without the shader (software scene graph) it is a gradient of that colour.
// theme-exception: the tone comes from the user's artwork, mixed with the surface roles.
import QtQuick
import QtQuick.Effects
import WysunM3

Item {
    id: root

    property url source
    property color tone: Theme.m3secondaryContainer
    property real strength: 1            // 0-1: how much of the artwork shows through
    property bool fadeBottom: true
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool ready: image.status === Image.Ready

    clip: true

    Rectangle {
        anchors.fill: parent
        color: Theme.m3surface
    }

    Image {
        id: image

        anchors.fill: parent
        visible: false
        source: root.source
        sourceSize.width: 96
        sourceSize.height: 96
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }

    MultiEffect {
        anchors.centerIn: parent
        width: parent.width * 1.3
        height: parent.height * 1.3
        visible: root.ready && !root._software
        source: image
        blurEnabled: true
        blur: 1
        blurMax: 64
        saturation: 0.35
        brightness: Theme.dark ? -0.3 : 0.2
        opacity: 0.9 * root.strength

        Behavior on opacity {
            NumberAnimation {
                duration: Motion.ms("slowEffects")
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.alpha(root.tone, root.ready && !root._software ? 0.18 : 0.45 * root.strength)

        Behavior on color {
            CAnim {
                kind: "slowEffects"
            }
        }
    }

    // A veil of the surface keeps text readable over any artwork (light covers in dark mode, dark ones in light).
    Rectangle {
        anchors.fill: parent
        visible: !root.fadeBottom
        color: Qt.alpha(Theme.m3surface, Theme.dark ? 0.62 : 0.55)
    }

    Rectangle {
        anchors.fill: parent
        visible: root.fadeBottom
        gradient: Gradient {
            GradientStop {
                position: 0
                color: Qt.alpha(Theme.m3surface, Theme.dark ? 0.4 : 0.35)
            }
            GradientStop {
                position: 0.55
                color: Qt.alpha(Theme.m3surface, 0.7)
            }
            GradientStop {
                position: 1
                color: Theme.m3surface
            }
        }
    }
}
