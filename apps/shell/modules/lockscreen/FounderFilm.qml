pragma ComponentBehavior: Bound

// Wysun lock · the founder's film, the reward at 100 %. Pixel art on a 320x180 canvas scaled up without
// smoothing (the art in film/, prepared by film/prepare.py). `seconds` runs the shots, cut like a film:
//   0.0- 5.0  over the ranges: sky, clouds and three ranges drifting at their own depth
//   5.0- 8.5  the lone peak above the sea of clouds, the camera closing in
//   8.5-12.5  the founder on the ledge, seen from behind, his coat in the wind
//  12.5-13.7  he crouches and leaps from the ledge
//  13.7-18.0  he soars over the clouds, turns into an eagle and flies off into the sunset
import QtQuick

Item {
    id: root

    property real seconds: 0
    readonly property real duration: 18
    readonly property string art: Qt.resolvedUrl("film/")

    function frame(name: string, count: int, fps: real, from: real): url {
        const index = Math.floor(Math.max(0, root.seconds - from) * fps) % count;
        return root.art + name + "-" + index + ".png";
    }

    function between(from: real, to: real): bool {
        return root.seconds >= from && root.seconds < to;
    }

    function progress(from: real, to: real): real {
        return Math.max(0, Math.min(1, (root.seconds - from) / (to - from)));
    }

    component Pixels: Image {
        smooth: false
        mipmap: false
        asynchronous: false
    }

    Item {
        id: canvas

        width: 320
        height: 180
        // Cover the screen, centred, in whole art pixels.
        scale: Math.max(root.width / width, root.height / height)
        transformOrigin: Item.TopLeft
        x: (root.width - width * scale) / 2
        y: (root.height - height * scale) / 2
        clip: true
        layer.enabled: true
        layer.smooth: false

        // ------------------------------------------------ over the ranges
        Item {
            anchors.fill: parent
            visible: root.between(0, 5)
            readonly property real t: root.progress(0, 5)

            Pixels { source: root.art + "sky.png"; x: -40 * parent.t }
            Pixels { source: root.art + "clouds.png"; x: -120 * parent.t }
            Pixels { source: root.art + "range-far.png"; x: -110 * parent.t }
            Pixels { source: root.art + "range-mid.png"; x: -190 * parent.t; y: 6 }
            Pixels { source: root.art + "range-near.png"; x: -270 * parent.t; y: 14 }
            Pixels { source: root.art + "cloud-sea.png"; x: -320 * parent.t; y: 24 }
        }

        // ------------------------------------------------ the lone peak
        Pixels {
            source: root.art + "peak.png"
            visible: root.between(5, 8.5)
            scale: 1 + 0.2 * root.progress(5, 8.5)
            transformOrigin: Item.Top
        }

        // ------------------------------------------------ the founder on the ledge, and his leap
        Item {
            anchors.fill: parent
            visible: root.between(8.5, 13.7)
            // The camera eases in while he stands; it holds during the leap.
            scale: 1 + 0.12 * root.progress(8.5, 12.5)
            transformOrigin: Item.Left

            Pixels { source: root.art + "ledge.png" }
            Pixels {
                visible: root.seconds < 12.5
                source: root.frame("founder-stand", 4, 3, 8.5)
                x: 152 - width / 2
                y: 109 - height
            }
            Pixels {
                readonly property real t: root.progress(12.5, 13.7)
                visible: root.seconds >= 12.5
                source: root.frame("founder-jump", 4, 4 / 1.2, 12.5)
                // Off the tip of the ledge: up and forward once airborne.
                x: 160 - width / 2 + Math.max(0, t - 0.5) * 2 * 60
                y: 112 - height - Math.max(0, t - 0.5) * 2 * 40
            }
        }

        // ------------------------------------------------ the flight
        Item {
            anchors.fill: parent
            visible: root.seconds >= 13.7
            readonly property real t: root.progress(13.7, 18)

            Pixels { source: root.art + "sky.png"; x: -200 - 40 * parent.t }
            Pixels { source: root.art + "clouds.png"; x: -160 * parent.t - 80 }
            Pixels { source: root.art + "range-far.png"; x: -100 * parent.t; y: 40 }
            Pixels { source: root.art + "cloud-sea.png"; x: -260 * parent.t; y: 34 }

            // He glides in from the left, turns into the eagle mid-sky, and the eagle soars away.
            Pixels {
                readonly property real t: parent.t
                readonly property string stage: t < 0.42 ? "founder-fly" : t < 0.62 ? "founder-turn" : "eagle"
                source: stage === "founder-fly" ? root.frame("founder-fly", 4, 6, 13.7)
                      : stage === "founder-turn" ? root.art + "founder-turn-" + Math.min(3, Math.floor((t - 0.42) / 0.2 * 4)) + ".png"
                      : root.frame("eagle", 6, 10, 13.7)
                scale: t < 0.62 ? 1 : 1 - 0.75 * (t - 0.62) / 0.38
                x: -40 + t * 300 - width / 2
                y: 90 - t * 70 + 8 * Math.sin(t * 9) - height / 2
            }
        }
    }
}
