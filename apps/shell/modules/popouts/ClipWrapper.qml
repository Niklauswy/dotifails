// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/bar/popouts/ClipWrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick

// Clipping surface for the morphing card. The content keeps its final size and
// its final place on the output (`contentX/Y` are relative to this item), so the
// window opening reveals it instead of squeezing and re-laying it out every
// frame. Only the clip rectangle changes during the transition.
Item {
    id: root
    property real contentX: 0
    property real contentY: 0
    property real contentWidth: width
    property real contentHeight: height
    clip: true
    default property alias content: inner.data

    Item {
        id: inner
        x: root.contentX
        y: root.contentY
        width: root.contentWidth
        height: root.contentHeight
    }
}
