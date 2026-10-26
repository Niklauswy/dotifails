// M3 fade through: the outgoing page fades out, then the incoming one fades in while it scales up from 92 %.
// For switching between destinations that are not related hierarchically (nav items, tabs).
import QtQuick
import WysunM3

TransitionHost {
    enterScale: Metrics.fadeThroughScale
}
