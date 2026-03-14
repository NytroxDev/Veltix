from enum import IntEnum


class BufferSize(IntEnum):
    SMALL = 1024  # 1KB  — peu de données, faible mémoire
    MEDIUM = 8192  # 8KB  — usage général (défaut)
    LARGE = 65536  # 64KB — gros messages fréquents
    HUGE = 1048576  # 1MB  — transferts de fichiers
