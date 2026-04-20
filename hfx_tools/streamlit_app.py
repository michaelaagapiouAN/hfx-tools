"""Streamlit app for building HFX files from metadata and data folders."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

from hfx_tools.build import build_hfx_from_folder
from hfx_tools.io import read_hfx_json
from hfx_tools.validators import ValidationFramework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    st.set_page_config(page_title="HFX Builder", layout="wide")
    st.title("🧬 HFX Builder")
    st.markdown(
        "Build HFX (Haplotype Frequency Exchange) bundles from metadata and data files."
    )

    with st.sidebar:
        st.header("Configuration")
        output_name = st.text_input(
            "Output filename",
            value="output",
            help="Name for the output .hfx file (without extension)"
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

    st.header("Input Folder")
    st.info(
        """
        Expected folder structure:
        ```
        input_folder/
        ├── metadata.json
        └── frequencies.csv  (optional if inline or remote)
        ```
        """
    )

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
            "update `metadata.frequencyLocation` to point to the data file."
        )
        uploaded_metadata = st.file_uploader(
            "Upload metadata.json",
            type=["json"],
            key="metadata_upload"
        )
        uploaded_data = st.file_uploader(
            "Upload frequency data (CSV or Parquet)",
            type=["csv", "parquet"],
            key="data_upload",
            help="Optional: auto-updates metadata.frequencyLocation"
        )

    if folder_path:
        input_folder = Path(folder_path).expanduser()

        if not input_folder.exists():
            st.error(f"❌ Folder not found: {input_folder}")
            return

        metadata_files = [f for f in input_folder.glob("*.json") if f.name != "MANIFEST.json"]
        if not metadata_files:
            st.error(f"❌ No JSON metadata file found in: {input_folder}")
            return

        st.success(f"✅ Found metadata: {metadata_files[0].name}")

        with st.expander("📋 Metadata Preview"):
            try:
                st.json(read_hfx_json(metadata_files[0]))
            except Exception as e:
                st.error(f"Error reading metadata: {str(e)}")

        if st.button("🔍 Validate", key="validate_btn"):
            try:
                validator = ValidationFramework()
                results = validator.validate(
                    metadata_files[0],
                    read_hfx_json(metadata_files[0]),
                    input_folder
                )
                st.subheader("Validation Results")
                for r in results:
                    if r.level == "error":
                        st.error(f"**{r.validator_name}**: {r.message}")
                    elif r.level == "warning":
                        st.warning(f"**{r.validator_name}**: {r.message}")
                    else:
                        st.info(f"**{r.validator_name}**: {r.message}")
                if not validator.has_errors(results):
                    st.success("✅ All validations passed!")
                else:
                    st.error("❌ Validation failed - fix errors before building")
            except Exception as e:
                st.error(f"Validation error: {str(e)}")

        if st.button("🚀 Build HFX", key="build_btn"):
            try:
                with st.spinner("Processing..."):
                    result = build_hfx_from_folder(
                        input_folder=input_folder,
                        output_name=output_name,
                        output_dir=input_folder,
                        write_manifest=write_manifest,
                        hash_alg=hash_alg,
                    )

                if result["success"]:
                    st.success(f"✅ HFX created: {result['output_path']}")
                    output_file = Path(result["output_path"])
                    if output_file.exists():
                        with open(output_file, "rb") as f:
                            st.download_button(
                                label="⬇️ Download HFX",
                                data=f.read(),
                                file_name=output_file.name,
                                mime="application/zip"
                            )
                    passed = sum(1 for r in result["validation_results"] if r.passed)
                    total = len(result["validation_results"])
                    st.metric("Validation Results", f"{passed}/{total} passed")
                    if Path(result["log_file"]).exists():
                        with open(result["log_file"], "r") as f:
                            with st.expander("📝 Build Log"):
                                st.text(f.read())
                else:
                    st.error("❌ Build failed!")
                    for r in result["validation_results"]:
                        if r.level == "error" and not r.passed:
                            st.error(f"  - {r.message}")
                    if "error" in result:
                        st.error(f"Error: {result['error']}")
            except Exception as e:
                st.error(f"Build error: {str(e)}")
                logger.exception("Build failed with exception")

    elif uploaded_metadata:
        st.info("📂 Using uploaded files...")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            metadata_path = tmpdir / "metadata.json"
            metadata_path.write_bytes(uploaded_metadata.getbuffer())

            if uploaded_data:
                (tmpdir / uploaded_data.name).write_bytes(uploaded_data.getbuffer())

            st.subheader("Metadata Preview")
            try:
                metadata = read_hfx_json(metadata_path)
                if uploaded_data:
                    st.info(
                        f"📝 **Will be updated**: `metadata.frequencyLocation` → "
                        f"`file://{uploaded_data.name}`"
                    )
                st.json(metadata)
            except Exception as e:
                st.error(f"Error reading metadata: {str(e)}")
                return

            if st.button("🚀 Build HFX", key="build_btn_upload"):
                try:
                    with st.spinner("Processing..."):
                        result = build_hfx_from_folder(
                            input_folder=tmpdir,
                            output_name=output_name,
                            output_dir=tmpdir,
                            write_manifest=write_manifest,
                            hash_alg=hash_alg,
                        )
                    if result["success"]:
                        st.success("✅ HFX created successfully!")
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
