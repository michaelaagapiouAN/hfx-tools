## hfx-tools


# hfx-tools

Tools for working with HFX submissions (Haplotype Frequency Exchange).

This repo provides composable command line tools and a Streamlit app for building, packing, 
inspecting, and validating HFX documents. Key features include:

- **`build`** - Build HFX bundles from a folder structure with automatic validation
- **`pack`** - Pack HFX archives from metadata.json with optional manifests and checksums
- **`qc`** - Compute quality control statistics
- **`inspect`** - Inspect metadata or bundled HFX files
- **Validation framework** - Extensible validation with built-in validators
- **Streamlit UI** - Web-based interface for building HFX files

## Key schema facts

- `metadata.frequencyLocation` controls where frequencies are stored: either `"inline"`
  or a URI (e.g., `file://data/frequencies.csv`) (see HFX schema).
  
- If inline, the JSON may include `frequencyData` (array of `{haplotype, frequency}`).

## Install

### Basic installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### With optional dependencies
```bash
# For Parquet support
pip install -e ".[parquet]"

# For Streamlit web UI
pip install -e ".[streamlit]"

# For development
pip install -e ".[dev,lint]"
```

## Usage

### Frequency Location Types

The HFX standard supports four types of frequency data locations:

1. **Inline** - `"frequencyLocation": "inline"` with `frequencyData` array in same JSON
2. **Remote** - `"frequencyLocation": "https://zenodo.org/.../data.csv"` or S3 URL
3. **File (relative)** - `"frequencyLocation": "file://data/frequencies.csv"` pointing to file within HFX bundle
4. **File (parquet)** - Same as above but with `.parquet` extension

### CLI: Build from folder

The most common workflow for hackathons and batch processing:

```bash
hfx-build /path/to/input_folder -n output_name
```

This will:
1. Read metadata from `input_folder/metadata/`
2. **Auto-detect** frequency data files in `input_folder/data/`
3. **Auto-update** `metadata.frequencyLocation` to `file://data/<filename>` (unless already set to remote or inline)
4. **Validate** all data with built-in validators
5. **Pack** into a single `output_name.hfx` file (self-contained bundle with all data)
6. **Log** all validation results to `output_name.build.log`

Expected folder structure:
```
input_folder/
├── metadata/
│   └── metadata.json      # Required: HFX metadata + inline data (optional)
└── data/
    └── frequencies.csv    # Optional: if frequencyLocation = "file://frequencies.csv"
```

Example:
```bash
mkdir -p example/{metadata,data}
cp metadata.json example/metadata/
cp frequencies.csv example/data/
hfx-build example -n my_submission
# Output: example/my_submission.hfx
```

Options:
- `-n, --name NAME` - Output filename (required, without .hfx)
- `-o, --out DIR` - Output directory (defaults to input folder)
- `--no-manifest` - Skip MANIFEST.json in archive
- `--hash {md5,sha256,none}` - Hash algorithm (default: sha256)
- `--no-auto-update-location` - Don't auto-update `metadata.frequencyLocation` (advanced)

### CLI: Pack (low-level)

For direct packing when you already have a metadata.json:

```bash
hfx-pack metadata.json -o dist/example.hfx --manifest --hash sha256
```

### CLI: Inspect

```bash
hfx-inspect metadata.json       # Inspect a metadata.json file
hfx-inspect example.hfx         # Inspect a bundled .hfx archive
```

### CLI: QC

```bash
hfx-qc metadata.json --write-metadata --topk 10 100 1000
```

### Streamlit: Web UI

Launch the interactive web interface:

```bash
streamlit run hfx_tools/streamlit_app.py
```

The Streamlit app provides:
- **Folder browser** - Select local folders with metadata/ and data/ subdirectories
- **File upload** - Upload metadata.json and data files directly
- **Auto-update mode** - Automatically sets `metadata.frequencyLocation` to point to uploaded data
- **Metadata preview** - View JSON structure and what will be auto-updated before building
- **Validation preview** - Run validators and see results
- **HFX download** - Download the built .hfx file
- **Build logs** - View detailed validation and packing logs

## Validation Framework

The build process includes an extensible validation framework with built-in validators:

1. **Metadata required fields** - Ensures `metadata.frequencyLocation` is present
2. **Frequency location** - Validates frequency location format (inline, file://, http://)
3. **Frequency data format** - Checks inline frequency data structure, types, and duplicates
4. **File references** - Verifies that referenced data files exist

Validation results are logged and returned with error/warning levels. The build fails if any 
error-level validations fail.

### Custom validators (for hackathon extensibility)

Hackathon participants can register custom validators:

```python
from hfx_tools.validators import ValidationFramework, ValidationResult

def my_custom_validator(metadata_json, hfx_obj, data_folder):
    # Your validation logic here
    return ValidationResult(
        validator_name="my_validator",
        passed=True,
        message="My validation passed",
        level="info"  # or "warning", "error"
    )

validator_framework = ValidationFramework()
validator_framework.register_validator("my_validator", my_custom_validator)
```

## Package contents

```
.
├── __init__.py
├── build.py           # Build orchestration (NEW - hackathon MVP)
├── cli.py             # Command-line interface
├── inspect.py         # HFX inspection tools
├── io.py              # JSON and file I/O
├── pack.py            # Low-level packing
├── qc.py              # Quality control
├── streamlit_app.py   # Web UI (NEW - hackathon MVP)
├── util.py            # Utilities
├── validators.py      # Validation framework (NEW - hackathon MVP)
├── Makefile
└── pyproject.toml
```



