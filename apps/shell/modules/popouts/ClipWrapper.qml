// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/ClipWrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

// Clipping surface for the morphing card. Keeping the clip in its own item
// means the card can grow from a small rail anchor without painting outside
// its final bounds during the transition.
Item {
    id: root
    clip: true
    default property alias content: inner.data

    Item {
        id: inner
        anchors.fill: parent
    }
}
