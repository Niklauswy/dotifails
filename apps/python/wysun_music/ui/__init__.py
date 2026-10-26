"""Qt surfaces of Wysun Music. Colours, radii, spacing, type and motion come
from the active Wysun theme tokens; widgets read them while painting, so a
style or variant change applies live without rebuilding anything."""
from wysun_core import icons  # noqa: F401  (registers the Lucide fallback for Material symbols the font lacks)
