# intake/output_writer.py
# Output writing utilities for ingestion results
# Separates file I/O concerns from processing logic

import json
import logging
from pathlib import Path
from typing import Dict, Any

from .utils import ensure_directory, safe_filename
from .serialization import to_jsonable


class OutputWriter:
    """
    Handles writing ingestion results to the filesystem.

    Separates output concerns from the main ingestion logic,
    making the system more testable and following SRP.
    """

    def __init__(self):
        """Initialize the output writer."""
        self.logger = logging.getLogger(__name__)

    def write_intake(
        self,
        intake_data: Dict[str, Any],
        output_dir: Path,
        filename: str
    ) -> Path:
        """
        Write combined intake data to a JSON file.

        Args:
            intake_data: Dictionary containing all intake data (metadata + content)
            output_dir: Directory to write the file to
            filename: Name of the file (will be sanitized)

        Returns:
            Path to the written file
        """
        ensure_directory(output_dir)
        safe_name = safe_filename(filename)
        file_path = output_dir / safe_name

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(to_jsonable(intake_data), f, indent=2, ensure_ascii=False)

        self.logger.debug(f"Wrote intake data to {file_path}")
        return file_path

    def write_dataset_summary(
        self,
        summary: Dict[str, Any],
        output_path: Path,
        dataset_name: str
    ) -> Path:
        """
        Write a dataset summary file.

        Args:
            summary: Dictionary containing the dataset summary
            output_path: Base path for the output
            dataset_name: Name of the dataset

        Returns:
            Path to the written summary file
        """
        summary_filename = safe_filename(f"{dataset_name}_summary.json")
        summary_file_path = output_path / summary_filename

        with open(summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(to_jsonable(summary), f, indent=2, ensure_ascii=False)

        self.logger.info(f"Created summary: {summary_file_path}")
        return summary_file_path

    def write_ingestion_summary(
        self,
        summary: Dict[str, Any],
        output_path: Path,
        ingestion_id: str
    ) -> Path:
        """
        Write the overall ingestion summary file.

        Args:
            summary: Dictionary containing the overall summary
            output_path: Base path for the output
            ingestion_id: Unique identifier for the ingestion run

        Returns:
            Path to the written summary file
        """
        summary_path = output_path / ingestion_id / "ingestion_summary.json"
        ensure_directory(summary_path.parent)

        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(to_jsonable(summary), f, indent=2, ensure_ascii=False)

        self.logger.info(f"Overall summary saved to: {summary_path}")
        return summary_path