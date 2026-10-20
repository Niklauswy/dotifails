pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "Logic.js" as Logic
import "Icons.js" as Icons

PanelWindow {
    id: popup
    required property var preferences
    required property var controller
    required property var clock
    screen: controller.popupScreen
    visible: controller.opened
    anchors { top: true; right: true }
    margins { top: preferences.bar.offset + preferences.bar.height + 12; right: 12 }
    implicitWidth: Math.max(1, Math.min(520, (screen?.width || 520) - 24))
    implicitHeight: Math.max(1, Math.min(620, (screen?.height || 720) - margins.top - 12))
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "wysun-surface"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    readonly property bool windowsMode: controller.surface === "windows"
    readonly property bool sessionMode: controller.surface === "session"
    readonly property var monitor: screen ? Hyprland.monitorFor(screen) : null
    readonly property var windowRows: Hyprland.toplevels.values.filter(w =>
        w.monitor === monitor && w.title.toLocaleLowerCase().indexOf(search.text.toLocaleLowerCase()) >= 0)
    readonly property var appRows: Logic.filteredApplications(search.text).filter(app => app.command !== "launcher")

    function focusInitial() {
        if (sessionMode) lockButton.forceActiveFocus();
        else search.forceActiveFocus();
    }

    onVisibleChanged: {
        if (visible) {
            search.text = "";
            list.currentIndex = 0;
            Qt.callLater(function() { popup.focusInitial(); grab.active = true; });
        } else grab.active = false;
    }
    Connections {
        target: popup.controller
        function onSurfaceChanged() {
            search.text = "";
            list.currentIndex = 0;
            if (popup.visible) popup.focusInitial();
        }
    }
    HyprlandFocusGrab {
        id: grab
        windows: [popup]
        onCleared: popup.controller.close()
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: popup.visible
        onActivated: popup.controller.close()
    }
    Rectangle {
        anchors.fill: parent
        radius: popup.preferences.palette.radius
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(popup.preferences.palette.surface, popup.preferences.appearance.opacity) }
            GradientStop { position: 0.52; color: Qt.alpha(popup.preferences.palette.background, popup.preferences.appearance.opacity) }
            GradientStop { position: 1; color: Qt.alpha(Qt.darker(popup.preferences.palette.background, 1.12), Math.min(1, popup.preferences.appearance.opacity + 0.05)) }
        }
        border.width: 1
        border.color: Qt.alpha(popup.preferences.palette.foreground, 0.28)
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: Math.max(0, parent.radius - 1)
            color: "transparent"
            border.width: 1
            border.color: "#0cffffff"
        }
    }
    FocusScope {
        anchors.fill: parent
        anchors.margins: 20
        focus: true
        Keys.onEscapePressed: popup.controller.close()
        Keys.onPressed: event => {
            if (event.modifiers === Qt.ControlModifier && event.key === Qt.Key_1) {
                popup.controller.show("menu", popup.screen.name); event.accepted = true;
            } else if (event.modifiers === Qt.ControlModifier && event.key === Qt.Key_2) {
                popup.controller.show("windows", popup.screen.name); event.accepted = true;
            } else if (event.modifiers === Qt.ControlModifier && event.key === Qt.Key_3) {
                popup.controller.show("session", popup.screen.name); event.accepted = true;
            }
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Text {
                        text: "WYSUN  /  ESCRITORIO"
                        color: popup.preferences.palette.muted
                        font { family: "Inter"; pixelSize: 10; weight: Font.DemiBold; letterSpacing: 1.5 }
                    }
                    Text {
                        text: popup.windowsMode ? "Ventanas" : (popup.sessionMode ? "Sesión" : "Centro de escritorio")
                        color: popup.preferences.palette.foreground
                        font { family: "Inter"; pixelSize: 23; weight: Font.DemiBold }
                        Accessible.role: Accessible.Heading
                    }
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: popup.screen?.name || ""
                    color: popup.preferences.palette.muted
                    font { family: "Inter"; pixelSize: 12 }
                }
                ShellButton {
                    preferences: popup.preferences
                    text: ""
                    glyph: "x"
                    description: "Cerrar · Escape"
                    onClicked: popup.controller.close()
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                ShellButton {
                    preferences: popup.preferences
                    text: "Accesos"
                    description: "Accesos del escritorio · Control 1"
                    Layout.fillWidth: true
                    selected: !popup.windowsMode && !popup.sessionMode
                    onClicked: popup.controller.show("menu", popup.screen.name)
                }
                ShellButton {
                    preferences: popup.preferences
                    text: "Ventanas"
                    description: "Ventanas · Control 2"
                    Layout.fillWidth: true
                    selected: popup.windowsMode
                    onClicked: popup.controller.show("windows", popup.screen.name)
                }
                ShellButton {
                    preferences: popup.preferences
                    text: "Sesión"
                    description: "Sesión · Control 3"
                    Layout.fillWidth: true
                    selected: popup.sessionMode
                    onClicked: popup.controller.show("session", popup.screen.name)
                }
            }
            ShellButton {
                Layout.fillWidth: true
                implicitHeight: 44
                visible: !popup.windowsMode && !popup.sessionMode
                preferences: popup.preferences
                glyph: "search"
                text: "Abrir lanzador Wysun"
                textAlignment: Text.AlignLeft
                description: "Abrir el lanzador principal de aplicaciones, cálculo y búsqueda"
                onClicked: popup.controller.launch("launcher")
            }
            TextField {
                id: search
                Layout.fillWidth: true
                visible: !popup.sessionMode
                focus: !popup.sessionMode
                placeholderText: popup.windowsMode ? "Buscar ventanas de esta pantalla…" : "Filtrar accesos del escritorio…"
                Accessible.name: placeholderText
                color: popup.preferences.palette.foreground
                placeholderTextColor: popup.preferences.palette.muted
                selectionColor: popup.preferences.palette.accent
                selectedTextColor: popup.preferences.palette.background
                font { family: "Inter"; pixelSize: 13 }
                padding: 10
                background: Rectangle {
                    radius: 10
                    color: popup.preferences.palette.surface
                    border.width: 1
                    border.color: Qt.alpha(popup.preferences.palette.accent, search.activeFocus ? 1 : 0.2)
                }
                onTextChanged: list.currentIndex = 0
                onAccepted: list.activateCurrent()
                Keys.onDownPressed: { list.forceActiveFocus(); if (list.currentIndex < 0) list.currentIndex = 0; }
            }
            Text {
                visible: !popup.sessionMode
                text: popup.windowsMode ? "VENTANAS DE ESTA PANTALLA" : "ACCESOS A TUS HERRAMIENTAS"
                color: popup.preferences.palette.muted
                font { family: "Inter"; pixelSize: 11; weight: Font.DemiBold; letterSpacing: 1 }
            }
            Flickable {
                visible: popup.windowsMode
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                contentWidth: workspaceRow.implicitWidth
                clip: true
                Row {
                    id: workspaceRow
                    spacing: 4
                    Repeater {
                        model: Logic.sortWorkspaces(Hyprland.workspaces.values.filter(w => w.monitor === popup.monitor))
                        ShellButton {
                            required property var modelData
                            preferences: popup.preferences
                            text: Logic.workspaceLabel(modelData)
                            description: "Ir al escritorio " + Logic.workspaceLabel(modelData)
                            selected: modelData.active
                            onClicked: { popup.controller.close(); modelData.activate(); }
                        }
                    }
                }
            }
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !popup.sessionMode
                model: popup.windowsMode ? popup.windowRows : popup.appRows
                clip: true
                spacing: 4
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationWraps: true
                ScrollBar.vertical: ScrollBar {}
                function activateCurrent() {
                    var item = model[currentIndex];
                    if (!item) return;
                    if (popup.windowsMode) popup.controller.activateWindow(item);
                    else popup.controller.launch(item.command);
                }
                Keys.onReturnPressed: activateCurrent()
                Keys.onEnterPressed: activateCurrent()
                Keys.onUpPressed: {
                    if (currentIndex <= 0) search.forceActiveFocus();
                    else decrementCurrentIndex();
                }
                delegate: ShellButton {
                    id: row
                    required property var modelData
                    required property int index
                    width: list.width
                    implicitHeight: 57
                    preferences: popup.preferences
                    selected: ListView.isCurrentItem
                    description: popup.windowsMode ? (modelData?.title || "Ventana") + ", escritorio " + Logic.workspaceLabel(modelData?.workspace) : (modelData?.title || "") + ", " + (modelData?.detail || "")
                    onClicked: {
                        list.currentIndex = index;
                        list.activateCurrent();
                    }
                    contentItem: RowLayout {
                        spacing: 12
                        Rectangle {
                            readonly property string tint: Icons.accents[row.modelData?.command] || popup.preferences.palette.accent
                            Layout.preferredWidth: 30
                            Layout.preferredHeight: 30
                            radius: 7
                            color: Qt.alpha(tint, 0.105)
                            border.width: 1
                            border.color: Qt.alpha(tint, 0.15)
                            Image {
                                anchors.centerIn: parent
                                width: 18; height: 18
                                sourceSize.width: 36; sourceSize.height: 36
                                source: Icons.source(popup.windowsMode ? "panels-top-left" : (row.modelData?.icon || "file-text"), parent.tint)
                            }
                        }
                        ColumnLayout {
                            spacing: 3
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: row.modelData?.title || "Ventana sin título"
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: popup.preferences.palette.foreground
                                font { family: "Inter"; pixelSize: 13; weight: Font.Medium }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: popup.windowsMode ? "Escritorio " + (Logic.workspaceLabel(row.modelData?.workspace) || "—") + (row.modelData?.activated ? " · Activa" : "") : (row.modelData?.detail || "")
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: popup.preferences.palette.muted
                                font { family: "Inter"; pixelSize: 11 }
                            }
                        }
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 3; height: Math.max(0, parent.height - 24)
                        radius: 1.5
                        visible: row.selected
                        color: popup.preferences.palette.accent
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: list.count === 0
                    text: popup.windowsMode ? "No hay ventanas coincidentes en esta pantalla." : "No hay resultados."
                    color: popup.preferences.palette.muted
                    width: parent.width
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: popup.sessionMode
                spacing: 12
                Text {
                    text: Qt.formatDateTime(popup.clock.date, "hh:mm")
                    color: popup.preferences.palette.foreground
                    font { family: "Inter"; pixelSize: 48; weight: Font.Light }
                }
                Text {
                    text: Qt.formatDateTime(popup.clock.date, "dddd d 'de' MMMM")
                    color: popup.preferences.palette.muted
                    font { family: "Inter"; pixelSize: 15 }
                }
                ShellButton {
                    id: lockButton
                    Layout.fillWidth: true
                    preferences: popup.preferences
                    text: "Bloquear sesión"
                    glyph: "lock"
                    textAlignment: Text.AlignLeft
                    description: "Bloquear mediante el bloqueo seguro de la sesión"
                    onClicked: popup.controller.launch("lock")
                }
                ShellButton {
                    Layout.fillWidth: true
                    preferences: popup.preferences
                    text: "Energía y sesión…"
                    glyph: "power"
                    textAlignment: Text.AlignLeft
                    onClicked: popup.controller.launch("power")
                }
                ShellButton {
                    Layout.fillWidth: true
                    preferences: popup.preferences
                    text: "Notificaciones y concentración…"
                    glyph: "bell"
                    textAlignment: Text.AlignLeft
                    onClicked: popup.controller.launch("notifications")
                }
                ShellButton {
                    Layout.fillWidth: true
                    preferences: popup.preferences
                    text: "Preferencias…"
                    glyph: "settings-2"
                    textAlignment: Text.AlignLeft
                    onClicked: popup.controller.launch("settings")
                }
                Item { Layout.fillHeight: true }
            }
            Text {
                Layout.fillWidth: true
                visible: popup.controller.errorMessage !== ""
                text: popup.controller.errorMessage
                color: popup.preferences.palette.foreground
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
                Accessible.role: Accessible.AlertMessage
            }
            Text {
                text: "↑ ↓ navegar   ·   Enter abrir   ·   Esc cerrar"
                color: popup.preferences.palette.muted
                font { family: "Inter"; pixelSize: 11 }
            }
        }
    }
}
