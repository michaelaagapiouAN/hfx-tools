from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Dict

from .io import read_hfx_json


def _print_summary(hfx: Dict[str, Any], label: str) -> None:
    md = hfx.get("metadata", {})
    cohort = md.get("cohortDescription", {}) or {}
    pops = cohort.get("population", []) or []
    pop_names = [p.get("name") for p in pops if isinstance(p, dict) and p.get("name")]

    out_res = md.get("outputResolution", []) or []
    loci = [x.get("locus") for x in out_res if isinstance(x, dict) and x.get("locus")]

    print(f"== {label} ==")
    print(f"frequencyLocation: {md.get('frequencyLocation')}")
    print(f"checkSum (md5): {md.get('checkSum')}")
    print(f"species: {cohort.get('species')}")
    print(f"cohortSize: {cohort.get('cohortSize')}")
    print(f"populations: {pop_names}")
    print(f"loci: {loci}")
    print(f"nomenclature: {md.get('nomenclatureUsed')}")
    print(f"hfeMethod: {md.get('hfeMethod')}")


def inspect_any(path: Path) -> None:
    if path.suffix.lower() == ".hfx":
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            print(f"{path} contains {len(names)} files:")
            for n in names:
                print(f" - {n}")
            if "metadata.json" not in names:
                raise ValueError("No metadata.json found inside .hfx")
            hfx = json.loads(z.read("metadata.json").decode("utf-8"))
            _print_summary(hfx, "metadata.json (from archive)")
    else:
        hfx = read_hfx_json(path)
        _print_summary(hfx, str(path))

