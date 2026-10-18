"""Native interface, imported lazily so CLI recovery needs no Qt display."""
def main():
    from .main import main as run
    return run()
