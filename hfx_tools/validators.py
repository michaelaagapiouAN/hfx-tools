from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    validator_name: str
    passed: bool
    message: str
    level: str = "error"  # "error", "warning", "info"


class ValidationFramework:
    """Extensible validation framework for HFX documents."""
    
    def __init__(self):
        self._validators: Dict[str, Callable] = {}
        self._register_builtin_validators()
    
    def register_validator(self, name: str, validator_func: Callable) -> None:
        """Register a custom validator function.
        
        Validator should return a ValidationResult or list of ValidationResults.
        """
        self._validators[name] = validator_func
    
    def _register_builtin_validators(self) -> None:
        """Register built-in validators."""
        self.register_validator("schema_version", validate_schema_version)
        self.register_validator("metadata_required_fields", validate_metadata_required_fields)
        self.register_validator("frequency_location", validate_frequency_location)
        self.register_validator("frequency_data_format", validate_frequency_data_format)
        self.register_validator("file_references", validate_file_references)
    
    def validate(self, metadata_json: Path, hfx_obj: Dict[str, Any], 
                 data_folder: Path) -> List[ValidationResult]:
        """Run all validators on the HFX object.
        
        Args:
            metadata_json: Path to the metadata.json file
            hfx_obj: Parsed HFX object
            data_folder: Path to the data folder for file reference checks
        
        Returns:
            List of ValidationResults
        """
        results = []
        for name, validator_func in self._validators.items():
            try:
                result = validator_func(metadata_json, hfx_obj, data_folder)
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)
            except Exception as e:
                results.append(ValidationResult(
                    validator_name=name,
                    passed=False,
                    message=f"Validator crashed: {str(e)}",
                    level="error"
                ))
        return results
    
    def log_results(self, results: List[ValidationResult], logger_obj=None) -> None:
        """Log validation results."""
        if logger_obj is None:
            logger_obj = logger
        
        for result in results:
            if result.level == "error":
                logger_obj.error(f"[{result.validator_name}] {result.message}")
            elif result.level == "warning":
                logger_obj.warning(f"[{result.validator_name}] {result.message}")
            else:
                logger_obj.info(f"[{result.validator_name}] {result.message}")
    
    def has_errors(self, results: List[ValidationResult]) -> bool:
        """Check if any error-level validation failed."""
        return any(r.level == "error" and not r.passed for r in results)


# Built-in validators

HFX_SCHEMA_VERSION = "0.1.1"


def validate_schema_version(metadata_json: Path, hfx_obj: Dict[str, Any],
                            data_folder: Path) -> ValidationResult:
    """Check that top-level version matches the expected HFX schema version."""
    version = hfx_obj.get("version")
    if version is None:
        return ValidationResult(
            validator_name="schema_version",
            passed=False,
            message=f"Missing required top-level 'version' field (expected '{HFX_SCHEMA_VERSION}')",
            level="error"
        )
    if version != HFX_SCHEMA_VERSION:
        return ValidationResult(
            validator_name="schema_version",
            passed=False,
            message=f"Version mismatch: found '{version}', expected '{HFX_SCHEMA_VERSION}'",
            level="error"
        )
    return ValidationResult(
        validator_name="schema_version",
        passed=True,
        message=f"Schema version OK: {version}",
        level="info"
    )


def validate_metadata_required_fields(metadata_json: Path, hfx_obj: Dict[str, Any],
                                      data_folder: Path) -> List[ValidationResult]:
    """Check that required metadata fields are present per HFX schema."""
    results = []
    metadata = hfx_obj.get("metadata", {})

    required_fields = [
        "outputResolution",
        "hfeMethod",
        "cohortDescription",
        "nomenclatureUsed",
        "frequencyLocation",
    ]
    for field in required_fields:
        if field not in metadata:
            results.append(ValidationResult(
                validator_name="metadata_required_fields",
                passed=False,
                message=f"Missing required field: metadata.{field}",
                level="error"
            ))

    if not results:
        results.append(ValidationResult(
            validator_name="metadata_required_fields",
            passed=True,
            message="All required metadata fields present",
            level="info"
        ))

    return results


