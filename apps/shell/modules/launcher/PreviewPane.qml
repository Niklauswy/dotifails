pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.services
import qs.modules.launcher.services
import "services/Files.js" as Files

// Large preview of the selected file, clipboard entry or snippet, with metadata underneath.
Item {
    id: root

    property var row: null
    property real scale: 1
    property bool focusedPane
    // Final pixel size requested from the image decoder, independent of the open animation.
    property size decodeSize: Qt.size(640, 400)

    readonly property bool isFile: row?.kind === "file"
    readonly property bool isClip: row?.kind === "clip"
    readonly property bool isSnippet: row?.kind === "snippet"
    readonly property bool isImageFile: isFile && !row.isDir && Files.isImage(row.path)
    readonly property bool isImageClip: isClip && row.clip_kind === "image"
    readonly property bool isColour: isClip && row.clip_kind === "color"
    property string imageSource
    property string bodyText
    property var info: []
    property string stamp: row ? row.key : ""

    onStampChanged: {
        imageSource = "";
        bodyText = "";
        info = [];
        debounce.restart();
    }

    function when(seconds: real): string {
        return Qt.formatDateTime(new Date(seconds * 1000), "d MMM yyyy · HH:mm");
    }

    function size(bytes: real): string {
        if (bytes < 1024)
            return bytes + " B";
        const units = ["KB", "MB", "GB", "TB"];
        let v = bytes / 1024, i = 0;
        while (v >= 1024 && i < units.length - 1) {
            v /= 1024;
            i++;
        }
        return v.toFixed(v < 10 ? 1 : 0) + " " + units[i];
    }

    function describe(): void {
        const r = row;
        if (!r)
            return;
        if (isFile) {
            imageSource = isImageFile ? "file://" + r.path : "";
            statProc.command = ["stat", "-L", "-c", "%s|%Y|%F", r.path];
            statProc.running = true;
            if (!isImageFile && !r.isDir) {
                const kind = Files.icon(r.path, false);
                if (kind === "code" || kind === "description") {
                    headProc.command = ["head", "-c", "6000", r.path];
                    headProc.running = true;
                } else if (kind === "picture_as_pdf" || kind === "video" || kind === "slideshow") {
                    pyProc.command = ["python3", "-I", LauncherData.script, "preview", r.path];
                    pyProc.running = true;
                }
            }
        } else if (isImageClip) {
            LauncherIndex.exportClip(r.id, path => {
                if (root.row?.key === r.key)
                    root.imageSource = "file://" + path;
            });
            info = [["Type", "Image"], ["Copied", when(r.stamp)]];
        } else if (isClip) {
            bodyText = r.value;
            info = [["Type", r.clip_kind[0].toUpperCase() + r.clip_kind.slice(1)], ["Copied", when(r.stamp)], ["Characters", String(r.value.length)]];
        } else if (isSnippet) {
            bodyText = r.value;
            info = [["Abbreviation", r.shortcut || "—"], ["Characters", String(r.body.length)]];
        }
    }

    Timer {
        id: debounce

        interval: 90
        onTriggered: root.describe()
    }

    Process {
        id: statProc

        stdout: StdioCollector {
            onStreamFinished: {
                const p = text.trim().split("|");
                if (p.length < 3 || !root.row)
                    return;
                root.info = [["Size", root.size(parseInt(p[0]))], ["Modified", root.when(parseInt(p[1]))], ["Path", root.row.path]];
            }
        }
    }

    Process {
        id: headProc

        stdout: StdioCollector {
            onStreamFinished: root.bodyText = text
        }
    }

    Process {
        id: pyProc

        environment: ({QT_QPA_PLATFORM: "offscreen"})
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse(text);
                    root.imageSource = d.image || "";
                    root.bodyText = d.text || "";
                } catch (e) {}
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Tokens.spacing.medium

        Rectangle {
            id: stage

            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Tokens.rounding.medium
            color: Colours.tPalette.m3surfaceContainer
            clip: true

            Image {
                anchors.fill: parent
                anchors.margins: Tokens.padding.small
                visible: root.imageSource !== ""
                source: root.imageSource
                sourceSize: root.decodeSize
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
                opacity: status === Image.Ready ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            Rectangle {
                anchors.centerIn: parent
                visible: root.isColour
                width: Math.min(parent.width, parent.height) * 0.6
                height: width
                radius: Tokens.rounding.large
                color: root.isColour ? root.row.value : "transparent" // theme-exception: user colour sample from clipboard
            }

            Flickable {
                id: textFlick

                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                visible: root.imageSource === "" && root.bodyText !== "" && !root.isColour
                contentHeight: body.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                StyledText {
                    id: body

                    width: textFlick.width
                    text: root.bodyText
                    font: root.isFile ? Tokens.font.mono.small : Tokens.font.body.medium
                    wrapMode: Text.WrapAnywhere
                    color: Colours.palette.m3onSurface
                }
            }

            MaterialIcon {
                anchors.centerIn: parent
                visible: root.imageSource === "" && root.bodyText === "" && !root.isColour
                text: root.row?.icon ?? "draft"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.builders.extraLarge.scale(1.5).build()
            }

            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "transparent"
                border.width: root.focusedPane ? 2 : 0
                border.color: Colours.palette.m3primary
            }
        }

        Column {
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall

            Repeater {
                model: root.info

                RowLayout {
                    id: infoRow

                    required property var modelData

                    width: parent.width
                    spacing: Tokens.spacing.medium

                    StyledText {
                        Layout.preferredWidth: 92 * root.scale
                        text: infoRow.modelData[0]
                        font: Tokens.font.label.medium
                        color: Colours.palette.m3onSurfaceVariant
                    }
                    StyledText {
                        Layout.fillWidth: true
                        text: infoRow.modelData[1]
                        font: Tokens.font.label.medium
                        elide: infoRow.modelData[0] === "Path" ? Text.ElideMiddle : Text.ElideRight
                    }
                }
            }
        }
    }

    function scrollBy(dy: real): void {
        textFlick.contentY = Math.max(0, Math.min(textFlick.contentHeight - textFlick.height, textFlick.contentY + dy));
    }
}
