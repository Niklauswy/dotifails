import Wysun.Config
import qs.services

// A round quick-settings tile that stays tinted while on.
IconButton {
    inactiveColour: Colours.layer(Colours.palette.m3surfaceContainerHighest, 2)
    fillWidth: true
    isToggle: true
    isRound: true
    shapeMorph: true
}
