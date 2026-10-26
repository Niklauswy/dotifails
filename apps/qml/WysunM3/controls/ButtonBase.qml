// What every button shares (the counterpart of the shell's ButtonBase): a Surface with the container and
// content colours of its state, the corner that morphs while pressed, the state layer, the keyboard focus ring,
// and activation by click, Space or Enter. A mouse click never takes focus (Qt.TabFocus).
import QtQuick
import WysunM3

Surface {
    id: root

    property bool checkable
    property bool checked
    property bool hasContainer: true
    property int elevation: 0
    property color containerColor: Theme.m3primary
    property color contentRestColor: Theme.m3onPrimary
    property real restRadius: Theme.fullRadius(height)
    property real pressedRadius: Theme.rounding.small ?? 0
    property real checkedRadius: Theme.rounding.medium ?? 0
    property bool morph: true
    property alias stateLayer: layer

    readonly property color contentColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : contentRestColor
    readonly property bool pressed: layer.pressed || _keyDown
    readonly property bool hovered: layer.hovered
    property bool _keyDown

    signal clicked
    signal toggled

    function activate() {
        if (disabled)
            return;
        if (checkable) {
            checked = !checked;
            toggled();
        }
        clicked();
    }

    focusPolicy: disabled ? Qt.NoFocus : Qt.TabFocus
    activeFocusOnTab: !disabled
    level: disabled ? 0 : elevation + (hovered && elevation > 0 ? 1 : 0)
    container: !hasContainer ? "transparent" : disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContainer) : containerColor
    // Buttons keep their exact container role (M3 dropped the surface tint for them; elevation is the shadow), and
    // one without a container stays transparent where Surface would paint the 10 % disabled container.
    color: container
    radius: morph && pressed ? pressedRadius : checkable && checked ? checkedRadius : restRadius

    onDisabledChanged: {
        if (disabled && activeFocus)
            focus = false;
    }

    SpringBehavior on radius {
        kind: "fastSpatial"
    }

    Keys.onPressed: event => {
        if (event.isAutoRepeat || (event.key !== Qt.Key_Space && event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter))
            return;
        event.accepted = true;
        _keyDown = true;
    }
    Keys.onReleased: event => {
        if (event.isAutoRepeat || (event.key !== Qt.Key_Space && event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter))
            return;
        event.accepted = true;
        if (_keyDown) {
            _keyDown = false;
            activate();
        }
    }
    onActiveFocusChanged: _keyDown = false

    StateLayer {
        id: layer

        z: 1
        tint: root.contentColor
        radius: root.radius
        disabled: root.disabled
        focused: root.activeFocus
        onClicked: root.activate()
    }

    FocusRing {
        target: root
    }
}
