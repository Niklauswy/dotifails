pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Services.Notifications
import M3Shapes
import Wysun.Components
import Wysun.Config
import qs.components
import qs.components.controls
import qs.components.effects
import qs.services
import qs.utils

StyledRect {
    id: root

    required property NotifData modelData
    readonly property string imageUrl: Icons.usableImage(modelData.image)
    readonly property bool hasImage: imageUrl.length > 0
    readonly property bool hasAppIcon: modelData.appIcon.length > 0
    readonly property bool critical: modelData.urgency === NotificationUrgency.Critical
    readonly property bool low: modelData.urgency === NotificationUrgency.Low
    // Icon-theme glyphs often do not exist; then the card draws a Material symbol chosen from the app, icon name and summary.
    readonly property string themeIcon: Icons.appIconPath(modelData.appIcon, modelData.appName, modelData.hints)
    readonly property string symbol: Icons.notifSymbol(modelData.appIcon, modelData.appName, modelData.summary, modelData.urgency)
    readonly property bool hasProgress: modelData.hints?.value !== undefined && modelData.hints?.value !== null
    readonly property real progress: Math.max(0, Math.min(100, Number(modelData.hints?.value ?? 0))) / 100
    readonly property color toneColour: critical ? Colours.palette.m3error : low ? Colours.palette.m3secondaryContainer : Colours.palette.m3primaryContainer
    readonly property color onToneColour: critical ? Colours.palette.m3onError : low ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onPrimaryContainer
    readonly property color textColour: critical ? Colours.palette.m3onErrorContainer : Colours.palette.m3onSurface
    readonly property color subtleColour: critical ? Colours.palette.m3onErrorContainer : Colours.palette.m3onSurfaceVariant
    readonly property int bodyTextFormat: /[<*_`#\[\]]/.test(modelData.body) ? Text.MarkdownText : Text.PlainText
    readonly property int nonAnimHeight: summary.implicitHeight + (root.expanded ? Tokens.spacing.extraSmall * 2 + appName.height + body.height + actions.height + actions.anchors.topMargin : bodyPreview.height) + (hasProgress ? progressBar.implicitHeight + Tokens.spacing.small : 0) + inner.anchors.margins * 2
    property bool expanded: Config.notifs.openExpanded || modelData.actions.length > 0

    color: critical ? Colours.palette.m3errorContainer : low ? Colours.tPalette.m3surfaceContainer : Colours.tPalette.m3surfaceContainerHigh
    radius: Tokens.rounding.extraLarge

    implicitHeight: inner.implicitHeight

    x: implicitWidth
    Component.onCompleted: {
        x = 0;
        modelData.lock(this);
    }
    Component.onDestruction: modelData.unlock(this)

    Behavior on x {
        Anim {
            easing: Tokens.anim.emphasizedDecel
        }
    }

    MouseArea {
        property int startY

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.expanded && body.hoveredLink ? Qt.PointingHandCursor : pressed ? Qt.ClosedHandCursor : undefined
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        preventStealing: true

        onEntered: root.modelData.timer.stop()
        onExited: {
            if (!pressed)
                root.modelData.timer.start();
        }

        drag.target: parent
        drag.axis: Drag.XAxis

        onPressed: event => {
            root.modelData.timer.stop();
            startY = event.y;
            if (event.button === Qt.MiddleButton)
                root.modelData.close();
        }
        onReleased: event => {
            if (!containsMouse)
                root.modelData.timer.start();

            if (Math.abs(root.x) < root.implicitWidth * Config.notifs.clearThreshold)
                root.x = 0;
            else
                root.modelData.popup = false;
        }
        onPositionChanged: event => {
            if (pressed) {
                const diffY = event.y - startY;
                if (Math.abs(diffY) > Config.notifs.expandThreshold)
                    root.expanded = diffY > 0;
            }
        }
        onClicked: event => {
            if (!GlobalConfig.notifs.actionOnClick || event.button !== Qt.LeftButton)
                return;

            const actions = root.modelData.actions;
            if (actions.length === 1)
                actions[0].invoke();
        }

        Item {
            id: inner

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.medium

            implicitHeight: root.nonAnimHeight

            Behavior on implicitHeight {
                Anim {}
            }

            // Photo/avatar sent with the notification, clipped to a soft squircle.
            Loader {
                id: image

                asynchronous: true
                active: root.hasImage

                anchors.left: parent.left
                anchors.top: parent.top
                width: TokenConfig.sizes.notifs.image
                height: TokenConfig.sizes.notifs.image
                visible: true

                sourceComponent: ClipRect {
                    radius: Tokens.rounding.largeIncreased
                    color: root.toneColour
                    implicitWidth: TokenConfig.sizes.notifs.image
                    implicitHeight: TokenConfig.sizes.notifs.image

                    Image {
                        anchors.fill: parent
                        source: Qt.resolvedUrl(root.imageUrl)
                        fillMode: Image.PreserveAspectCrop
                        sourceSize: {
                            const size = TokenConfig.sizes.notifs.image * ((QsWindow.window as QsWindow)?.devicePixelRatio ?? 1);
                            return Qt.size(size, size);
                        }
                        cache: false
                        asynchronous: true
                    }
                }
            }

            // Tonal expressive badge: cookie for normal, soft burst for critical, circle for low priority.
            Item {
                id: appIcon

                readonly property int size: root.hasImage ? Tokens.sizes.notifs.badge : TokenConfig.sizes.notifs.image

                anchors.horizontalCenter: root.hasImage ? undefined : image.horizontalCenter
                anchors.verticalCenter: root.hasImage ? undefined : image.verticalCenter
                anchors.right: root.hasImage ? image.right : undefined
                anchors.bottom: root.hasImage ? image.bottom : undefined
                anchors.left: root.hasImage ? undefined : parent.left
                anchors.top: root.hasImage ? undefined : parent.top
                implicitWidth: size
                implicitHeight: size
                width: size
                height: size

                MaterialShape {
                    anchors.centerIn: parent
                    implicitSize: appIcon.size * (root.critical ? 0.96 : 0.92)
                    color: root.themeIcon.length > 0 ? Colours.palette.m3surfaceContainerHighest : root.toneColour
                    shape: root.themeIcon.length > 0 ? MaterialShape.Circle : root.critical ? MaterialShape.SoftBurst : root.low ? MaterialShape.Circle : MaterialShape.Cookie9Sided

                    Behavior on color {
                        CAnim {}
                    }
                }

                // Real app icons keep their own colours; only monochrome (symbolic) ones are tinted.
                Loader {
                    anchors.centerIn: parent
                    asynchronous: true
                    active: root.themeIcon.length > 0

                    width: Math.round(appIcon.size * 0.66)
                    height: width

                    sourceComponent: root.themeIcon.includes("symbolic") ? tintedIcon : plainIcon
                }

                Component {
                    id: tintedIcon

                    ColouredIcon {
                        anchors.fill: parent
                        source: root.themeIcon
                        colour: root.onToneColour
                        layer.enabled: true
                    }
                }

                Component {
                    id: plainIcon

                    Image {
                        anchors.fill: parent
                        source: Qt.resolvedUrl(root.themeIcon)
                        sourceSize: Qt.size(width * ((QsWindow.window as QsWindow)?.devicePixelRatio ?? 1), height * ((QsWindow.window as QsWindow)?.devicePixelRatio ?? 1))
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        asynchronous: true
                    }
                }

                StyledText {
                    anchors.centerIn: parent
                    visible: root.themeIcon.length === 0 && root.symbol.length === 0
                    text: (root.modelData.appName || "?").charAt(0).toUpperCase()
                    color: root.onToneColour
                    font: root.hasImage ? Tokens.font.label.medium : Tokens.font.title.medium
                }

                MaterialIcon {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: 1
                    visible: root.themeIcon.length === 0 && root.symbol.length > 0
                    text: root.symbol
                    color: root.onToneColour
                    fontStyle: root.hasImage ? Tokens.font.icon.small : Tokens.font.icon.large
                    fill: 1
                }
            }

            StyledProgressBar {
                id: progressBar

                visible: root.hasProgress
                anchors.left: summary.left
                anchors.right: expandBtn.left
                anchors.rightMargin: Tokens.spacing.small
                // Sits under whichever text block is showing (preview when collapsed, full body when expanded).
                y: (root.expanded ? body.y + body.height : bodyPreview.y + bodyPreview.height) + Tokens.spacing.small
                implicitHeight: Tokens.padding.small
                value: root.progress
                fgColour: root.critical ? Colours.palette.m3onErrorContainer : Colours.palette.m3primary
                bgColour: root.critical ? Colours.palette.m3error : Colours.palette.m3secondaryContainer

                Behavior on y {
                    Anim {}
                }
            }

            StyledText {
                id: appName

                anchors.top: parent.top
                anchors.left: image.right
                anchors.leftMargin: Tokens.spacing.medium

                animate: true
                text: appNameMetrics.elidedText
                maximumLineCount: 1
                color: root.subtleColour
                font: Tokens.font.label.medium

                opacity: root.expanded ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            TextMetrics {
                id: appNameMetrics

                text: root.modelData.appName
                font: appName.font
                elide: Text.ElideRight
                elideWidth: expandBtn.x - time.width - timeSep.width - summary.x - root.Tokens.spacing.small * 3
            }

            StyledText {
                id: summary

                anchors.top: parent.top
                anchors.left: image.right
                anchors.leftMargin: Tokens.spacing.medium

                animate: true
                text: summaryMetrics.elidedText
                maximumLineCount: 1
                height: implicitHeight
                color: root.textColour
                font: Tokens.font.title.small

                states: State {
                    name: "expanded"
                    when: root.expanded

                    PropertyChanges {
                        summary.maximumLineCount: undefined
                        summary.anchors.topMargin: root.Tokens.spacing.extraSmall
                        bodyPreview.anchors.topMargin: root.Tokens.spacing.extraSmall
                        body.anchors.topMargin: root.Tokens.spacing.extraSmall
                    }

                    AnchorChanges {
                        target: summary
                        anchors.top: appName.bottom
                    }
                }

                transitions: Transition {
                    PropertyAction {
                        target: summary
                        property: "maximumLineCount"
                    }
                    Anim {
                        property: "topMargin"
                    }
                    AnchorAnim {}
                }

                Behavior on height {
                    Anim {}
                }
            }

            TextMetrics {
                id: summaryMetrics

                text: root.modelData.summary
                font: summary.font
                elide: Text.ElideRight
                elideWidth: expandBtn.x - time.width - timeSep.width - summary.x - root.Tokens.spacing.small * 3
            }

            StyledText {
                id: timeSep

                anchors.top: parent.top
                anchors.left: summary.right
                anchors.leftMargin: Tokens.spacing.small

                text: "•"
                color: root.subtleColour
                font: Tokens.font.body.small

                states: State {
                    name: "expanded"
                    when: root.expanded

                    AnchorChanges {
                        target: timeSep
                        anchors.left: appName.right
                    }
                }

                transitions: Transition {
                    AnchorAnim {}
                }
            }

            StyledText {
                id: time

                anchors.top: parent.top
                anchors.left: timeSep.right
                anchors.leftMargin: Tokens.spacing.small

                animate: true
                horizontalAlignment: Text.AlignLeft
                text: root.modelData.timeStr
                color: root.subtleColour
                font: Tokens.font.body.small
            }

            Item {
                id: expandBtn

                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: -Tokens.padding.extraSmall

                implicitWidth: expandIcon.implicitHeight
                implicitHeight: expandIcon.implicitHeight

                StateLayer {
                    radius: Tokens.rounding.full
                    color: root.textColour
                    onClicked: root.expanded = !root.expanded
                }

                MaterialIcon {
                    id: expandIcon

                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: root.expanded ? -1 : 1
                    text: "expand_more"
                    fontStyle: Tokens.font.icon.medium
                    rotation: root.expanded ? 180 : 0

                    Behavior on anchors.verticalCenterOffset {
                        Anim {}
                    }

                    Behavior on rotation {
                        Anim {}
                    }
                }
            }

            StyledText {
                id: bodyPreview

                anchors.left: summary.left
                anchors.right: expandBtn.left
                anchors.top: summary.bottom
                anchors.rightMargin: Tokens.spacing.small

                animate: true
                textFormat: root.bodyTextFormat
                text: bodyPreviewMetrics.elidedText
                color: root.subtleColour
                font: Tokens.font.body.small

                opacity: root.expanded ? 0 : 1

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            TextMetrics {
                id: bodyPreviewMetrics

                text: root.modelData.body
                font: bodyPreview.font
                elide: Text.ElideRight
                elideWidth: bodyPreview.width
            }

            StyledText {
                id: body

                anchors.left: summary.left
                anchors.right: expandBtn.left
                anchors.top: summary.bottom
                anchors.rightMargin: Tokens.spacing.small

                animate: true
                textFormat: root.bodyTextFormat
                text: root.modelData.body
                color: root.subtleColour
                font: Tokens.font.body.small
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                height: text ? implicitHeight : 0

                onLinkActivated: link => {
                    if (!root.expanded)
                        return;

                    Qt.openUrlExternally(link);
                    root.modelData.popup = false;
                }

                opacity: root.expanded ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            ButtonRow {
                id: actions

                anchors.left: body.left
                anchors.right: body.right
                anchors.top: body.bottom
                anchors.topMargin: Tokens.spacing.small

                spacing: Tokens.spacing.extraSmall
                opacity: root.expanded ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }

                IconButton {
                    isRound: true
                    shapeMorph: true
                    fillWidth: root.modelData.actions.length === 0
                    inactiveColour: root.critical ? Colours.palette.m3error : Colours.palette.m3secondaryContainer
                    inactiveOnColour: root.critical ? Colours.palette.m3onError : Colours.palette.m3onSecondaryContainer
                    icon: "close"
                    padding: Tokens.padding.extraSmall
                    onClicked: root.modelData.close()
                }

                Repeater {
                    model: root.modelData.actions

                    TextButton {
                        required property var modelData

                        isRound: true
                        shapeMorph: true
                        fillWidth: true
                        inactiveColour: root.critical ? Colours.palette.m3error : Colours.palette.m3secondaryContainer
                        inactiveOnColour: root.critical ? Colours.palette.m3onError : Colours.palette.m3onSecondaryContainer
                        text: modelData.text
                        onClicked: modelData.invoke()

                        label.horizontalAlignment: Text.AlignHCenter
                        label.anchors.left: left
                        label.anchors.right: right
                        label.anchors.verticalCenter: verticalCenter
                        label.anchors.centerIn: undefined
                        label.anchors.margins: Tokens.padding.medium
                        label.elide: Text.ElideRight
                    }
                }

                IconButton {
                    visible: root.modelData.actions.length < 2
                    isRound: true
                    shapeMorph: true
                    fillWidth: root.modelData.actions.length === 0
                    inactiveColour: root.critical ? Colours.palette.m3error : Colours.palette.m3secondaryContainer
                    inactiveOnColour: root.critical ? Colours.palette.m3onError : Colours.palette.m3onSecondaryContainer
                    icon: copyTimer.running ? "inventory" : "content_copy"
                    padding: Tokens.padding.extraSmall
                    onClicked: {
                        Quickshell.clipboardText = root.modelData.body;
                        copyTimer.restart();
                    }
                    label.animate: true

                    Timer {
                        id: copyTimer

                        interval: 3000
                    }
                }
            }
        }
    }
}
