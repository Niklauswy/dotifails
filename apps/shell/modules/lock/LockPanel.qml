// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Composición centrada y jerarquía de estados de modules/lock/Center.qml,
// Content.qml y center/{Clock,PasswordInput,InputField,StateMessage}.qml,
// commit 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y
// LICENSES/GPL-3.0.txt. No incluye perfil, columnas laterales, notificaciones,
// captura de pantalla ni el backend Lock.qml/Pam.qml de origen.
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../" as Wysun
import "../../components" as Components
import "LockPolicy.js" as Policy

Item {
    id: root

    required property bool secure
    property bool authenticating: false
    property string state: "locked"
    property string detail: ""
    property int attempts: 0
    property bool mediaEnabled: false
    property var motion: null
    property string buffer: ""
    readonly property var layout: Policy.layout(width, height)
    readonly property var locale: Qt.locale("es_MX")

    signal submitted(string password)

    focus: root.secure
    Accessible.role: Accessible.Pane
    Accessible.name: "Pantalla de bloqueo de Wysun"
    Accessible.description: Policy.text(root.state, root.detail)

    function submit() {
        if (!root.secure || root.authenticating || root.buffer.length === 0) return;
        var password = root.buffer;
        root.buffer = "";
        root.submitted(password);
    }

    onSecureChanged: if (root.secure) root.forceActiveFocus()
    Component.onCompleted: if (root.secure) root.forceActiveFocus()

    Keys.onPressed: function(event) {
        if (!root.secure) return;
        var next = Policy.key(root.buffer, event.key, event.text,
                              (event.modifiers & Qt.ControlModifier) !== 0);
        root.buffer = next.buffer;
        if (next.submit) root.submit();
        event.accepted = true;
    }

    Rectangle {
        anchors.fill: parent
        color: Wysun.Appearance.canvas
    }

    MouseArea {
        anchors.fill: parent
        onClicked: if (root.secure) root.forceActiveFocus()
    }

    Column {
        id: center

        anchors.centerIn: parent
        width: Math.max(0, Math.min(parent.width - Wysun.Appearance.spaceXl * 2, root.layout.width))
        spacing: root.layout.gap

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Wysun.Appearance.spaceS

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(4, Wysun.Appearance.focusWidth * 2)
                height: Wysun.Appearance.fontBody
                radius: width / 2
                color: Wysun.Appearance.accent
            }
            Components.StyledText {
                text: "Wysun"
                color: Wysun.Appearance.muted
                font.pixelSize: root.layout.labelSize
                font.weight: Font.DemiBold
                font.letterSpacing: 2
                motion: root.motion
            }
        }

        Components.StyledText {
            width: parent.width
            text: root.locale.toString(clock.date, "dddd d 'de' MMMM").toLocaleUpperCase(root.locale)
            color: Wysun.Appearance.muted
            font.pixelSize: root.layout.dateSize
            font.weight: Font.DemiBold
            font.letterSpacing: 2
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            motion: root.motion
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Wysun.Appearance.spaceXs

            Text {
                text: root.locale.toString(clock.date, "hh")
                color: Wysun.Appearance.accent
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: root.layout.clockSize
                font.weight: Font.Bold
            }
            Text {
                text: ":"
                color: Wysun.Appearance.muted
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: root.layout.clockSize
            }
            Text {
                text: root.locale.toString(clock.date, "mm")
                color: Wysun.Appearance.text
                font.family: Wysun.Appearance.fontFamily
                font.pixelSize: root.layout.clockSize
                font.weight: Font.Bold
            }
        }

        Rectangle {
            id: field

            width: parent.width
            height: root.layout.fieldHeight
            radius: height / 2
            color: Wysun.Appearance.surface
            border.width: root.activeFocus ? Wysun.Appearance.focusWidth : Wysun.Appearance.borderWidth
            border.color: root.activeFocus ? Wysun.Appearance.focus : Wysun.Appearance.line
            Accessible.role: Accessible.EditableText
            Accessible.name: "Contraseña"
            Accessible.description: root.buffer.length ? "Contraseña escrita" : "Campo vacío"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Wysun.Appearance.spaceL
                anchors.rightMargin: Wysun.Appearance.spaceL
                spacing: Wysun.Appearance.spaceM

                Text {
                    Layout.fillWidth: true
                    text: root.buffer.length ? Policy.mask(root.buffer.length) : "Contraseña"
                    color: root.buffer.length ? Wysun.Appearance.text : Wysun.Appearance.muted
                    font.family: Wysun.Appearance.fontFamily
                    font.pixelSize: root.buffer.length ? root.layout.labelSize * 1.35 : root.layout.labelSize
                    font.letterSpacing: root.buffer.length ? 3 : 0
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }
                Text {
                    text: root.authenticating ? "" : "Intro"
                    color: Wysun.Appearance.muted
                    font.family: Wysun.Appearance.fontFamily
                    font.pixelSize: root.layout.labelSize
                    font.weight: Font.DemiBold
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Components.StyledText {
            width: parent.width
            text: Policy.text(root.state, root.detail)
            color: Policy.isError(root.state) ? Wysun.Appearance.danger
                 : (root.state === "authenticating" ? Wysun.Appearance.accent : Wysun.Appearance.muted)
            font.pixelSize: root.layout.labelSize
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            motion: root.motion
        }

        Components.StyledText {
            width: parent.width
            visible: root.attempts > 1 && root.state === "failed"
            text: "Intento " + root.attempts
            color: Wysun.Appearance.muted
            font.pixelSize: root.layout.labelSize - 1
            horizontalAlignment: Text.AlignHCenter
            motion: root.motion
        }

        // Opt-in: without the explicit preference no MPRIS player is queried,
        // so a locked screen never exposes media metadata by default.
        Loader {
            width: parent.width
            active: root.mediaEnabled
            visible: active
            sourceComponent: LockMedia {
                mediaEnabled: root.mediaEnabled
                motion: root.motion
            }
        }

        Components.StyledText {
            width: parent.width
            text: "Esc borra · Intro desbloquea"
            color: Wysun.Appearance.muted
            opacity: 0.8
            font.pixelSize: root.layout.labelSize - 1
            horizontalAlignment: Text.AlignHCenter
            motion: root.motion
        }
    }

    SystemClock {
        id: clock
        precision: SystemClock.Minutes
    }
}