def validate_frequency_location(metadata_json: Path, hfx_obj: Dict[str, Any],
                                data_folder: Path) -> ValidationResult:
    """Check that frequencyLocation is valid."""
    metadata = hfx_obj.get("metadata", {})
    freq_loc = metadata.get("frequencyLocation", "")
    
    valid_locations = ["inline"]
    if freq_loc.startswith("file://"):
        valid_locations.append("file")
    elif freq_loc.startswith("http://") or freq_loc.startswith("https://"):
        valid_locations.append("http")
    
    if not freq_loc:
        return ValidationResult(
            validator_name="frequency_location",
            passed=False,
            message="frequencyLocation is empty",
            level="error"
        )
    
    if freq_loc not in ["inline"] and not (freq_loc.startswith("file://") or 
                                           freq_loc.startswith("http")):
        # Could be relative path
        if freq_loc.startswith("/"):
            return ValidationResult(
                validator_name="frequency_location",
                passed=False,
                message=f"frequencyLocation uses absolute path, use relative or file:// URI: {freq_loc}",
                level="warning"
            )
    
    return ValidationResult(
        validator_name="frequency_location",
        passed=True,
        message=f"frequencyLocation is valid: {freq_loc}",
        level="info"
    )


def validate_frequency_data_format(metadata_json: Path, hfx_obj: Dict[str, Any],
                                   data_folder: Path) -> List[ValidationResult]:
    """Check frequency data format for inline data."""
    results = []
    metadata = hfx_obj.get("metadata", {})
    freq_loc = metadata.get("frequencyLocation", "")
    
    # Only check if inline
    if freq_loc != "inline":
        return [ValidationResult(
            validator_name="frequency_data_format",
            passed=True,
            message="Not inline data; skipping format check",
            level="info"
        )]
    
    freq_data = hfx_obj.get("frequencyData", [])
    
    if not freq_data:
        results.append(ValidationResult(
            validator_name="frequency_data_format",
            passed=False,
            message="frequencyData is empty but frequencyLocation is 'inline'",
            level="warning"
        ))
        return results
    
    errors = []
    warnings = []
    
    seen_haplotypes = set()
    for i, row in enumerate(freq_data):
        if not isinstance(row, dict):
            errors.append(f"Row {i}: not a dict")
            continue
        
        if "haplotype" not in row:
            errors.append(f"Row {i}: missing 'haplotype'")
        elif "frequency" not in row:
            errors.append(f"Row {i}: missing 'frequency'")
        else:
            haplo = row["haplotype"]
            freq = row["frequency"]
            
            # Check for duplicates
            if haplo in seen_haplotypes:
                warnings.append(f"Row {i}: duplicate haplotype '{haplo}'")
            seen_haplotypes.add(haplo)
            
            # Check frequency value
            if not isinstance(freq, (int, float)):
                errors.append(f"Row {i}: frequency is not a number")
            elif math.isnan(freq):
                errors.append(f"Row {i}: frequency is NaN")
            elif freq < 0:
                errors.append(f"Row {i}: frequency is negative: {freq}")
    
    if errors:
        for err in errors:
            results.append(ValidationResult(
                validator_name="frequency_data_format",
                passed=False,
                message=err,
                level="error"
            ))
    
    if warnings:
        for warn in warnings:
            results.append(ValidationResult(
                validator_name="frequency_data_format",
                passed=True,
                message=warn,
                level="warning"
            ))
    
    if not errors and not warnings:
        results.append(ValidationResult(
            validator_name="frequency_data_format",
            passed=True,
            message=f"Frequency data valid: {len(freq_data)} records",
            level="info"
        ))
    
    return results


def validate_file_references(metadata_json: Path, hfx_obj: Dict[str, Any],
                             data_folder: Path) -> ValidationResult:
    """Check that referenced data files exist."""
    metadata = hfx_obj.get("metadata", {})
    freq_loc = metadata.get("frequencyLocation", "")
    
    # Only check file:// references
    if not freq_loc.startswith("file://"):
        return ValidationResult(
            validator_name="file_references",
            passed=True,
            message="Not a file reference; skipping check",
            level="info"
        )
    
    # Extract relative path from file://...
    rel_path = freq_loc[7:]  # Remove "file://"
    file_path = data_folder / rel_path

    if file_path.exists():
        return ValidationResult(
            validator_name="file_references",
            passed=True,
            message=f"File reference valid: {file_path}",
            level="info"
        )

    # Fall back: look for any matching data file in the folder
    if data_folder.exists():
        data_files = [f for f in data_folder.glob("*")
                      if f.is_file() and f.suffix.lower() in (".csv", ".parquet")]

        if len(data_files) == 1:
            return ValidationResult(
                validator_name="file_references",
                passed=True,
                message=f"File found (using {data_files[0].name} instead of {rel_path})",
                level="warning"
            )
        elif len(data_files) > 1:
            available = ", ".join(f.name for f in data_files)
            return ValidationResult(
                validator_name="file_references",
                passed=False,
                message=f"Multiple data files but none match '{rel_path}'. Available: {available}",
                level="error"
            )
    
    return ValidationResult(
        validator_name="file_references",
        passed=False,
        message=f"Referenced file does not exist: {file_path}. Expected filename: '{rel_path}'",
        level="error"
    )
