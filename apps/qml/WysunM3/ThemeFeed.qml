// Put one as the first child of the app's root item: it hands the host's scheme, tokens and reduced-motion flag
// to Theme. (Bindings on a singleton are the only way to feed it without the library knowing the host.)
import QtQuick

Item {
    id: root

    property var scheme
    property var tokens
    property bool reducedMotion: false

    visible: false
    width: 0
    height: 0

    Binding {
        target: Theme
        property: "scheme"
        value: root.scheme
        when: root.scheme !== undefined && root.scheme !== null
    }

    Binding {
        target: Theme
        property: "tokens"
        value: root.tokens
        when: root.tokens !== undefined && root.tokens !== null
    }

    Binding {
        target: Theme
        property: "reducedMotion"
        value: root.reducedMotion
    }
}
