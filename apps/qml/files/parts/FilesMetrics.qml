// Wysun Files' own sizes (the M3 component measures stay in WysunM3's Metrics). Taken from the approved mock-ups
// (docs/design/qml-migration/files-*.html) and the Widgets window they replace.
pragma Singleton
import QtQuick
import WysunM3

QtObject {
    readonly property int tileWidth: 136            // grid cell
    readonly property int tileHeight: 156
    readonly property int tileIcon: 76              // icon box inside a tile
    readonly property int rowHeight: 48             // list row
    readonly property int rowIcon: 32
    readonly property int heroEmblem: 72
    readonly property int tabHeight: 40
    readonly property int tabMaxWidth: 220
    readonly property int statusHeight: 32
    readonly property int filterWidth: 260          // the filter field, wider while it has focus
    readonly property int filterWideWidth: 420
    readonly property int inspectorWidth: 372       // F-50
    readonly property int inspectorFrom: 1000       // the inspector opens by itself from this window width
    readonly property int dateColumn: 128
    readonly property int sizeColumn: 96
    readonly property int typeColumn: 140
    readonly property int listColumnsFrom: 760      // narrower lists keep only name and size
    readonly property int entranceRows: 40          // rows that play the staggered entrance
    readonly property int entranceStep: 14          // ms between two of them
    readonly property int entranceRise: 12
    readonly property int pagePadding: Theme.padding.large ?? 0
}
