// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/osd/{Wrapper,Content}.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// One OSD for the whole session: a single OsdState (PipeWire default nodes and
// sysfs backlight, no polling) drives one passive window per output. Every
// volume, mute and microphone change shows it, including the existing
// multimedia keys, which are not touched.
import QtQuick
import Quickshell

Scope {
    id: root

    required property var motion
    readonly property alias state: osdState

    OsdState { id: osdState }

    Variants {
        model: Quickshell.screens
        OsdHost { osd: osdState; motion: root.motion }
    }
}
