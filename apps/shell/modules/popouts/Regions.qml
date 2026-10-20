// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Regions.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

// The upstream drawer subtracts panel regions from a drag mask. Wysun opens a
// single overlay per output, so only the geometry helpers are needed: the
// anchor rectangle at the rail control and a hit test used by tests and by the
// outside-click guard.
QtObject {
    function anchorRect(anchorX, anchorY, width, height, hostWidth, hostHeight) {
        var w = Math.max(0, width || 72);
        var h = Math.max(0, height || 64);
        return {
            x: Math.max(0, Math.min(hostWidth - w, (anchorX || 0) - w / 2)),
            y: Math.max(0, Math.min(hostHeight - h, (anchorY || 0) - h / 2)),
            width: w,
            height: h
        };
    }

    function contains(rect, x, y) {
        return !!rect && x >= rect.x && y >= rect.y && x < rect.x + rect.width && y < rect.y + rect.height;
    }
}
