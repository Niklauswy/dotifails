// The sheet a window opens into (inside a ContainerTransform): state shape and icon, name and title, actions, the
// thumbnail in large, rolling CPU/memory/GPU/process figures, a scrub chart and the app's busiest processes. The
// preview keeps the window's own aspect (no tinted letterbox bars) and asks the shell for a capture of that size,
// only while the sheet is open. On a wide sheet the preview grows and the app's processes sit under it; on a tall
// one the preview keeps the full height and the processes stay beside it.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: sheet

    property var entry: ({})
    readonly property var stat: procs.stats[entry.app] ?? ({})
    readonly property var kids: { procs.stats; return procs.appProcesses(entry.app ?? ""); }
    readonly property color tintColour: (entry.tint ?? "") !== "" ? Qt.color(entry.tint) : Theme.m3primary
    readonly property string address: entry.address ?? ""
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    // The window's ratio, from Hyprland's size; the image itself or 16:9 while there is no capture yet.
    readonly property real aspect: {
        const size = entry.size;
        if (size && size.length >= 2 && size[0] > 0 && size[1] > 0)
            return size[0] / size[1];
        if (bigThumb.status === Image.Ready && bigThumb.implicitWidth > 0 && bigThumb.implicitHeight > 0)
            return bigThumb.implicitWidth / bigThumb.implicitHeight;
        return 16 / 9;
    }

    signal closeRequested
    signal showProcesses(string app)

    // The shell captures at the preview's device pixels: sharp at the size it is shown, never at a fixed 480 px.
    function requestPreview() {
        if (sheet.address && previewCaptureWidth > 0)
            procs.requestPreview(sheet.address, previewCaptureWidth);
    }
    readonly property int previewCaptureWidth: big && big.width > 0
        ? Math.max(160, Math.min(1920, Math.round(big.width * sheet.dpr))) : 0

    Component.onCompleted: Qt.callLater(sheet.requestPreview)
    onPreviewCaptureWidthChanged: requestPreview()
    Component.onDestruction: {
        if (typeof procs !== "undefined")
            procs.releasePreview(sheet.address, previewCaptureWidth);
    }

    Row {
        id: head

        x: Theme.padding.large ?? 0
        y: Theme.padding.large ?? 0
        width: parent.width - x * 2
        spacing: Theme.spacing.medium ?? 0

        StateShape {
            state: "G"
            color: Qt.tint(Theme.m3surfaceContainerHighest, Qt.alpha(sheet.tintColour, 0.32))

            AppIcon {
                anchors.centerIn: parent
                source: sheet.entry.icon ?? ""
                tint: sheet.entry.tint ?? ""
                label: sheet.entry.name ?? ""
                color: Qt.alpha(Theme.m3surface, 0)
            }
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - actions.width - parent.spacing

            Label {
                width: parent.width
                text: sheet.entry.name ?? ""
                role: "headline.small"
                elide: Text.ElideRight
            }

            Label {
                width: parent.width
                text: (sheet.entry.title ?? "") + " · espacio " + (sheet.entry.ws ?? "")
                role: "body.medium"
                color: Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
        }

        Row {
            id: actions

            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.small ?? 0

            Button {
                type: "filled"
                icon: "open_in_new"
                text: "Ir a la ventana"
                onClicked: procs.focusApp(sheet.entry.app)
            }

            Button {
                type: "tonal"
                icon: "list"
                text: "Procesos"
                onClicked: sheet.showProcesses(sheet.entry.app)
            }

            Button {
                type: "tonal"
                icon: "cancel"
                text: "Cerrar"
                containerColor: Theme.m3errorContainer
                contentRestColor: Theme.m3onErrorContainer
                onClicked: procs.closeApp(sheet.entry.app, false)
            }

            IconButton {
                icon: "close"
                onClicked: sheet.closeRequested()
            }
        }
    }

    Item {
        id: body

        anchors.top: head.bottom
        anchors.topMargin: Theme.spacing.large ?? 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.padding.large ?? 0
        anchors.rightMargin: Theme.padding.large ?? 0
        anchors.bottomMargin: Theme.padding.large ?? 0

        readonly property real gap: Theme.padding.large ?? 0
        readonly property real rowSpacing: Theme.spacing.small ?? 0
        // The rows of the app's processes: the same rows go under the preview on a wide sheet or beside it on a
        // tall one, so this is their natural height in both places.
        readonly property real rowsHeight: sheet.kids.length > 0
            ? sheet.kids.length * Metrics.chipHeight + (sheet.kids.length - 1) * rowSpacing : 0
        // Room under the preview for up to seven rows (the rest scroll): a wide sheet fills its left column this
        // way instead of leaving the bottom half empty.
        readonly property real listRoom: sheet.kids.length > 0
            ? Math.min(rowsHeight, 7 * Metrics.chipHeight + 6 * rowSpacing) : 0
        // The preview: 56 % of the width, or the full height for a tall window (never more than there is). A wide
        // window that leaves room for the rows grows to 62 % of the width and gives them the strip under it.
        readonly property real baseWidth: Math.max(0, Math.min(width * 0.56, height * sheet.aspect))
        readonly property real widePreview: Math.max(0, Math.min(width * 0.62,
            Math.max(0, height - listRoom - gap) * sheet.aspect))
        // Grow only when that does not shrink the preview: a short body keeps the base size and the rows beside.
        readonly property real previewWidth: listRoom > 0 && baseWidth < height * sheet.aspect
            && widePreview > baseWidth ? widePreview : baseWidth
        readonly property real previewHeight: previewWidth / Math.max(0.001, sheet.aspect)
        // Only a preview that takes most of the width keeps the rows under it; a tall, narrow one keeps them
        // beside it, in the figures column.
        readonly property bool listBelow: listRoom > 0 && previewWidth >= width * 0.45
            && height - previewHeight - gap >= Metrics.chipHeight

        Rectangle {
            id: big

            objectName: "appSheetPreview"
            x: 0
            width: body.previewWidth
            height: body.previewHeight
            radius: Theme.rounding.extraLarge ?? 0
            clip: true
            color: Qt.tint(Theme.m3surfaceContainerHigh, Qt.alpha(sheet.tintColour, 0.22))

            Image {
                id: bigThumb

                objectName: "appSheetThumb"
                anchors.fill: parent
                // Only the sheet's own capture (at this size): the row's small one would be shown stretched while
                // the large one is written, which is exactly the blurry preview this sheet avoids.
                source: procs.previewAddress === sheet.address ? procs.previewThumb : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                visible: status === Image.Ready
            }

            // Same aspect as the window while the shell has not written a capture yet.
            AppIcon {
                anchors.centerIn: parent
                // A very wide window leaves a short frame: no clipped emblem there.
                visible: !bigThumb.visible && big.height >= Metrics.iconButtonSize
                source: sheet.entry.icon ?? ""
                tint: sheet.entry.tint ?? ""
                label: sheet.entry.name ?? ""
                size: Math.min(Metrics.emptyEmblemSize, Math.max(Metrics.iconButtonSize, Math.min(big.width, big.height) * 0.42))
            }
        }

        // Under a wide preview: the app's processes fill the rest of the left column (and scroll if needed).
        Flickable {
            id: below

            visible: body.listBelow
            x: 0
            y: big.height + body.gap
            width: big.width
            height: Math.max(0, body.height - y)
            contentHeight: belowList.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: belowList

                width: parent.width
                spacing: body.rowSpacing

                Repeater {
                    model: body.listBelow ? sheet.kids : []

                    KidRow {}
                }
            }
        }

        ColumnLayout {
            id: side

            x: big.x + big.width + body.gap
            width: Math.max(0, body.width - x)
            height: body.height
            spacing: Theme.spacing.medium ?? 0

            Grid {
                id: figures

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                // A narrow figures column stacks the cards in two rows instead of squeezing four.
                columns: width < Metrics.drawerWidth * 2.2 ? 2 : 4
                columnSpacing: Theme.spacing.small ?? 0
                rowSpacing: Theme.spacing.small ?? 0

                Repeater {
                    model: [["CPU", Fmt.pct(sheet.stat.cpu ?? 0)], ["Memoria", Fmt.mem(sheet.stat.mem ?? 0)],
                            ["GPU", Fmt.pct(sheet.stat.gpu ?? 0)], ["Procesos", String(sheet.stat.count ?? 0)]]

                    Rectangle {
                        required property var modelData

                        width: (parent.width - parent.columnSpacing * (parent.columns - 1)) / parent.columns
                        height: Metrics.listItemThreeLine
                        radius: Theme.rounding.large ?? 0
                        color: Theme.m3surfaceContainerHigh

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            x: Theme.padding.medium ?? 0

                            Label {
                                text: parent.parent.modelData[0]
                                role: "label.medium"
                                color: Theme.m3onSurfaceVariant
                            }

                            RollingNumber {
                                text: parent.parent.modelData[1]
                                role: "title.large"
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: Metrics.topAppBarLarge
                radius: Theme.rounding.large ?? 0
                color: Theme.m3surfaceContainerHigh

                LiveChart {
                    anchors.fill: parent
                    anchors.margins: Theme.padding.medium ?? 0
                    series: [sheet.stat.history ?? []]
                    colors: [Qt.tint(Theme.m3primary, Qt.alpha(sheet.tintColour, 0.6))]
                    interval: procs.interval
                    scrub: true
                    formatValue: v => Fmt.pct(v)
                    labelAt: i => {
                        const ago = Math.round(((sheet.stat.history ?? []).length - 1 - i) * procs.interval / 1000);
                        return ago ? "hace " + ago + " s" : "ahora";
                    }
                }
            }

            // Beside a tall preview: the app's processes under the chart (a bounded height, scrollable).
            Flickable {
                visible: !body.listBelow && sheet.kids.length > 0
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(body.rowsHeight, Math.round(body.height * 0.35))
                contentHeight: besideList.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: besideList

                    width: parent.width
                    spacing: body.rowSpacing

                    Repeater {
                        model: !body.listBelow ? sheet.kids : []

                        KidRow {}
                    }
                }
            }
        }
    }

    // One process of the app: state dot, name and pid, CPU · memory. Shared by the under-preview and beside-chart
    // lists so both show the same rows.
    component KidRow: Row {
        id: kid

        required property var modelData

        width: parent ? parent.width : 0
        height: Metrics.chipHeight
        spacing: Theme.spacing.medium ?? 0

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Theme.spacing.small ?? 0
            height: width
            radius: width / 2
            color: Theme["m3" + Fmt.stateColourRole(kid.modelData.state)]
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.6
            text: kid.modelData.name + "  " + kid.modelData.pid
            role: "body.medium"
            elide: Text.ElideRight
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            text: Fmt.pct(kid.modelData.cpu) + " · " + Fmt.mem(kid.modelData.mem)
            role: "label.medium"
            color: Theme.m3onSurfaceVariant
        }
    }
}
