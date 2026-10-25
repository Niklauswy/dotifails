"""Moving and resizing a frameless top-level window through the compositor."""
from PySide6.QtCore import Qt

RESIZE_MARGIN = 6


def resize_edges(widget, point):
    """The window edges within RESIZE_MARGIN of ``point``."""
    edges = Qt.Edges()
    if point.x() <= RESIZE_MARGIN:
        edges |= Qt.LeftEdge
    if point.x() >= widget.width() - RESIZE_MARGIN:
        edges |= Qt.RightEdge
    if point.y() <= RESIZE_MARGIN:
        edges |= Qt.TopEdge
    if point.y() >= widget.height() - RESIZE_MARGIN:
        edges |= Qt.BottomEdge
    return edges


class FramelessResize:
    """Mixin for a frameless QWidget: edges resize, the top strip moves (``drag_height``; None = everywhere)."""

    drag_height = 72

    def frame_gestures_enabled(self):
        return True

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.windowHandle() is None or not self.frame_gestures_enabled():
            return
        edges = resize_edges(self, event.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
        elif self.drag_height is None or event.position().y() < self.drag_height:
            self.windowHandle().startSystemMove()

    def mouseMoveEvent(self, event):
        edges = resize_edges(self, event.position().toPoint())
        horizontal = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
        vertical = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
        if horizontal and vertical:
            diagonal = edges in (Qt.Edges(Qt.LeftEdge | Qt.TopEdge), Qt.Edges(Qt.RightEdge | Qt.BottomEdge))
            self.setCursor(Qt.SizeFDiagCursor if diagonal else Qt.SizeBDiagCursor)
        elif horizontal or vertical:
            self.setCursor(Qt.SizeHorCursor if horizontal else Qt.SizeVerCursor)
        else:
            self.unsetCursor()
