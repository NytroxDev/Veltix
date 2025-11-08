# unit_utils.py
"""
Petit module utilitaire pour manipuler les unités de taille :
- parse_size("2 MB") -> 2097152
- parse_size("10Mb") -> 1250000
- format_size(1048576) -> "1.00 MB"
- Mo(10) -> 10485760
"""

import re

# Table des unités : nom -> multiplicateur (en octets)
_UNIT_MAP = {
    # Octets (SI)
    "b": 1 / 8,  # bits → octets
    "B": 1,
    "KB": 10**3,
    "MB": 10**6,
    "GB": 10**9,
    "TB": 10**12,
    # Octets (binaire)
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
    # Bits (SI)
    "kb": 10**3 / 8,
    "mb": 10**6 / 8,
    "gb": 10**9 / 8,
    "tb": 10**12 / 8,
    # Bits (binaire)
    "Kib": 1024 / 8,
    "Mib": 1024**2 / 8,
    "Gib": 1024**3 / 8,
    "Tib": 1024**4 / 8,
    # Français
    "Ko": 1024,
    "Mo": 1024**2,
    "Go": 1024**3,
    "To": 1024**4,
}

_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*([A-Za-z]+)?\s*$")


def parse_size(value: str) -> int:
    """Convertit une chaîne ('10MB', '2.5Mo', '100kb') en octets."""
    match = _SIZE_RE.match(value)
    if not match:
        raise ValueError(f"Valeur de taille invalide : {value!r}")
    number, unit = match.groups()
    number = float(number)
    unit = (unit or "B").strip()
    if unit not in _UNIT_MAP:
        raise ValueError(f"Unité inconnue : {unit}")
    return int(number * _UNIT_MAP[unit])


def format_size(num_bytes: int, precision: int = 2) -> str:
    """Formate une taille en octets en chaîne lisible (base 1024)."""
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024:
            return f"{size:.{precision}f} {unit}"
        size /= 1024
    return f"{size:.{precision}f} PiB"


def format_bits(num_bits: int, precision: int = 2) -> str:
    """Formate une taille en bits (vitesse)."""
    units = ["b", "Kb", "Mb", "Gb", "Tb", "Pb"]
    size = float(num_bits)
    for unit in units:
        if size < 1000:
            return f"{size:.{precision}f} {unit}"
        size /= 1000
    return f"{size:.{precision}f} Pb"


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convertit une valeur d'une unité vers une autre (bits/octet inclus)."""
    from_unit = from_unit.strip()
    to_unit = to_unit.strip()
    if from_unit not in _UNIT_MAP:
        raise ValueError(f"Unité source inconnue : {from_unit}")
    if to_unit not in _UNIT_MAP:
        raise ValueError(f"Unité cible inconnue : {to_unit}")
    value_bytes = value * _UNIT_MAP[from_unit]
    return value_bytes / _UNIT_MAP[to_unit]


# === Fonctions abrégées pour plus de lisibilité ===
def B(x): return int(x)
def KB(x): return int(x * 10**3)
def MB(x): return int(x * 10**6)
def GB(x): return int(x * 10**9)
def TB(x): return int(x * 10**12)

def KiB(x): return int(x * 1024)
def MiB(x): return int(x * 1024**2)
def GiB(x): return int(x * 1024**3)
def TiB(x): return int(x * 1024**4)

def Ko(x): return int(x * 1024)
def Mo(x): return int(x * 1024**2)
def Go(x): return int(x * 1024**3)
def To(x): return int(x * 1024**4)

def Kb(x): return int(x * 10**3 / 8)
def Mb(x): return int(x * 10**6 / 8)
def Gb(x): return int(x * 10**9 / 8)
def Tb(x): return int(x * 10**12 / 8)
