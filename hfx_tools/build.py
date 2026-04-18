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
    normalize_data_path: bool = True,
    write_manifest: bool = True,
    hash_alg: str = "sha256",
    auto_update_frequency_location: bool = True,
) -> Dict[str, Any]:
    """Build an HFX bundle from a folder structure.
    
    Expected folder structure:
        input_folder/
        ├── metadata/
        │   └── metadata.json (or multiple metadata files)
        └── data/
            └── frequency_file.csv or .parquet (optional if inline)
    
    If a data file is found and auto_update_frequency_location is True,
    the metadata.frequencyLocation will be updated to point to the file
    location within the wheel (e.g., "file://data/myfile.csv").
    
    Args:
        input_folder: Root folder containing metadata/ and data/ subdirectories
        output_name: Name for output .hfx file (without extension)
        output_dir: Where to write the .hfx file (defaults to input_folder)
        normalize_data_path: Rewrite file:// paths inside archive
        write_manifest: Include MANIFEST.json in archive
        hash_alg: Hash algorithm for manifest ("md5", "sha256", or None)
        auto_update_frequency_location: Auto-update metadata to point to data files
    
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
    
    # Validate structure
    metadata_folder = input_folder / "metadata"
    data_folder = input_folder / "data"
    
    if not metadata_folder.exists():
        logger.error(f"metadata/ folder not found: {metadata_folder}")
        raise FileNotFoundError(f"metadata/ folder not found: {metadata_folder}")
    
    # Discover metadata files
    metadata_files = list(metadata_folder.glob("*.json"))
    if not metadata_files:
        logger.error(f"No JSON files found in metadata/: {metadata_folder}")
        raise FileNotFoundError(f"No JSON files found in metadata/: {metadata_folder}")
    
    logger.info(f"Found {len(metadata_files)} metadata file(s)")
    
    # For MVP: assume single metadata file
    if len(metadata_files) > 1:
        logger.warning(f"Found {len(metadata_files)} metadata files; using first one: {metadata_files[0]}")
    
    metadata_json = metadata_files[0]
    logger.info(f"Using metadata file: {metadata_json}")
    
    # Load and validate
    hfx_obj = read_hfx_json(metadata_json)
    
    # Auto-detect and update frequency location if data files exist
    if auto_update_frequency_location and data_folder.exists():
        data_files = [f for f in data_folder.glob("*") if f.is_file()]
        if data_files and len(data_files) == 1:
            data_file = data_files[0]
            freq_loc = hfx_obj.get("metadata", {}).get("frequencyLocation", "")
            
            # Only auto-update if:
            # 1. Not already set to remote (http/https)
            # 2. Not already set to inline
            # 3. Not already set to a file:// reference
            if not freq_loc or (freq_loc != "inline" and not freq_loc.startswith("http")):
                old_loc = freq_loc
                new_loc = f"file://data/{data_file.name}"
                logger.info(f"Auto-updating frequencyLocation from '{old_loc}' to '{new_loc}'")
                hfx_obj["metadata"]["frequencyLocation"] = new_loc
    
    # Run validation
    validator = ValidationFramework()
    validation_results = validator.validate(metadata_json, hfx_obj, data_folder)
    
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
            normalize_data_path=normalize_data_path,
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
