import QtQuick
import Quickshell
import qs.components.controls

// SelectRow over a dynamic list of {value, label} options.
SelectRow {
    id: root

    property var options: []
    property var current

    signal picked(var value)

    menuItems: variants.instances
    active: menuItems.find(i => i.value === root.current) ?? null
    fallbackText: String(root.current ?? "")
    onSelected: item => root.picked(item.value)

    Variants {
        id: variants

        model: root.options

        MenuItem {
            required property var modelData

            text: modelData.label
            value: modelData.value
        }
    }
}
