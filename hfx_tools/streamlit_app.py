"""Streamlit app for building HFX files from metadata and data folders."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

from hfx_tools.build import build_hfx_from_folder
from hfx_tools.io import read_hfx_json
from hfx_tools.validators import ValidationFramework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    st.set_page_config(page_title="HFX Builder", layout="wide")
    st.title("🧬 HFX Builder")
    st.markdown(
        "Build HFX (Haplotype Frequency Exchange) bundles from metadata and data folders."
    )

    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        output_name = st.text_input(
            "Output filename",
            value="output",
            help="Name for the output .hfx file (without extension)"
        )
        normalize_paths = st.checkbox(
            "Normalize data paths",
            value=True,
            help="Rewrite file:// paths to file://data/<basename> inside archive"
        )
        write_manifest = st.checkbox(
            "Write MANIFEST.json",
            value=True,
            help="Include manifest file in archive"
        )
        hash_alg = st.selectbox(
            "Hash algorithm",
            options=["sha256", "md5", None],
            help="Include checksums in manifest"
        )

    # Main area - folder input
    st.header("Input Folder Structure")
    st.info(
        """
        Expected folder structure:
        ```
        input_folder/
        ├── metadata/
        │   └── metadata.json
        └── data/
            └── frequencies.csv (optional if inline)
        ```
        """
    )

    # Create a temporary directory for demo purposes
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Option 1: Use Local Folder")
        folder_path = st.text_input(
            "Path to input folder",
            placeholder="/path/to/input_folder"
        )

    with col2:
        st.subheader("Option 2: Upload Files")
        st.info(
            "✨ **Auto-update mode**: Upload your files and the tool will automatically "
            "update `metadata.frequencyLocation` to point to the data file within the HFX bundle."
        )
        uploaded_metadata = st.file_uploader(
            "Upload metadata.json",
            type=["json"],
            key="metadata_upload"
        )
        
        uploaded_data = st.file_uploader(
            "Upload frequency data (CSV or Parquet)",
            type=["csv", "tsv", "parquet"],
            key="data_upload",
            help="Optional: The tool will auto-update metadata.frequencyLocation to point to this file"
        )

    # Process based on selected method
    if folder_path:
        folder_path = Path(folder_path).expanduser()

        if not folder_path.exists():
            st.error(f"❌ Folder not found: {folder_path}")
            return

        metadata_folder = folder_path / "metadata"
        data_folder = folder_path / "data"

        if not metadata_folder.exists():
            st.error(f"❌ metadata/ folder not found: {metadata_folder}")
            return

        # Preview metadata files
        metadata_files = list(metadata_folder.glob("*.json"))
        if not metadata_files:
            st.error(f"❌ No JSON files found in metadata/: {metadata_folder}")
            return

        st.success(f"✅ Found {len(metadata_files)} metadata file(s)")

        # Display metadata preview
        with st.expander("📋 Metadata Preview"):
            for mf in metadata_files:
                st.subheader(f"File: {mf.name}")
                try:
                    metadata = read_hfx_json(mf)
                    st.json(metadata)
                except Exception as e:
                    st.error(f"Error reading {mf.name}: {str(e)}")

        # Validate before building
        if st.button("🔍 Validate", key="validate_btn"):
            st.info("Running validation...")
            try:
                validator = ValidationFramework()
                validation_results = validator.validate(
                    metadata_files[0],
                    read_hfx_json(metadata_files[0]),
                    data_folder if data_folder.exists() else Path()
                )

                # Display results
                st.subheader("Validation Results")
                for result in validation_results:
                    if result.level == "error":
                        st.error(f"**{result.validator_name}**: {result.message}")
                    elif result.level == "warning":
                        st.warning(f"**{result.validator_name}**: {result.message}")
                    else:
                        st.info(f"**{result.validator_name}**: {result.message}")

                has_errors = validator.has_errors(validation_results)
                if not has_errors:
                    st.success("✅ All validations passed!")
                else:
                    st.error("❌ Validation failed - fix errors before building")

            except Exception as e:
                st.error(f"Validation error: {str(e)}")

        # Build button
        if st.button("🚀 Build HFX", key="build_btn"):
            st.info("Building HFX...")
            try:
                with st.spinner("Processing..."):
                    result = build_hfx_from_folder(
                        input_folder=folder_path,
                        output_name=output_name,
                        output_dir=folder_path,
                        normalize_data_path=normalize_paths,
                        write_manifest=write_manifest,
                        hash_alg=hash_alg,
                    )

                if result["success"]:
                    st.success(f"✅ HFX created successfully: {result['output_path']}")

                    # Display download button
                    output_file = Path(result["output_path"])
                    if output_file.exists():
                        with open(output_file, "rb") as f:
                            st.download_button(
                                label="⬇️ Download HFX",
                                data=f.read(),
                                file_name=output_file.name,
                                mime="application/zip"
                            )

                    # Show validation summary
                    st.subheader("Build Summary")
                    passed = sum(1 for r in result["validation_results"] if r.passed)
                    total = len(result["validation_results"])
                    st.metric("Validation Results", f"{passed}/{total} passed")

                    # Show log file
                    if Path(result["log_file"]).exists():
                        with open(result["log_file"], "r") as f:
                            log_content = f.read()
                        with st.expander("📝 Build Log"):
                            st.text(log_content)

                else:
                    st.error("❌ Build failed!")
                    for result in result["validation_results"]:
                        if result.level == "error" and not result.passed:
                            st.error(f"  - {result.message}")

                    if "error" in result:
                        st.error(f"Error: {result['error']}")

            except Exception as e:
                st.error(f"Build error: {str(e)}")
                logger.exception("Build failed with exception")

    elif uploaded_metadata:
        st.info("📂 Using uploaded files...")

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            metadata_folder = tmpdir / "metadata"
            data_folder = tmpdir / "data"
            metadata_folder.mkdir()
            data_folder.mkdir()

            # Save uploaded metadata
            metadata_path = metadata_folder / "metadata.json"
            metadata_path.write_bytes(uploaded_metadata.getbuffer())

            # Save uploaded data if provided
            if uploaded_data:
                data_path = data_folder / uploaded_data.name
                data_path.write_bytes(uploaded_data.getbuffer())

            # Show preview
            st.subheader("Metadata Preview")
            try:
                metadata = read_hfx_json(metadata_path)
                
                # Show what will be updated
                if uploaded_data:
                    st.info(
                        f"📝 **Will be updated**: `metadata.frequencyLocation` → "
                        f"`file://data/{uploaded_data.name}`"
                    )
                
                st.json(metadata)
            except Exception as e:
                st.error(f"Error reading metadata: {str(e)}")
                return

            # Build button
            if st.button("🚀 Build HFX", key="build_btn_upload"):
                st.info("Building HFX...")
                try:
                    with st.spinner("Processing..."):
                        result = build_hfx_from_folder(
                            input_folder=tmpdir,
                            output_name=output_name,
                            output_dir=tmpdir,
                            normalize_data_path=normalize_paths,
                            write_manifest=write_manifest,
                            hash_alg=hash_alg,
                        )

                    if result["success"]:
                        st.success("✅ HFX created successfully!")

                        # Provide download
                        output_file = Path(result["output_path"])
                        if output_file.exists():
                            with open(output_file, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download HFX",
                                    data=f.read(),
                                    file_name=output_file.name,
                                    mime="application/zip"
                                )
                    else:
                        st.error("❌ Build failed!")

                except Exception as e:
                    st.error(f"Build error: {str(e)}")

    else:
        st.info("👈 Enter a folder path or upload files to get started")


if __name__ == "__main__":
    main()
