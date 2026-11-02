// A Dropdown bound to one preference of `settings` (the SettingsController). `numeric` for values saved as numbers;
// `fallback` is what shows when the saved value is not among the options (no choice yet, or a device unplugged).
import QtQuick
import WysunM3

Dropdown {
    id: root

    required property string key
    property bool numeric
    property string fallback
    readonly property string saved: String(settings.values[key])

    function _listed(value) {
        for (const option of model)
            if (option.value === value)
                return true;
        return false;
    }

    objectName: key
    width: Metrics.textFieldMinWidth * 1.75
    current: _listed(saved) ? saved : fallback
    onActivated: value => {
        settings.setPref(key, numeric ? Number(value) : value);
        current = Qt.binding(() => _listed(saved) ? saved : fallback);
    }
}
