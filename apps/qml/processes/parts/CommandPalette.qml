// Ctrl+K: every action on the selected process, a jump to any process by name and the sections, filtered as you
// type; ↑/↓ choose, Enter runs, Escape closes. It drops in with the default spatial spring.
import QtQuick
import WysunM3

Item {
    id: root

    property bool opened
    property int current: 0
    readonly property var sel: procs.selected
    readonly property string selName: sel.title ?? ""
    readonly property var entries: {
        const q = input.text.toLowerCase();
        const actions = sel.key ? [
            {group: "Acciones", icon: "cancel", text: "Terminar " + selName, keys: "Supr", run: () => procs.act("terminate")},
            {group: "Acciones", icon: "bolt", text: "Forzar el cierre de " + selName, keys: "⇧ Supr", run: () => procs.act("kill")},
            {group: "Acciones", icon: sel.state === "T" ? "play_arrow" : "pause", text: (sel.state === "T" ? "Reanudar " : "Pausar ") + selName, keys: "P", run: () => procs.act("pause")},
            {group: "Acciones", icon: "swap_vert", text: "Cambiar la prioridad…", keys: "+ −", run: () => procs.act("priority")},
            {group: "Acciones", icon: "open_in_new", text: "Ir a la ventana de " + selName, keys: "W", run: () => procs.focusWindow()},
            {group: "Acciones", icon: "my_location", text: "Localizar en pantalla", keys: "L", run: () => procs.locate()},
            {group: "Acciones", icon: "content_copy", text: "Copiar PID", keys: "Y", run: () => procs.copyPid()}
        ] : [];
        const nav = [
            {group: "Ir a", icon: "list_alt", text: "Procesos", keys: "1", run: () => root.go("procs")},
            {group: "Ir a", icon: "monitoring", text: "Rendimiento", keys: "2", run: () => root.go("perf")},
            {group: "Ir a", icon: "apps", text: "Apps", keys: "3", run: () => root.go("apps")},
            {group: "Ir a", icon: "settings_suggest", text: "Servicios", keys: "4", run: () => root.go("services")},
            {group: "Vista", icon: "account_tree", text: "Ver como árbol", keys: "V", run: () => procs.setMode("tree")},
            {group: "Vista", icon: "view_agenda", text: "Ver por app", keys: "V", run: () => procs.setMode("apps")},
            {group: "Vista", icon: "person", text: procs.mine ? "Mostrar todos los usuarios" : "Solo mis procesos", keys: "U", run: () => procs.setMine(!procs.mine)}
        ];
        const found = [];
        if (q.length > 0) {
            const model = procs.rows;
            for (let i = 0; i < model.count && found.length < 6; i++) {
                const r = model.get(i);
                if ((r.title + " " + r.name + " " + r.pid).toLowerCase().indexOf(q) >= 0)
                    found.push({group: "Procesos", icon: r.group ? "view_agenda" : "memory", text: r.title + (r.group ? "" : " · " + r.pid), keys: "", run: () => { root.go("procs"); procs.select(r.key); }});
            }
        }
        return actions.concat(found, nav).filter(e => !q || e.group === "Procesos" || e.text.toLowerCase().indexOf(q) >= 0);
    }

    signal go(string id)
    signal closed

    function open() {
        input.text = "";
        current = 0;
        opened = true;
        input.forceActiveFocus();
    }
    function close() {
        opened = false;
        closed();
    }
    function run(index) {
        const entry = entries[index];
        close();
        if (entry)
            entry.run();
    }

    visible: scrim.opacity > 0
    z: 50

    Rectangle {
        id: scrim

        anchors.fill: parent
        color: Theme.m3scrim
        opacity: root.opened ? Metrics.scrimOpacity : 0

        Behavior on opacity {
            Anim {
                kind: "defaultEffects"
            }
        }

        TapHandler {
            onTapped: root.close()
        }
    }

    Rectangle {
        id: panel

        width: Math.min(Metrics.dialogMaxWidth * 1.15, root.width - (Theme.padding.large ?? 0) * 2)
        height: Math.min(root.height * 0.7, header.height + list.contentHeight + (Theme.padding.medium ?? 0) * 2)
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.height * 0.12 + (root.opened ? 0 : -(Theme.spacing.large ?? 0))
        radius: Theme.rounding.extraLarge ?? 0
        color: Theme.m3surfaceContainerHigh
        opacity: root.opened ? 1 : 0
        scale: root.opened ? 1 : 0.97

        Behavior on y {
            Anim {
                kind: "defaultSpatial"
            }
        }
        Behavior on opacity {
            Anim {
                kind: "fastEffects"
            }
        }
        Behavior on scale {
            Anim {
                kind: "defaultSpatial"
            }
        }

        Item {
            id: header

            width: parent.width
            height: Metrics.searchBarHeight + (Theme.spacing.small ?? 0)

            Icon {
                id: glass

                x: Theme.padding.large ?? 0
                anchors.verticalCenter: parent.verticalCenter
                name: "search"
                color: Theme.m3onSurfaceVariant
            }

            TextInput {
                id: input

                anchors.left: glass.right
                anchors.leftMargin: Theme.spacing.medium ?? 0
                anchors.right: parent.right
                anchors.rightMargin: Theme.padding.large ?? 0
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.m3onSurface
                font.family: Theme.typeFont("body.large").family
                font.pointSize: Theme.typeFont("body.large").pointSize > 0 ? Theme.typeFont("body.large").pointSize : Qt.application.font.pointSize
                selectByMouse: true
                onTextChanged: root.current = 0

                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Escape) {
                        root.close();
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Tab) {
                        root.current = Math.min(root.entries.length - 1, root.current + 1);
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Backtab) {
                        root.current = Math.max(0, root.current - 1);
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        root.run(root.current);
                        event.accepted = true;
                    }
                }

                Label {
                    visible: input.text === ""
                    text: "Escribe una acción o un proceso…"
                    role: "body.large"
                    color: Theme.m3onSurfaceVariant
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: Metrics.outlineWidth
                color: Theme.m3outlineVariant
            }
        }

        ListView {
            id: list

            anchors.top: header.bottom
            anchors.bottom: parent.bottom
            anchors.margins: Theme.padding.small ?? 0
            width: parent.width
            clip: true
            model: root.entries
            currentIndex: root.current
            section.property: "group"
            section.delegate: Label {
                required property string section

                x: Theme.padding.large ?? 0
                height: Metrics.chipHeight
                verticalAlignment: Text.AlignBottom
                text: section.toUpperCase()
                role: "label.small"
                color: Theme.m3onSurfaceVariant
            }
            delegate: Rectangle {
                id: entry

                required property var modelData
                required property int index

                x: Theme.spacing.small ?? 0
                width: list.width - x * 2
                height: Metrics.listItemOneLine * 0.85
                radius: Theme.rounding.large ?? 0
                color: index === root.current ? Theme.m3secondaryContainer : Qt.alpha(Theme.m3secondaryContainer, 0)

                Behavior on color {
                    ColorAnimation {
                        duration: Motion.ms("fastEffects")
                    }
                }

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.medium ?? 0
                    width: parent.width - x * 2
                    spacing: Theme.spacing.medium ?? 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: entry.modelData.icon
                        color: entry.index === root.current ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    }

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - x - keys.width - parent.spacing
                        text: entry.modelData.text
                        role: "body.large"
                        elide: Text.ElideRight
                        color: entry.index === root.current ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                    }

                    Label {
                        id: keys

                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.modelData.keys
                        role: "label.medium"
                        font.family: Theme.font.family?.mono ?? ""
                        color: Theme.m3onSurfaceVariant
                    }
                }

                HoverHandler {
                    onHoveredChanged: if (hovered) root.current = entry.index
                }

                TapHandler {
                    onTapped: root.run(entry.index)
                }
            }
        }
    }
}
