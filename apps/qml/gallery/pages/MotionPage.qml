// Motion: the expressive springs (spatial overshoot vs effects), the three M3 transition patterns and the
// reduced-motion switch.
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    property bool moved
    property int step: 0

    Section {
        title: "Muelles"
        note: "Spatial (posición, tamaño, forma) puede rebotar; effects (color, opacidad) nunca."

        Column {
            spacing: Theme.spacing.medium ?? 0

            Button {
                type: "tonal"
                text: "Mover"
                onClicked: page.moved = !page.moved
            }

            Repeater {
                model: ["fastSpatial", "defaultSpatial", "slowSpatial"]

                Item {
                    required property string modelData

                    width: Metrics.textFieldMinWidth * 2
                    height: Metrics.chipHeight

                    Rectangle {
                        width: Metrics.chipHeight * 2
                        height: parent.height
                        radius: Theme.fullRadius(height)
                        color: Theme.m3primaryContainer
                        x: page.moved ? parent.width - width : 0

                        SpringBehavior on x {
                            kind: modelData
                        }

                        Label {
                            anchors.centerIn: parent
                            role: "label.small"
                            text: modelData.replace("Spatial", "")
                            color: Theme.m3onPrimaryContainer
                        }
                    }
                }
            }

            Rectangle {
                id: fade

                width: Metrics.textFieldMinWidth
                height: Metrics.chipHeight
                radius: Theme.rounding.small ?? 0
                color: page.moved ? Theme.m3tertiaryContainer : Theme.m3secondaryContainer

                Behavior on color {
                    CAnim {
                        kind: "defaultEffects"
                    }
                }
            }

            Rectangle {
                id: pulse

                width: Metrics.chipHeight
                height: Metrics.chipHeight
                radius: Theme.fullRadius(height)
                color: Theme.m3primary

                Anim on scale {
                    running: page.moved
                    from: Metrics.menuEnterScale
                    to: 1
                    kind: "defaultSpatial"
                }
            }
        }
    }

    Section {
        title: "Patrones de transición"
        note: "Fade through entre destinos hermanos; shared axis en jerarquías; container transform al abrir un elemento."

        Column {
            spacing: Theme.spacing.small ?? 0

            Row {
                spacing: Theme.spacing.small ?? 0

                Button {
                    type: "tonal"
                    text: "Fade through"
                    onClicked: fadeDemo.show(demoPage, {n: ++page.step})
                }
                Button {
                    type: "tonal"
                    text: "Eje ←"
                    onClicked: axisDemo.show(demoPage, {n: --page.step}, false)
                }
                Button {
                    type: "tonal"
                    text: "Eje →"
                    onClicked: axisDemo.show(demoPage, {n: ++page.step}, true)
                }
                Button {
                    type: "tonal"
                    text: "Fundido simple"
                    onClicked: plainDemo.show(demoPage, {n: ++page.step})
                }
            }

            Row {
                spacing: Theme.spacing.medium ?? 0

                DemoFrame {
                    FadeThrough {
                        id: fadeDemo

                        objectName: "fadeDemo"
                        anchors.fill: parent
                    }
                }
                DemoFrame {
                    SharedAxis {
                        id: axisDemo

                        objectName: "axisDemo"
                        anchors.fill: parent
                        axis: "x"
                    }
                }
                DemoFrame {
                    TransitionHost {
                        id: plainDemo

                        anchors.fill: parent
                    }
                }
            }
        }

        Rectangle {
            id: albumCard

            width: Metrics.textFieldMinWidth * 0.8
            height: Metrics.topAppBarLarge
            radius: Theme.rounding.large ?? 0
            color: Theme.m3secondaryContainer

            Label {
                anchors.centerIn: parent
                role: "title.medium"
                text: "Abrir (container transform)"
                color: Theme.m3onSecondaryContainer
            }

            StateLayer {
                radius: albumCard.radius
                onClicked: transform.open(albumCard, detailPage, {})
            }
        }
    }

    Section {
        title: "Movimiento reducido"
        note: "Con el ajuste del sistema, las animaciones terminan al instante."

        Button {
            type: Theme.reducedMotion ? "filled" : "outlined"
            checkable: true
            checked: Theme.reducedMotion
            text: Theme.reducedMotion ? "Reducido" : "Completo"
            icon: "motion_photos_off"
            onToggled: bridge.setReducedMotion(checked)
        }
    }

    // Called by the gallery checks: one forward and one back step of the shared axis demo.
    function axisStep(forward) {
        return axisDemo.show(demoPage, {n: forward ? ++step : --step}, forward);
    }

    component DemoFrame: Rectangle {
        width: Metrics.textFieldMinWidth * 0.8
        height: Metrics.topAppBarLarge
        radius: Theme.rounding.large ?? 0
        color: Theme.m3surfaceContainerHigh
        clip: true
    }

    Component {
        id: demoPage

        Rectangle {
            property int n

            color: [Theme.m3primaryContainer, Theme.m3secondaryContainer, Theme.m3tertiaryContainer][((n % 3) + 3) % 3]

            Label {
                anchors.centerIn: parent
                role: "headline.medium"
                text: parent.n
            }
        }
    }

    Component {
        id: detailPage

        Rectangle {
            color: Theme.m3secondaryContainer

            Column {
                anchors.centerIn: parent
                spacing: Theme.spacing.large ?? 0

                ShapeEmblem {
                    anchors.horizontalCenter: parent.horizontalCenter
                    size: Metrics.emptyEmblemSize
                    shape: "cookie12"
                    icon: "album"
                }
                Button {
                    text: "Cerrar"
                    onClicked: transform.close()
                }
            }
        }
    }

    ContainerTransform {
        id: transform

        parent: page.overlay
        anchors.fill: parent
        containerColor: Theme.m3secondaryContainer
        endRadius: 0
    }
}
