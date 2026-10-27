// Wysun Music's own sizes (the M3 component measures stay in WysunM3's Metrics). Taken from the approved
// mock-ups (docs/design/qml-migration/music-*.html).
pragma Singleton
import QtQuick
import WysunM3

QtObject {
    readonly property int cardCover: 160            // album / playlist / artist cards
    readonly property int cardWidth: cardCover
    readonly property int bentoHeight: 200
    readonly property int bentoWideFrom: 780         // the bento lays its tiles in one row from this width
    readonly property int chartRowWidth: 290
    readonly property int chartRows: 3
    readonly property int heroCover: 208             // collection header artwork
    readonly property int heroCompactCover: Metrics.listImageSize
    readonly property int trackRow: Metrics.listItemOneLine
    readonly property int trackCover: Metrics.listAvatarSize
    readonly property int nowPlayingCover: 360
    readonly property int pagePadding: Theme.padding.extraLarge ?? 0
}
