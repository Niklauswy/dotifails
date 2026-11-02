// The folder's header (F-26): its emblem in an expressive shape chosen by what it holds (a flower for pictures, a
// cookie for music, a gem for code…) next to the title and the summary «6 carpetas · 8 archivos · 1,3 GB».
import QtQuick
import WysunM3

Item {
    id: root

    property string title
    property string summary
    property string glyph                    // the folder's own glyph, if special
    property string dominant                 // FolderModel.dominant
    readonly property var look: ({
            images: ["flower", "image", Theme.m3tertiaryContainer, Theme.m3onTertiaryContainer],
            videos: ["pill", "movie", Theme.m3tertiaryContainer, Theme.m3onTertiaryContainer],
            audio: ["cookie", "music_note", Theme.m3primaryContainer, Theme.m3onPrimaryContainer],
            documents: ["squircle", "description", Theme.m3primaryContainer, Theme.m3onPrimaryContainer],
            code: ["gem", "code", Theme.m3secondaryContainer, Theme.m3onSecondaryContainer]
        })[dominant] ?? ["cookie", "folder", Theme.m3secondaryContainer, Theme.m3onSecondaryContainer]

    implicitHeight: FilesMetrics.heroEmblem + 2 * (Theme.spacing.small ?? 0)

    ShapeEmblem {
        id: emblem

        objectName: "heroEmblem"
        anchors.verticalCenter: parent.verticalCenter
        size: FilesMetrics.heroEmblem
        width: size
        height: size
        shape: root.look[0]
        icon: root.glyph !== "" ? root.glyph : root.look[1]
        color: root.look[2]
        iconColor: root.look[3]
        morphOnHover: true
    }
    Column {
        anchors.left: emblem.right
        anchors.leftMargin: Theme.spacing.large ?? 0
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacing.extraSmall ?? 0

        Label {
            objectName: "heroTitle"
            width: parent.width
            role: "headline.medium"
            text: root.title
            color: Theme.m3onSurface
            elide: Text.ElideMiddle
        }
        Label {
            objectName: "heroSummary"
            width: parent.width
            role: "body.medium"
            text: root.summary
            color: Theme.m3onSurfaceVariant
            elide: Text.ElideRight
        }
    }
}
