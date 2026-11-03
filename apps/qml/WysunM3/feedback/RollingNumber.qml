// A figure whose digits roll to their new value like a counter (CPU, memory, counts). Each digit is a column
// 0-9 that slides with the default spatial spring; other characters stay put. Tabular figures keep the width
// steady. With reduced motion the digits jump. Use for live numbers that change often; not for static text.
import QtQuick
import WysunM3

Item {
    id: root

    property string text
    property string role: "headline.medium"
    property color color: Theme.m3onSurface
    readonly property var type: Theme.typeFont(role)
    readonly property real lineHeight: Math.ceil(metrics.height)

    function isDigit(ch: string): bool {
        return ch >= "0" && ch <= "9";
    }

    // The characters as currently shown (each digit from its column's position): what a reader sees.
    function shownText() {
        let out = "";
        for (let i = 0; i < cells.count; i++) {
            const cell = cells.itemAt(i);
            out += cell ? cell.shown : "";
        }
        return out;
    }

    implicitWidth: row.implicitWidth
    implicitHeight: lineHeight

    FontMetrics {
        id: metrics

        font.family: root.type.family
        font.pointSize: root.type.pointSize > 0 ? root.type.pointSize : Qt.application.font.pointSize
        font.weight: root.type.weight
    }

    TextMetrics {
        id: digitMetrics

        font: metrics.font
        text: "0"
    }

    Row {
        id: row

        Repeater {
            id: cells

            model: root.text.length

            Item {
                id: cell

                required property int index
                readonly property string ch: root.text.charAt(index)
                readonly property bool digit: root.isDigit(ch)
                readonly property string shown: digit ? String(Math.max(0, Math.min(9, Math.round(-column.y / root.lineHeight)))) : ch

                width: digit ? Math.ceil(digitMetrics.advanceWidth) : glyph.implicitWidth
                height: root.lineHeight
                clip: digit

                Text {
                    id: glyph

                    visible: !cell.digit
                    text: cell.digit ? "" : cell.ch
                    color: root.color
                    font: metrics.font
                    height: root.lineHeight
                    verticalAlignment: Text.AlignVCenter
                }

                Column {
                    id: column

                    visible: cell.digit
                    y: cell.digit ? -Number(cell.ch) * root.lineHeight : 0

                    Behavior on y {
                        Anim {
                            kind: "defaultSpatial"
                        }
                    }

                    Repeater {
                        model: cell.digit ? 10 : 0

                        Text {
                            required property int index

                            text: index
                            color: root.color
                            font: metrics.font
                            height: root.lineHeight
                            width: cell.width
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
    }
}
