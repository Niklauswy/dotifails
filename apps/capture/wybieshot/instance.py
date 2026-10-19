"""One active selection/edit session per user/display; clipboard owners are free."""
import fcntl
import hashlib
import os
from pathlib import Path
import stat


class CaptureLease:
    def __init__(self,directory=None):
        self.directory=Path(directory) if directory else Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/f'wybie-screenshot-{os.getuid()}'
        self.fd=None

    def claim(self):
        if self.fd is not None:return True
        root=self.directory
        if root.is_symlink():raise RuntimeError('Unsafe screenshot runtime directory')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=root.stat()
        if info.st_uid!=os.getuid() or info.st_mode&0o077:raise RuntimeError('Screenshot runtime directory must be private')
        display=hashlib.sha256((os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY','default')).encode()).hexdigest()[:16]
        fd=os.open(root/f'capture-{display}.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            info=os.fstat(fd)
            if info.st_uid!=os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode&0o077:raise RuntimeError('Unsafe screenshot session lock')
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:os.close(fd);return False
        except Exception:
            os.close(fd);raise
        self.fd=fd;return True

    def release(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
