from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

from .io import read_hfx_json, write_hfx_json
from .pack import pack_hfx
from .validators import ValidationFramework, ValidationResult

logger = logging.getLogger(__name__)


def build_hfx_from_folder(
    input_folder: Path,
    output_name: str,
    output_dir: Optional[Path] = None,
    write_manifest: bool = True,
    hash_alg: str = "sha256",
    auto_update_frequency_location: bool = True,
) -> Dict[str, Any]:
    """Build an HFX bundle from a folder.

    Expected folder structure:
        input_folder/
        ├── metadata.json          # Required
        └── frequencies.csv        # Optional if frequencyLocation is inline or remote

    Args:
        input_folder: Folder containing metadata JSON and optional data files
        output_name: Name for output .hfx file (without extension)
        output_dir: Where to write the .hfx file (defaults to input_folder)
        write_manifest: Include MANIFEST.json in archive
        hash_alg: Hash algorithm for manifest ("md5", "sha256", or None)
        auto_update_frequency_location: Auto-update metadata to point to detected data file

    Returns:
        Dictionary with build results including validation results and output path
    """
    input_folder = Path(input_folder)
    if output_dir is None:
        output_dir = input_folder
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up logging
    log_file = output_dir / f"{output_name}.build.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info(f"Starting HFX build: {output_name}")
    logger.info(f"Input folder: {input_folder}")

    # Discover metadata file (single .json at top level, excluding known non-metadata names)
    metadata_files = [f for f in input_folder.glob("*.json")
                      if f.name not in ("MANIFEST.json",)]
    if not metadata_files:
        raise FileNotFoundError(f"No JSON metadata file found in: {input_folder}")
    if len(metadata_files) > 1:
        logger.warning(f"Found {len(metadata_files)} JSON files; using first: {metadata_files[0]}")

    metadata_json = metadata_files[0]
    logger.info(f"Using metadata file: {metadata_json}")

    # Discover data files (non-JSON files at top level)
    data_files = [f for f in input_folder.glob("*")
                  if f.is_file() and f.suffix.lower() in (".csv", ".parquet")]
    
    # Load and validate
    hfx_obj = read_hfx_json(metadata_json)

    # Ensure top-level version is set per schema
    if "version" not in hfx_obj:
        hfx_obj["version"] = "0.1.1"
        logger.info("Added missing top-level version: 0.1.1")

    # Ensure metadata wrapper exists
    if "metadata" not in hfx_obj:
        hfx_obj["metadata"] = {}
        logger.warning("Added missing metadata wrapper")
    
    # Auto-detect and update frequency location
    if auto_update_frequency_location and data_files:
        if len(data_files) == 1:
            data_file = data_files[0]
            freq_loc = hfx_obj.get("metadata", {}).get("frequencyLocation", "")
            if not freq_loc or (freq_loc != "inline" and not freq_loc.startswith("http")):
                new_loc = f"file://{data_file.name}"
                logger.info(f"Auto-updating frequencyLocation to '{new_loc}'")
                hfx_obj["metadata"]["frequencyLocation"] = new_loc
                write_hfx_json(metadata_json, hfx_obj)
        else:
            logger.warning(f"Found {len(data_files)} data files; skipping auto-update")

    # Run validation
    validator = ValidationFramework()
    validation_results = validator.validate(metadata_json, hfx_obj, input_folder)
    
    # Log validation results
    logger.info("--- Validation Results ---")
    validator.log_results(validation_results, logger)
    
    has_errors = validator.has_errors(validation_results)
    
    if has_errors:
        logger.error("Validation failed; aborting build")
        return {
            "success": False,
            "output_path": None,
            "validation_results": validation_results,
            "log_file": str(log_file),
        }
    
    # Pack HFX
    output_path = output_dir / f"{output_name}.hfx"
    logger.info(f"Packing HFX: {output_path}")
    
    try:
        pack_hfx(
            metadata_json=metadata_json,
            out_path=output_path,
            write_manifest=write_manifest,
            hash_alg=hash_alg,
        )
        logger.info(f"Successfully created: {output_path}")
    except Exception as e:
        logger.error(f"Failed to pack HFX: {str(e)}")
        return {
            "success": False,
            "output_path": None,
            "validation_results": validation_results,
            "error": str(e),
            "log_file": str(log_file),
        }
    
    logger.info("Build complete")
    
    return {
        "success": True,
        "output_path": str(output_path),
        "validation_results": validation_results,
        "log_file": str(log_file),
    }
