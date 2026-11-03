// The sheet a window opens into (inside a ContainerTransform): state shape and icon, name and title, actions, the
// thumbnail in large, rolling CPU/memory/GPU/process figures, a scrub chart and the app's busiest processes. The
// preview keeps the window's own aspect (no tinted letterbox bars) and asks the shell for a capture of that size,
// only while the sheet is open.
import QtQuick
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
                icon: "my_location"
                text: "Localizar"
                onClicked: procs.locateApp(sheet.entry.app)
            }

            Button {
                objectName: "windowInfoButton"
                type: "tonal"
                icon: "live_tv"
                text: "En vivo"
                onClicked: procs.showWindowInfo(sheet.entry.address ?? "")
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
        // The preview takes at most 56 % of the row and never more than the room there is: a very tall window
        // narrows it and gives the freed width to the figures, a very wide one shortens it and leaves them compact.
        readonly property real previewWidth: Math.max(0, Math.min(width, Math.min(width * 0.56, height * sheet.aspect)))
        readonly property real previewHeight: previewWidth / Math.max(0.001, sheet.aspect)

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
                // The sheet's own (larger) capture while it is open, the row's one until the shell writes it.
                source: procs.previewAddress === sheet.address && procs.previewThumb !== ""
                    ? procs.previewThumb : (sheet.entry.thumb ?? "")
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

        Column {
            id: side

            x: big.x + big.width + body.gap
            width: Math.max(0, body.width - x)
            spacing: Theme.spacing.medium ?? 0

            Row {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Repeater {
                    model: [["CPU", Fmt.pct(sheet.stat.cpu ?? 0)], ["Memoria", Fmt.mem(sheet.stat.mem ?? 0)], ["GPU", Fmt.pct(sheet.stat.gpu ?? 0)], ["Procesos", String(sheet.stat.count ?? 0)]]

                    Rectangle {
                        required property var modelData

                        width: (parent.width - parent.spacing * 3) / 4
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
                width: parent.width
                height: Metrics.topAppBarLarge
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

            Repeater {
                model: sheet.kids

                Row {
                    required property var modelData

                    width: parent.width
                    height: Metrics.chipHeight
                    spacing: Theme.spacing.medium ?? 0

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Theme.spacing.small ?? 0
                        height: width
                        radius: width / 2
                        color: Theme["m3" + Fmt.stateColourRole(parent.modelData.state)]
                    }

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width * 0.6
                        text: parent.modelData.name + "  " + parent.modelData.pid
                        role: "body.medium"
                        elide: Text.ElideRight
                    }

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Fmt.pct(parent.modelData.cpu) + " · " + Fmt.mem(parent.modelData.mem)
                        role: "label.medium"
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }
        }
    }
}
