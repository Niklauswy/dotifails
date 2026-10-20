// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// modules/background/DesktopClock.qml y services/Time.qml, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun

Item {
    id: root
    property date now: new Date()
    readonly property var locale: Qt.locale("es_MX")
    implicitWidth: layout.implicitWidth + Wysun.Appearance.spaceXl * 2
    implicitHeight: layout.implicitHeight + Wysun.Appearance.spaceL * 2
    Accessible.role: Accessible.StaticText
    Accessible.name: locale.toString(now, "hh:mm, dddd d 'de' MMMM")

    Rectangle {
        anchors.fill: parent
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.surface
        border.width: Wysun.Appearance.borderWidth
        border.color: Wysun.Appearance.line
    }
    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: Wysun.Appearance.spaceL
        scale: Math.max(0, Math.min(1,
               (root.width - Wysun.Appearance.spaceS * 2) / implicitWidth,
               (root.height - Wysun.Appearance.spaceS * 2) / implicitHeight))
        Row {
            spacing: Wysun.Appearance.spaceXs
            Text {
                text: root.locale.toString(root.now, "hh")
                color: Wysun.Appearance.accent
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontTitle * 3
                font.weight: Font.Bold
            }
            Text {
                text: ":"
                color: Wysun.Appearance.muted
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontTitle * 3
            }
            Text {
                text: root.locale.toString(root.now, "mm")
                color: Wysun.Appearance.text
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontTitle * 3
                font.weight: Font.Bold
            }
        }
        Rectangle {
            implicitWidth: Wysun.Appearance.focusWidth
            implicitHeight: Wysun.Appearance.fontTitle * 3
            color: Wysun.Appearance.lineStrong
        }
        Column {
            Text {
                text: root.locale.toString(root.now, "MMMM").toLocaleUpperCase(root.locale)
                color: Wysun.Appearance.muted
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontSmall
                font.weight: Font.DemiBold
            }
            Text {
                text: root.locale.toString(root.now, "dd")
                color: Wysun.Appearance.accent
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontTitle * 2
                font.weight: Font.Medium
            }
            Text {
                text: root.locale.toString(root.now, "dddd")
                color: Wysun.Appearance.text
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: Wysun.Appearance.fontBody
            }
        }
    }
}
