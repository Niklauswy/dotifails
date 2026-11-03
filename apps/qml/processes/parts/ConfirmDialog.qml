// Confirmation before terminating, forcing or changing the priority of a process or a whole app. Priority uses
// a slider from −20 (más tiempo de CPU) to 19 (menos); raising it may need administrator rights.
import QtQuick
import WysunM3

Dialog {
    id: root

    property string action
    property string label
    property int count: 1
    property int nice: 0

    signal closedForFocus

    function ask(action, label, count, nice) {
        root.action = action;
        root.label = label;
        root.count = count;
        root.nice = nice;
        open();
    }

    icon: action === "priority" ? "swap_vert" : action === "kill" ? "bolt" : "cancel"
    title: action === "priority" ? "Prioridad de " + label : action === "kill" ? "¿Forzar el cierre de " + label + "?" : "¿Terminar " + label + "?"
    message: action === "priority" ? "Los valores bajos dan más tiempo de CPU. Subirla por encima de normal puede pedir permisos de administrador."
           : (action === "kill" ? "Se detiene al instante, sin poder guardar." : "Se le pide que se cierre de forma ordenada; normalmente guarda su estado.")
             + (count > 1 ? " Afecta a " + count + " procesos." : "")
    actions: [{id: "cancel", text: "Cancelar"}, {id: "ok", text: action === "priority" ? "Aplicar" : action === "kill" ? "Forzar cierre" : "Terminar", primary: true}]
    onAccepted: id => {
        if (id === "ok")
            procs.confirm(action, nice);
        Qt.callLater(closedForFocus);
    }
    onRejected: Qt.callLater(closedForFocus)

    Column {
        visible: root.action === "priority"
        width: Metrics.dialogMinWidth
        spacing: Theme.spacing.small ?? 0

        Row {
            spacing: Theme.spacing.medium ?? 0

            Slider {
                id: slider

                width: Metrics.dialogMinWidth - value.width - parent.spacing
                from: -20
                to: 19
                stepSize: 1
                value: root.nice
                onValueChanged: root.nice = Math.round(value)
            }

            Label {
                id: value

                anchors.verticalCenter: parent.verticalCenter
                width: Metrics.iconButtonSize
                text: (root.nice > 0 ? "+" : "") + root.nice
                role: "headline.small"
                horizontalAlignment: Text.AlignRight
            }
        }

        Item {
            width: slider.width
            height: low.implicitHeight

            Label {
                id: low

                text: "Alta (−20)"
                role: "label.small"
                color: Theme.m3onSurfaceVariant
            }

            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Normal (0)"
                role: "label.small"
                color: Theme.m3onSurfaceVariant
            }

            Label {
                anchors.right: parent.right
                text: "Baja (19)"
                role: "label.small"
                color: Theme.m3onSurfaceVariant
            }
        }
    }
}
