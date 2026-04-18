from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .io import read_hfx_json, write_hfx_json, load_frequency_rows, parse_frequency_location
from .util import md5_hex, flatten_index_row


def _shannon_entropy(freqs: List[float]) -> float:
    # natural log entropy
    h = 0.0
    for p in freqs:
        if p > 0:
            h -= p * math.log(p)
    return h


def _topk_cumsum(freqs_sorted_desc: List[float], k: int) -> float:
    return float(sum(freqs_sorted_desc[:k])) if k > 0 else 0.0


def compute_qc(rows: List[Tuple[str, float]], topk: List[int]) -> Dict[str, Any]:
    warnings: List[str] = []

    haplotypes = [h for h, _ in rows]
    freqs = [f for _, f in rows]

    n = len(freqs)
    n_nan = sum(1 for f in freqs if isinstance(f, float) and math.isnan(f))
    n_nonpos = sum(1 for f in freqs if (not (isinstance(f, float) and math.isnan(f))) and f <= 0)

    # duplicates
    seen = set()
    dup = 0
    for h in haplotypes:
        if h in seen:
            dup += 1
        else:
            seen.add(h)

    # filter usable freqs for math
    usable = [f for f in freqs if isinstance(f, (int, float)) and not math.isnan(f) and f > 0]
    if len(usable) != n:
        warnings.append(f"{n - len(usable)} rows have NaN or non-positive frequency")

    s = float(sum(usable))
    if abs(s - 1.0) > 1e-6:
        warnings.append(f"Sum of positive frequencies is {s:.10f} (deviation {abs(s-1.0):.3g})")

    freqs_sorted = sorted(usable, reverse=True)
    h = _shannon_entropy(usable)
    eff = float(math.exp(h)) if h >= 0 else None

    qc: Dict[str, Any] = {
        "nHaplotypes": n,
        "nUsable": len(usable),
        "nNaN": n_nan,
        "nNonPositive": n_nonpos,
        "nDuplicateHaplotypes": dup,
        "sumFrequency": s,
        "sumAbsDeviationFrom1": abs(s - 1.0),
        "minFrequency": float(min(usable)) if usable else None,
        "maxFrequency": float(max(usable)) if usable else None,
        "entropyShannon": float(h),
        "effectiveNumber": eff,
        "warnings": warnings,
    }

    for k in topk:
        qc[f"top{k}Cumulative"] = _topk_cumsum(freqs_sorted, k)

    return qc


def qc_hfx(metadata_json: Path, write_metadata: bool, index_row: bool, topk: List[int]) -> None:
    hfx = read_hfx_json(metadata_json)
    rows = load_frequency_rows(metadata_json, hfx)
    qc = compute_qc(rows, topk=topk)

    # If the frequencies are referenced via file://..., compute MD5 and write to metadata.checkSum (schema says MD5) :contentReference[oaicite:4]{index=4}
    md = hfx.get("metadata", {})
    freq_loc = md.get("frequencyLocation")
    kind, rel = parse_frequency_location(freq_loc)

    if kind == "file" and rel is not None:
        freq_file = (metadata_json.parent / rel).resolve()
        md["checkSum"] = md5_hex(freq_file)

    if write_metadata:
        # Add QC under metadata.qc (schema currently disallows extra props under metadata,
        # but this is your internal convention for phycus; phycus index can consume it even
        # if submissions keep QC elsewhere.)
        md["qc"] = qc
        hfx["metadata"] = md
        write_hfx_json(metadata_json, hfx)

    if index_row:
        row = flatten_index_row(hfx, qc)
        print(json.dumps(row, indent=2))
    else:
        print(json.dumps(qc, indent=2))

