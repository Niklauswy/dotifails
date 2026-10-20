// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Regions.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

QtObject {
    // The host intentionally captures its full output while open, allowing
    // outside-click dismissal. No passive frame/exclusion zones are changed.
    function contains(panel, x, y) {
        return panel && panel.visible && x >= panel.x && y >= panel.y && x < panel.x + panel.width && y < panel.y + panel.height;
    }
}
