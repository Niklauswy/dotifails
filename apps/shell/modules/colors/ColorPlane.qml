import QtQuick
import Wysun.Config
import qs.services

Item {
    id: root
    property real hue: 0
    property real saturation: 0.5
    property real brightness: 0.8
    signal selected(real saturation, real brightness)
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: "Saturación y brillo. Usa las flechas para ajustar."
    onHueChanged: plane.requestPaint()
    Keys.onPressed: event => {
        const step = event.modifiers & Qt.ShiftModifier ? 0.1 : 0.01;
        if (event.key === Qt.Key_Left) selected(Math.max(0, saturation - step), brightness);
        else if (event.key === Qt.Key_Right) selected(Math.min(1, saturation + step), brightness);
        else if (event.key === Qt.Key_Up) selected(saturation, Math.min(1, brightness + step));
        else if (event.key === Qt.Key_Down) selected(saturation, Math.max(0, brightness - step));
        else return;
        event.accepted = true;
    }
    Canvas {
        id: plane
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d"), r = Math.min(Tokens.rounding.extraLarge, width / 2, height / 2);
            ctx.reset();
            ctx.beginPath(); ctx.moveTo(r, 0); ctx.arcTo(width, 0, width, height, r);
            ctx.arcTo(width, height, 0, height, r); ctx.arcTo(0, height, 0, 0, r);
            ctx.arcTo(0, 0, width, 0, r); ctx.closePath(); ctx.clip();
            // theme-exception-begin: mathematical HSV gamut, not interface colours.
            let gradient = ctx.createLinearGradient(0, 0, width, 0);
            gradient.addColorStop(0, "white"); gradient.addColorStop(1, Qt.hsva(root.hue, 1, 1, 1));
            ctx.fillStyle = gradient; ctx.fillRect(0, 0, width, height);
            gradient = ctx.createLinearGradient(0, 0, 0, height);
            gradient.addColorStop(0, "transparent"); gradient.addColorStop(1, "black");
            ctx.fillStyle = gradient; ctx.fillRect(0, 0, width, height);
            // theme-exception-end
        }
    }
    Rectangle {
        width: Tokens.spacing.largeIncreased; height: width; radius: width / 2
        x: Math.max(0, Math.min(parent.width - width, root.saturation * parent.width - width / 2))
        y: Math.max(0, Math.min(parent.height - height, (1 - root.brightness) * parent.height - height / 2))
        color: Qt.hsva(root.hue, root.saturation, root.brightness, 1)
        border.width: Tokens.spacing.extraSmall / 2
        border.color: root.brightness > 0.65 && root.saturation < 0.4 ? "black" : "white" // theme-exception: contrast marker over the user gamut.
    }
    Rectangle {
        anchors.fill: parent; anchors.margins: -Tokens.spacing.extraSmall
        radius: Tokens.rounding.extraLarge + Tokens.spacing.extraSmall
        color: "transparent"; border.width: root.activeFocus ? Tokens.spacing.extraSmall / 2 : 0; border.color: Colours.palette.m3primary
    }
    MouseArea {
        anchors.fill: parent; cursorShape: Qt.CrossCursor
        function pick(mouse): void { root.selected(Math.max(0, Math.min(1, mouse.x / width)), 1 - Math.max(0, Math.min(1, mouse.y / height))); }
        onPressed: mouse => { root.forceActiveFocus(); pick(mouse); }
        onPositionChanged: mouse => { if (pressed) pick(mouse); }
    }
}
