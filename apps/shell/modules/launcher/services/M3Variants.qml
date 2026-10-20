// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/M3Variants.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQml
import "../Logic.js" as Logic
QtObject {
    function query(text) { return Logic.search(Logic.variants, text, ["name", "id"]); }
}
