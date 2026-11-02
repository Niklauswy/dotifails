"""Private project folders: where one recording's worker keeps its files while it records and finalises."""
from datetime import datetime
from pathlib import Path
import uuid


class Library:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def new_directory(self):
        path = self.root / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        path.mkdir(mode=0o700)
        return path
