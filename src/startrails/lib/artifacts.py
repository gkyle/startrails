"""Stage related output files and roll back failed or cancelled publication."""
from concurrent.futures import CancelledError
from pathlib import Path
import os
import tempfile


class ArtifactTransaction:
    def __init__(self, cancel_check=None):
        self.cancel_check = cancel_check
        self.staged = {}

    def check_cancelled(self):
        if self.cancel_check and self.cancel_check():
            raise CancelledError()

    def stage(self, destination) -> Path:
        self.check_cancelled()
        destination = Path(destination).resolve()
        if destination not in self.staged:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(prefix=".denoise-", suffix=destination.suffix,
                                               dir=destination.parent)
            os.close(descriptor)
            self.staged[destination] = Path(name)
        return self.staged[destination]

    def commit(self):
        backups = {}
        published = []
        try:
            for destination, staged in self.staged.items():
                self.check_cancelled()
                if not staged.is_file() or staged.stat().st_size == 0:
                    raise OSError(f"Output was not written: {destination}")
                if destination.exists():
                    descriptor, name = tempfile.mkstemp(prefix=".denoise-backup-", dir=destination.parent)
                    os.close(descriptor)
                    backup = Path(name)
                    try:
                        os.replace(destination, backup)
                    except BaseException:
                        backup.unlink(missing_ok=True)
                        raise
                    backups[destination] = backup
                os.replace(staged, destination)
                published.append(destination)
            self.check_cancelled()
        except BaseException:
            for destination in reversed(published):
                destination.unlink(missing_ok=True)
            for destination, backup in backups.items():
                os.replace(backup, destination)
            raise
        else:
            for backup in backups.values():
                backup.unlink(missing_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for staged in self.staged.values():
            staged.unlink(missing_ok=True)
