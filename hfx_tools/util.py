from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Dict, Any


def file_hash(path: Path, alg: str) -> str:
    h = hashlib.new(alg)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_hex(path: Path) -> str:
    return file_hash(path, "md5")


def safe_relpath(path_str: str) -> str:
    # prevent absolute paths or traversal
    p = Path(path_str)
    if p.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {path_str}")
    if ".." in p.parts:
        raise ValueError(f"Path traversal is not allowed: {path_str}")
    return p.as_posix()


def flatten_index_row(hfx: Dict[str, Any], qc: Dict[str, Any]) -> Dict[str, Any]:
    md = hfx.get("metadata", {})
    cohort = md.get("cohortDescription", {}) or {}
    pops = cohort.get("population", []) or []
    pop_names = [p.get("name") for p in pops if isinstance(p, dict) and p.get("name")]

    # outputResolution is an array of {locus, resolution}
    out_res = md.get("outputResolution", []) or []
    loci = [x.get("locus") for x in out_res if isinstance(x, dict) and x.get("locus")]
    resolutions = [x.get("resolution") for x in out_res if isinstance(x, dict) and x.get("resolution")]

    nomen = md.get("nomenclatureUsed", {}) or {}
    hfe = md.get("hfeMethod", {}) or {}

    return {
        # minimal phycus index fields (extend as you like)
        "creationDateTime": md.get("creationDateTime"),
        "species": cohort.get("species"),
        "cohortSize": cohort.get("cohortSize"),
        "populationNames": pop_names,
        "ISO3166": [p.get("geoLocation", {}).get("ISO3166") for p in pops if isinstance(p, dict)],
        "dataSource": cohort.get("dataSource"),
        "loci": loci,
        "resolutions": resolutions,
        "nomenclatureDatabase": nomen.get("database"),
        "nomenclatureVersion": nomen.get("version"),
        "hfeMethod": hfe.get("method"),
        "frequencyLocation": md.get("frequencyLocation"),
        "checkSum": md.get("checkSum"),
        # QC fields
        **{f"qc_{k}": v for k, v in qc.items() if k != "warnings"},
        "qc_warnings": qc.get("warnings", []),
    }

