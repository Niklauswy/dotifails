// Live data: figures that roll (RollingNumber), a scrolling chart with a scrub guide and peak markers
// (LiveChart) and the shape of a process state (StateShape).
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    property var samples: []
    property int tick: 0

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            page.tick++;
            const next = page.samples.slice(-59);
            next.push(10 + Math.abs(Math.sin(page.tick / 3)) * 50 + (page.tick % 7 === 0 ? 30 : 0));
            page.samples = next;
        }
    }

    Section {
        title: "Números que ruedan"
        note: "Cada dígito gira hasta su valor con el muelle espacial; las cifras tabulares no bailan."

        Row {
            spacing: Theme.spacing.large ?? 0

            RollingNumber {
                text: Math.round(page.samples[page.samples.length - 1] ?? 0) + " %"
                role: "headline.large"
            }

            RollingNumber {
                text: (page.tick % 100 / 10).toFixed(1) + " GB"
                role: "title.large"
                color: Theme.m3tertiary
            }
        }
    }

    Section {
        title: "Gráfica en vivo"
        note: "Las muestras entran deslizándose; pasa el cursor para ver el valor y su etiqueta."

        LiveChart {
            width: Metrics.textFieldMinWidth * 3
            height: Metrics.emblemSize * 3
            series: [page.samples]
            colors: [Theme.m3primary]
            maxValue: 100
            scrub: true
            formatValue: v => Math.round(v) + " %"
            labelAt: i => "hace " + (page.samples.length - 1 - i) + " s"
            markers: page.samples.length > 10 ? [{index: page.samples.length - 8, glyph: "F", color: Theme.m3tertiaryContainer}] : []
        }
    }

    Section {
        title: "Indicador de desplazamiento"
        note: "Aparece al desplazar o al pasar el cursor; el pulgar se puede arrastrar."

        Item {
            width: Metrics.textFieldMinWidth
            height: Metrics.emblemSize * 2

            Flickable {
                id: scroller

                anchors.fill: parent
                clip: true
                contentHeight: Metrics.emblemSize * 8

                Column {
                    Repeater {
                        model: 8

                        Label {
                            required property int index

                            height: Metrics.emblemSize
                            text: "Proceso " + (index + 1)
                        }
                    }
                }
            }

            ScrollIndicator {
                anchors.right: parent.right
                height: parent.height
                flickable: scroller
            }
        }
    }

    Section {
        title: "Forma de estado"
        note: "Trabajando gira; en espera, círculo; pausado, cuadrado; zombi, estallido; grupo, sol."

        Row {
            spacing: Theme.spacing.large ?? 0

            Repeater {
                model: ["R", "S", "T", "Z", "G"]

                StateShape {
                    required property string modelData

                    state: modelData
                    color: Theme.m3secondaryContainer
                    size: Metrics.emblemSize

                    Icon {
                        anchors.centerIn: parent
                        name: "memory"
                        color: Theme.m3onSecondaryContainer
                    }
                }
            }
        }
    }
}
