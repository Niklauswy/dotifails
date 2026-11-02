"""Native interface, imported lazily so CLI recovery needs no Qt display."""
def main():
    from .window import run
    return run()
