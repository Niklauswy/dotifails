"""Native interface, imported lazily so CLI recovery needs no Qt display."""
def main():
    from .app_window import main as run
    return run()
