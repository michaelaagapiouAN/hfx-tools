from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from .io import read_hfx_json, write_hfx_json, parse_frequency_location
from .util import safe_relpath, file_hash, md5_hex


def pack_hfx(
    metadata_json: Path,
    out_path: Path,
    normalize_data_path: bool = False,
    write_manifest: bool = False,
    hash_alg: Optional[str] = None,
) -> None:
    hfx = read_hfx_json(metadata_json)
    md = hfx.get("metadata", {})
    if "frequencyLocation" not in md:
        raise ValueError("metadata.frequencyLocation is required")

    freq_loc = md["frequencyLocation"]
    kind, rel = parse_frequency_location(freq_loc)

    files_to_add: List[tuple[Path, str]] = []

    # Always include metadata.json (submission JSON)
    # We write it into the archive as "metadata.json"
    # (even if the input file was called something else)
    # NOTE: If normalize_data_path, we may update metadata.frequencyLocation
    metadata_arcname = "metadata.json"

    freq_file_path: Optional[Path] = None
    freq_arcname: Optional[str] = None

    if kind == "inline":
        # nothing else needed
        pass
    elif kind == "file" and rel is not None:
        freq_file_path = (metadata_json.parent / rel).resolve()
        if not freq_file_path.exists():
            raise FileNotFoundError(f"Referenced frequency file not found: {freq_file_path}")

        # Put it inside archive under data/<basename>
        freq_arcname = f"data/{freq_file_path.name}"

        if normalize_data_path:
            # Rewrite metadata pointer to file://data/<basename> (allowed as uri; example given in schema) :contentReference[oaicite:6]{index=6}
            md["frequencyLocation"] = f"file://{freq_arcname}"
            hfx["metadata"] = md
        else:
            # Keep metadata as-is; but still store file under its referenced relpath if it's already like data/...
            # If rel differs from data/<basename>, also add under that referenced path for consistency.
            ref_arc = safe_relpath(rel)
            if ref_arc != freq_arcname:
                # store at referenced arcname to satisfy pointer
                freq_arcname = ref_arc

        files_to_add.append((freq_file_path, freq_arcname))
        # Update MD5 checksum in metadata.checkSum (schema says MD5) :contentReference[oaicite:7]{index=7}
        md["checkSum"] = md5_hex(freq_file_path)
        hfx["metadata"] = md
    else:
        raise ValueError("http(s) frequencyLocation not supported for bundling in MVP")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build MANIFEST entries as we add files
    manifest_files = []

    def _manifest_add(arcname: str, data_bytes: int, digest: Optional[str]):
        rec = {"path": arcname, "bytes": int(data_bytes)}
        if digest is not None and hash_alg is not None:
            rec[hash_alg] = digest
        manifest_files.append(rec)

    with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        # Write metadata.json from in-memory JSON to ensure normalized formatting & updated checksum/pointer
        meta_bytes = json.dumps(hfx, indent=2).encode("utf-8") + b"\n"
        z.writestr(metadata_arcname, meta_bytes)
        _manifest_add(metadata_arcname, len(meta_bytes), None)

        for src_path, arcname in files_to_add:
            z.write(src_path, arcname)
            digest = file_hash(src_path, hash_alg) if hash_alg else None
            _manifest_add(arcname, src_path.stat().st_size, digest)

        if write_manifest:
            man = {
                "format": "hfx-bundle-manifest-v1",
                "files": manifest_files,
            }
            man_bytes = json.dumps(man, indent=2).encode("utf-8") + b"\n"
            z.writestr("MANIFEST.json", man_bytes)

        # Optional classic checksum listing
        if hash_alg:
            lines = []
            for rec in manifest_files:
                if hash_alg in rec:
                    lines.append(f"{rec[hash_alg]}  {rec['path']}")
            z.writestr(f"{hash_alg.upper()}SUMS", ("\n".join(lines) + "\n").encode("utf-8"))

