pragma ComponentBehavior: Bound

import QtQuick
import Wysun
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.launcher.services

Item {
    id: root

    required property ScreenState screenState
    required property var panels
    required property real maxHeight

    readonly property int padding: Tokens.padding.large
    readonly property int rounding: Tokens.rounding.extraLarge

    implicitWidth: listWrapper.width + padding * 2
    implicitHeight: search.height + listWrapper.height + padding + search.anchors.bottomMargin

    Item {
        id: listWrapper

        implicitWidth: list.width
        implicitHeight: list.height + root.padding

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: search.top
        anchors.bottomMargin: root.padding

        ContentList {
            id: list

            content: root
            screenState: root.screenState
            panels: root.panels
            maxHeight: root.maxHeight - search.implicitHeight - root.padding * 3
            search: search
            padding: root.padding
            rounding: root.rounding
        }
    }

    SearchBar {
        id: search

        objectName: "launcherSearch"

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: root.padding
        anchors.bottomMargin: CUtils.clamp(root.padding - Config.border.thickness, 0, root.padding)

        topPadding: Math.round((Tokens.padding.medium + Tokens.padding.large) / 2)
        bottomPadding: Math.round((Tokens.padding.medium + Tokens.padding.large) / 2)

        placeholderText: Tr.tr("Type \"%1\" for commands, clip, files, snip, win, emoji or run").arg(GlobalConfig.launcher.actionPrefix)

        onAccepted: {
            const currentItem = list.currentList?.currentItem;
            const prefix = GlobalConfig.launcher.actionPrefix;
            if (!currentItem) {
                // No match: like the Qt palette, fall back to a web search.
                const query = text.trim();
                if (query && !text.startsWith(prefix) && LauncherData.activate(LauncherData.webRow(query)))
                    root.screenState.launcher = false;
                return;
            }
            if (list.showWallpapers) {
                if (Colours.scheme === "dynamic" && currentItem.modelData.path !== Wallpapers.actualCurrent)
                    Wallpapers.previewColourLock = true;
                Wallpapers.setWallpaper(currentItem.modelData.path);
                root.screenState.launcher = false;
            } else if (list.displayState === "data" || list.displayState === "run" || list.displayState === "calc") {
                currentItem.onClicked();
            } else if (text.startsWith(prefix)) {
                currentItem.modelData.onClicked(list.currentList);
            } else {
                Apps.launch(currentItem.modelData);
                root.screenState.launcher = false;
            }
        }

        Keys.onUpPressed: list.currentList?.decrementCurrentIndex()
        Keys.onDownPressed: list.currentList?.incrementCurrentIndex()

        Keys.onEscapePressed: root.screenState.launcher = false

        Keys.onPressed: event => {
            const row = list.displayState === "data" ? list.currentList?.currentItem?.modelData : null;
            if (row) {
                // Row actions: Ctrl+Delete removes history/snippets, Shift+Enter opens the
                // containing folder, Ctrl+Enter copies a file path.
                if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Delete && LauncherData.remove(row)) {
                    event.accepted = true;
                    return;
                }
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    if ((event.modifiers & Qt.ShiftModifier) && LauncherData.openFolder(row)) {
                        root.screenState.launcher = false;
                        event.accepted = true;
                        return;
                    }
                    if ((event.modifiers & Qt.ControlModifier) && (LauncherData.paste(row) || LauncherData.copyPath(row))) {
                        root.screenState.launcher = false;
                        event.accepted = true;
                        return;
                    }
                }
            }

            if (!GlobalConfig.launcher.vimKeybinds)
                return;

            if (event.modifiers & Qt.ControlModifier) {
                if (event.key === Qt.Key_J || event.key === Qt.Key_N) {
                    list.currentList?.incrementCurrentIndex();
                    event.accepted = true;
                } else if (event.key === Qt.Key_K || event.key === Qt.Key_P) {
                    list.currentList?.decrementCurrentIndex();
                    event.accepted = true;
                }
            } else if (event.key === Qt.Key_Tab) {
                list.currentList?.incrementCurrentIndex();
                event.accepted = true;
            } else if (event.key === Qt.Key_Backtab || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))) {
                list.currentList?.decrementCurrentIndex();
                event.accepted = true;
            }
        }

        Component.onCompleted: {
            forceActiveFocus();
            if (root.screenState.launcherQuery) {
                text = root.screenState.launcherQuery;
                root.screenState.launcherQuery = "";
            }
        }

        Connections {
            function onLauncherChanged(): void {
                if (!root.screenState.launcher)
                    search.text = "";
            }

            function onLauncherQueryChanged(): void {
                if (root.screenState.launcherQuery) {
                    search.text = root.screenState.launcherQuery;
                    root.screenState.launcherQuery = "";
                    search.forceActiveFocus();
                }
            }

            function onSessionChanged(): void {
                if (!root.screenState.session)
                    search.forceActiveFocus();
            }

            target: root.screenState
        }
    }
}
