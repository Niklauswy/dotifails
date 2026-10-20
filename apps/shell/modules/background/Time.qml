// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// services/Time.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell

SystemClock {
    precision: SystemClock.Minutes
    // SystemClock updates from wall time on wake; no elapsed-time counter drifts.
}
