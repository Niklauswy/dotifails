// A Slider bound to one integer preference of `settings` (the SettingsController), with its value written beside it.
// It saves when the pointer lets go or a key moves it; the binding is restored so an outside change shows up too.
import QtQuick
import WysunM3

Row {
    id: root

    required property string key
    property real from: 0
    property real to: 100
    property real step: 1
    property string suffix
    property bool disabled

    spacing: Theme.spacing.small ?? 0

    Slider {
        id: slider

        objectName: root.key
        anchors.verticalCenter: parent.verticalCenter
        from: root.from
        to: root.to
        stepSize: root.step
        live: false
        disabled: root.disabled
        value: settings.values[root.key]
        onMoved: value => {
            settings.setPref(root.key, Math.round(value));
            slider.value = Qt.binding(() => settings.values[root.key]);
        }
    }

    Label {
        anchors.verticalCenter: parent.verticalCenter
        width: Metrics.iconButtonSize * 1.3
        role: "label.large"
        color: root.disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : Theme.m3onSurface
        text: Math.round(slider.value) + (root.suffix !== "" ? " " + root.suffix : "")
    }
}
