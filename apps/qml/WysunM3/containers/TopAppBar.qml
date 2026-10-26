// M3 top app bar: small (64; title-large), centered, medium (112; headline-small title on its own row) or large
// (152; headline-medium). Feed `scrollOffset` (e.g. a ListView's contentY): medium/large collapse to 64 and the
// small title fades in; once content scrolls under it the bar takes surfaceContainer.
import QtQuick
import WysunM3

Rectangle {
    id: root

    property string variant: "small"         // small | centered | medium | large
    property string title
    property Component leading
    property Component actions
    property real scrollOffset: 0
    readonly property int expandedHeight: variant === "large" ? Metrics.topAppBarLarge : variant === "medium" ? Metrics.topAppBarMedium : Metrics.topAppBarSmall
    readonly property bool collapsible: variant === "medium" || variant === "large"
    readonly property bool scrolled: scrollOffset > 0
    readonly property real collapse: collapsible ? Math.max(0, Math.min(1, scrollOffset / (expandedHeight - Metrics.topAppBarSmall))) : 1

    implicitHeight: Math.max(Metrics.topAppBarSmall, expandedHeight - Math.max(0, scrollOffset))
    height: implicitHeight
    color: scrolled ? Theme.m3surfaceContainer : Theme.m3surface
    clip: true

    Behavior on color {
        CAnim {
            kind: "defaultEffects"
        }
    }

    Item {
        id: top

        width: parent.width
        height: Metrics.topAppBarSmall

        Loader {
            id: lead

            x: Theme.padding.extraSmall ?? 0
            anchors.verticalCenter: parent.verticalCenter
            active: root.leading !== null
            sourceComponent: root.leading
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            x: root.variant === "centered" ? (parent.width - width) / 2 : root.leading ? lead.x + lead.width + (Theme.padding.extraSmall ?? 0) : Theme.padding.large ?? 0
            width: Math.min(implicitWidth, parent.width - 2 * Math.max(lead.width, tail.width) - 2 * (Theme.padding.large ?? 0))
            role: "title.large"
            text: root.title
            elide: Text.ElideRight
            opacity: root.collapsible ? root.collapse : 1
        }

        Loader {
            id: tail

            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.extraSmall ?? 0
            anchors.verticalCenter: parent.verticalCenter
            active: root.actions !== null
            sourceComponent: root.actions
        }
    }

    Label {
        visible: root.collapsible
        x: Theme.padding.large ?? 0
        width: parent.width - 2 * x
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.variant === "large" ? Theme.padding.extraLarge ?? 0 : Theme.padding.large ?? 0
        role: root.variant === "large" ? "headline.medium" : "headline.small"
        text: root.title
        elide: Text.ElideRight
        opacity: 1 - root.collapse
    }
}
