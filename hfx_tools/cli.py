#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pack import pack_hfx
from .qc import qc_hfx
from .inspect import inspect_any
from .build import build_hfx_from_folder


def main():
    parser = argparse.ArgumentParser(prog="hfx-tools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # hfx-pack
    p_pack = sub.add_parser("pack", help="Build a bundled .hfx archive (zip) from metadata.json")
    p_pack.add_argument("metadata_json", type=Path)
    p_pack.add_argument("-o", "--out", type=Path, required=True, help="Output .hfx path")
    p_pack.add_argument("--manifest", action="store_true", help="Write MANIFEST.json into the archive")
    p_pack.add_argument("--hash", choices=["md5", "sha256"], default=None, help="Include checksums in manifest/SHA* file")

    # hfx-qc
    p_qc = sub.add_parser("qc", help="Compute QC stats from an HFX submission JSON")
    p_qc.add_argument("metadata_json", type=Path)
    p_qc.add_argument("--write-metadata", action="store_true",
                      help="Write computed QC stats into top-level hfx.qc")
    p_qc.add_argument("--index-row", action="store_true",
                      help="Print a flattened JSON row intended for phycus catalog/index")
    p_qc.add_argument("--topk", type=int, nargs="*", default=[10, 100, 1000], help="Top-K cutoffs for cumulative frequency")

    # hfx-inspect
    p_ins = sub.add_parser("inspect", help="Inspect metadata.json or a bundled .hfx")
    p_ins.add_argument("path", type=Path)

    # hfx-build
    p_build = sub.add_parser("build", help="Build an HFX from a folder with metadata/ and data/ subdirs")
    p_build.add_argument("input_folder", type=Path, help="Folder containing metadata/ and data/ subdirectories")
    p_build.add_argument("-n", "--name", type=str, required=True, help="Output name (without .hfx extension)")
    p_build.add_argument("-o", "--out", type=Path, default=None, help="Output directory (defaults to input folder)")
    p_build.add_argument("--no-manifest", action="store_true", help="Skip writing MANIFEST.json")
    p_build.add_argument("--hash", choices=["md5", "sha256", "none"], default="sha256", help="Hash algorithm")
    p_build.add_argument("--no-auto-update-location", action="store_true",
                        help="Don't auto-update metadata.frequencyLocation for detected data files")

    args = parser.parse_args()

    if args.cmd == "pack":
        pack_hfx(
            metadata_json=args.metadata_json,
            out_path=args.out,
            write_manifest=args.manifest,
            hash_alg=args.hash,
        )
    elif args.cmd == "qc":
        qc_hfx(
            metadata_json=args.metadata_json,
            write_metadata=args.write_metadata,
            index_row=args.index_row,
            topk=args.topk,
        )
    elif args.cmd == "inspect":
        inspect_any(args.path)
    elif args.cmd == "build":
        # Set up logging for build
        logging.basicConfig(level=logging.INFO)
        hash_alg = None if args.hash == "none" else args.hash
        result = build_hfx_from_folder(
            input_folder=args.input_folder,
            output_name=args.name,
            output_dir=args.out,
            write_manifest=not args.no_manifest,
            hash_alg=hash_alg,
            auto_update_frequency_location=not args.no_auto_update_location,
        )
        if not result["success"]:
            raise SystemExit(f"Build failed: {result.get('error', 'validation errors')}")
    else:
        raise SystemExit(f"Unknown command: {args.cmd}")


# Convenience entrypoints:
# - `hfx-pack` calls `hfx-tools pack ...`
# - `hfx-qc` calls `hfx-tools qc ...`
# - `hfx-inspect` calls `hfx-tools inspect ...`
if __name__ == "__main__":
    main()

