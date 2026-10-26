// Prints the cards of the Settings design-system picker (see tests/test_shell_design_system.py). The test runs it as
// the shell.qml of a throwaway shell dir that holds services/Colours.qml, a Wallpapers stub, utils/, components/
// and modules/nexus/common/DesignSystemPicker.qml.
import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.modules.nexus.common

ShellRoot {
    FloatingWindow {
        implicitWidth: 720
        implicitHeight: 480

        ColumnLayout {
            anchors.fill: parent

            DesignSystemPicker {
                id: picker
            }
        }

        Timer {
            interval: 1500
            running: true
            onTriggered: {
                const cards = picker.children.filter(c => c.system !== undefined).map(c => {
                    const layer = c.children.find(k => k.disabled !== undefined && k.pressX !== undefined);
                    return {
                        system: c.system,
                        name: c.name,
                        wip: c.wip,
                        selected: c.selected,
                        interactive: !!layer && layer.visible && layer.enabled
                    };
                });
                console.info("DESIGN " + JSON.stringify({ current: picker.current, columns: picker.columns, cards: cards }));
                Qt.quit();
            }
        }
    }
}
