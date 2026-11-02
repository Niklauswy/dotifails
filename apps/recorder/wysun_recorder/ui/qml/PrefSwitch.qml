// A Switch bound to one boolean preference of `settings` (the SettingsController): it shows the saved value and
// saves a change at once; the binding is restored after each click so an outside change shows up too.
import QtQuick
import WysunM3

Switch {
    id: root

    required property string key

    objectName: key
    checked: settings.values[key] === true
    onToggled: {
        settings.setPref(key, checked);
        checked = Qt.binding(() => settings.values[key] === true);
    }
}
