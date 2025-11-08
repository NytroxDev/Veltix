import os
import tempfile
import threading
from contextlib import contextmanager
from multiprocessing import Lock as ProcessLock

class AtomicFile:
    _global_lock = ProcessLock()

    def __init__(self, path: str, use_cache: bool = False):
        self.path = path
        self._thread_lock = threading.Lock()
        self.use_cache = use_cache
        self._cache = None

    @contextmanager
    def open_for_write(self, mode="w", encoding="utf-8"):
        """
        Contexte pour écrire de manière atomique.
        """
        dir_name = os.path.dirname(self.path) or "."
        base_name = os.path.basename(self.path)

        fd, temp_path = tempfile.mkstemp(prefix=base_name, dir=dir_name)
        try:
            with os.fdopen(fd, mode, encoding=encoding) as f:
                yield f
                f.flush()
                os.fsync(f.fileno())

            with self._thread_lock, AtomicFile._global_lock:
                os.replace(temp_path, self.path)

            if self.use_cache:
                self._cache = self.read(mode=mode, encoding=encoding)
        except Exception as e:
            os.remove(temp_path)
            raise e

    def read(self, mode="r", encoding="utf-8"):
        """
        Lit le fichier. Utilise le cache si activé.
        """
        if self.use_cache and self._cache is not None:
            return self._cache

        if not os.path.exists(self.path):
            return None

        with self._thread_lock, AtomicFile._global_lock:
            with open(self.path, mode, encoding=encoding) as f:
                data = f.read()

        if self.use_cache:
            self._cache = data
        return data

    def write(self, content, mode="w", encoding="utf-8"):
        """
        Écrit le contenu de manière atomique.
        """
        with self.open_for_write(mode=mode, encoding=encoding) as f:
            f.write(content)
