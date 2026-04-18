from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse

from .util import safe_relpath


def read_hfx_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_hfx_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
        f.write("\n")


def parse_frequency_location(freq_loc: str) -> Tuple[str, Optional[str]]:
    """
    Returns (kind, value)
      - ("inline", None)
      - ("file", relative_path) for file://...
      - ("http", uri) for http(s)://... (not bundled in MVP)
    """
    if freq_loc == "inline":
        return ("inline", None)

    u = urlparse(freq_loc)
    if u.scheme in ("http", "https"):
        return ("http", freq_loc)
    if u.scheme == "file":
        # file://data/f.csv -> path = "data/f.csv"
        # urlparse gives netloc + path; handle both
        raw = (u.netloc + u.path).lstrip("/")
        return ("file", safe_relpath(raw))

    # allow plain relative path as a convenience (not strictly per schema format=uri)
    return ("file", safe_relpath(freq_loc))


def load_frequency_rows(hfx_path: Path, hfx_obj: Dict[str, Any]) -> List[Tuple[str, float]]:
    md = hfx_obj.get("metadata", {})
    freq_loc = md.get("frequencyLocation")
    if not freq_loc:
        raise ValueError("metadata.frequencyLocation is required")

    kind, val = parse_frequency_location(freq_loc)

    if kind == "inline":
        rows = hfx_obj.get("frequencyData")
        if rows is None:
            raise ValueError("frequencyLocation is 'inline' but top-level frequencyData is missing")
        out = []
        for r in rows:
            out.append((r["haplotype"], float(r["frequency"])))
        return out

    if kind == "http":
        raise ValueError("http(s) frequencyLocation not supported in MVP loader; please download locally or bundle with file://")

    # file
    rel = val
    assert rel is not None
    freq_file = (hfx_path.parent / rel).resolve()
    if not freq_file.exists():
        raise FileNotFoundError(f"Referenced frequency file not found: {freq_file}")

    if freq_file.suffix.lower() == ".csv":
        return load_csv(freq_file)
    if freq_file.suffix.lower() == ".parquet":
        return load_parquet(freq_file)

    raise ValueError(f"Unsupported frequency file type: {freq_file.suffix}")


def load_csv(path: Path) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if "haplotype" not in reader.fieldnames or "frequency" not in reader.fieldnames:
            raise ValueError(f"CSV must have columns haplotype,frequency; found {reader.fieldnames}")
        for row in reader:
            out.append((row["haplotype"], float(row["frequency"])))
    return out


def load_parquet(path: Path) -> List[Tuple[str, float]]:
    try:
        import pandas as pd  # type: ignore
    except Exception as e:
        raise ImportError("Parquet support requires pandas + pyarrow. Install with: pip install -e '.[parquet]'") from e

    df = pd.read_parquet(path)
    if "haplotype" not in df.columns or "frequency" not in df.columns:
        raise ValueError(f"Parquet must have columns haplotype,frequency; found {list(df.columns)}")
    return [(str(h), float(f)) for h, f in zip(df["haplotype"], df["frequency"])]

