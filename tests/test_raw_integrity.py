"""Garante que os dados históricos de data/raw/ não foram editados (regra do case)."""

import hashlib
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_raw_files_match_original_checksums():
    manifest = (RAW / "set2026.sha256").read_text().splitlines()
    for line in manifest:
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256((RAW / "set2026" / name).read_bytes()).hexdigest()
        assert actual == expected, f"{name} foi alterado"
