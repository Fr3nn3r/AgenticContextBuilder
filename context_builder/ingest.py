# intake/ingest.py
# Core ingestion orchestration and dataset processing logic
# Coordinates file processing through the plugin pipeline

from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

from dotenv import load_dotenv

from .processors import ProcessingPipeline, registry
from .utils import generate_ingestion_id, ensure_directory, get_relative_path_safe, safe_filename
from .serialization import to_jsonable
from .output_writer import OutputWriter

if TYPE_CHECKING:
    from .models import (
        FileIngestorConfig, ProcessorConfig, ProcessingInfo, ProcessorInfo,
        DatasetSummary, DatasetInfo, ProcessedFileInfo, IngestionSummary,
        OverallSummary, FileProcessingResult, FileMetadata
    )




def _validate_ai_processor_requirements(config: Dict[str, Any]) -> None:
    """
    Validate that AI processor requirements are met.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If AI processor is configured but requirements not met
    """
    # Load environment variables
    load_dotenv()

    # Check if ContentProcessor is in the pipeline
    processors = config.get('processors', [])
    has_ai_processor = any(
        proc.get('name') == 'ContentProcessor'
        for proc in processors
    )

    if has_ai_processor:
        # Check for OpenAI API key
        api_key = (
            os.getenv('OPENAI_API_KEY') or
            os.getenv('OPENAI_KEY')
        )

        if not api_key:
            raise ValueError(
                "ContentProcessor is configured but no OpenAI API key found. "
                "Please set OPENAI_API_KEY in your environment or .env file. "
                "For AI processing use config/default_config.json, or for metadata-only "
                "processing use config/metadata_only_config.json"
            )


class FileIngestor:
    """
    Main class for orchestrating file ingestion operations.

    Manages the processing of individual files and entire datasets through
    a configurable pipeline of processors.
    """

    def __init__(self, config: Optional[Union[Dict[str, Any], FileIngestorConfig]] = None):
        """
        Initialize the file ingestor.

        Args:
            config: Configuration dictionary or FileIngestorConfig for the ingestor and processors
        """
        from .models import FileIngestorConfig

        # Convert to typed config
        if isinstance(config, dict):
            try:
                self.typed_config = FileIngestorConfig(**config)
            except Exception:
                # Fallback to default config if validation fails
                self.typed_config = FileIngestorConfig()
        elif isinstance(config, FileIngestorConfig):
            self.typed_config = config
        else:
            self.typed_config = FileIngestorConfig()

        # Keep dict version for backward compatibility
        self.config = self.typed_config.model_dump()

        # Set up logger
        self.logger = logging.getLogger(__name__)

        # Set up output writer
        self.output_writer = OutputWriter()

        # Validate AI processor requirements if configured
        _validate_ai_processor_requirements(self.config)

        self.pipeline = ProcessingPipeline(registry)
        self._setup_pipeline()

    def _setup_pipeline(self) -> None:
        """
        Set up the processing pipeline based on configuration.

        By default, adds the MetadataProcessor. Additional processors
        can be configured in the config under 'processors'.
        """
        # Use typed config for processors
        for proc_config in self.typed_config.processors:
            processor_name = proc_config.name
            processor_config = proc_config.config
            self.pipeline.add_processor(processor_name, processor_config)

    def ingest_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single file through the ingestion pipeline.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary containing all processed metadata

        Raises:
            ProcessingError: If file processing fails
        """
        result = self.pipeline.process_file(file_path)
        # Convert any Pydantic models to dictionaries for backward compatibility
        return to_jsonable(result)

    def ingest_dataset_folder(
        self,
        dataset_path: Path,
        output_base_path: Path,
        ingestion_id: str,
        subfolders_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process a single dataset folder and create individual metadata files.

        Args:
            dataset_path: Path to the dataset folder
            output_base_path: Base path for output files
            ingestion_id: Unique identifier for this ingestion run
            subfolders_filter: Optional list of subfolders to process

        Returns:
            Dictionary containing processing summary and file list
        """
        dataset_name = dataset_path.name
        dataset_folder_name = f"dataset-{dataset_name}"
        output_dataset_path = output_base_path / ingestion_id / dataset_folder_name

        # Create output directory structure
        ensure_directory(output_dataset_path)

        processed_files = []

        # Process all files in the dataset folder (recursively)
        for item in dataset_path.rglob('*'):
            if item.is_file():
                relative_path = get_relative_path_safe(item, dataset_path)

                # If subfolders filter is specified, check if file is in allowed subfolder
                if subfolders_filter:
                    # Get the top-level folder name for this file
                    top_level_folder = relative_path.parts[0] if relative_path.parts else None
                    if top_level_folder not in subfolders_filter:
                        continue  # Skip files not in specified subfolders

                self.logger.info(f"  Processing file: {relative_path}")

                try:
                    # Process file through pipeline
                    file_metadata = self.ingest_file(item)

                    # Add processing information
                    processing_info = {
                        'ingestion_time': datetime.now().isoformat(),
                        'ingestion_id': ingestion_id,
                        'source_dataset': dataset_name,
                        'dataset_folder_name': dataset_folder_name,
                        'output_path': str(output_dataset_path),
                    }

                    # Separate file_content from other metadata
                    file_content = file_metadata.pop('file_content', None)

                    # Create combined intake file with all data
                    complete_intake = {
                        'processing_info': processing_info,
                    }

                    # Add all metadata (file_metadata, enrichment_info, etc.)
                    for key, value in file_metadata.items():
                        if key != 'processing_info':  # Avoid duplicate processing_info
                            complete_intake[key] = value

                    # Add file_content if it exists (from ContentProcessor)
                    if file_content:
                        complete_intake['file_content'] = file_content

                    # Prepare output directory and filename
                    relative_path_parent = relative_path.parent
                    intake_output_dir = output_dataset_path / relative_path_parent

                    intake_filename = f"{item.stem}_intake.json"
                    intake_file_path = self.output_writer.write_intake(
                        complete_intake,
                        intake_output_dir,
                        intake_filename
                    )

                    file_info = {
                        'original_file': str(item),
                        'relative_path': str(relative_path),
                        'intake_file': str(intake_file_path),
                        'file_name': item.name,
                        'intake_filename': safe_filename(intake_filename)
                    }

                    processed_files.append(file_info)

                except Exception as e:
                    self.logger.error(f"  Failed to process {relative_path}: {e}")
                    # Add failed file to processed list with error info
                    processed_files.append({
                        'original_file': str(item),
                        'relative_path': str(relative_path),
                        'file_name': item.name,
                        'error': str(e),
                        'is_processing_failed': True
                    })

        # Create a summary file for the dataset
        dataset_summary = {
            'dataset_info': {
                'ingestion_id': ingestion_id,
                'dataset_name': dataset_name,
                'dataset_folder_name': dataset_folder_name,
                'source_path': str(dataset_path),
                'output_path': str(output_dataset_path),
                'processing_time': datetime.now().isoformat(),
                'total_files_processed': len([f for f in processed_files if 'error' not in f]),
                'total_files_failed': len([f for f in processed_files if 'error' in f]),
            },
            'processed_files': processed_files
        }

        self.output_writer.write_dataset_summary(
            dataset_summary,
            output_dataset_path,
            dataset_name
        )
        return dataset_summary

    def ingest_multiple_datasets(
        self,
        input_path: Path,
        output_path: Path,
        num_datasets: Optional[int] = None,
        specific_datasets: Optional[List[str]] = None,
        subfolders_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process multiple datasets from an input directory.

        Args:
            input_path: Path to directory containing dataset folders
            output_path: Path for output files
            num_datasets: Maximum number of datasets to process (if not using specific_datasets)
            specific_datasets: List of specific dataset names to process
            subfolders_filter: Optional list of subfolders to process within each dataset

        Returns:
            Dictionary containing overall processing summary
        """
        # Generate unique ingestion ID
        ingestion_id = generate_ingestion_id(input_path)
        self.logger.info(f"Ingestion ID: {ingestion_id}")

        # Create output directory
        ensure_directory(output_path)

        # Get list of dataset folders (directories only)
        dataset_folders = [d for d in input_path.iterdir() if d.is_dir()]
        dataset_folders.sort()  # Sort for consistent ordering

        if not dataset_folders:
            raise ValueError(f"No dataset folders found in {input_path}")

        # Filter datasets if specific ones are requested
        if specific_datasets:
            requested_datasets = set(specific_datasets)
            available_datasets = {d.name for d in dataset_folders}

            # Check if all requested datasets exist
            missing_datasets = requested_datasets - available_datasets
            if missing_datasets:
                self.logger.warning(f"Requested datasets not found: {', '.join(missing_datasets)}")

            # Filter to only requested datasets that exist
            dataset_folders = [d for d in dataset_folders if d.name in requested_datasets]

            if not dataset_folders:
                raise ValueError("No valid datasets found from the requested list")

            datasets_to_process = dataset_folders
        else:
            # Process first N datasets if no specific datasets requested
            datasets_to_process = dataset_folders[:num_datasets] if num_datasets else dataset_folders

        self.logger.info(f"Processing {len(datasets_to_process)} datasets from {input_path}")
        self.logger.info(f"Output will be saved to: {output_path}")

        total_files_processed = 0
        total_files_failed = 0
        dataset_summaries = []

        for i, dataset_folder in enumerate(datasets_to_process, 1):
            self.logger.info(f"[{i}/{len(datasets_to_process)}] Processing dataset: {dataset_folder.name}")

            try:
                dataset_summary = self.ingest_dataset_folder(
                    dataset_folder, output_path, ingestion_id, subfolders_filter
                )
                files_processed = dataset_summary['dataset_info']['total_files_processed']
                files_failed = dataset_summary['dataset_info']['total_files_failed']

                total_files_processed += files_processed
                total_files_failed += files_failed
                dataset_summaries.append(dataset_summary)

                self.logger.info(f"  Processed {files_processed} files ({files_failed} failed)")
            except Exception as e:
                self.logger.error(f"  Error processing dataset {dataset_folder.name}: {e}")
                total_files_failed += 1

        # Create overall summary
        overall_summary = {
            'ingestion_summary': {
                'ingestion_id': ingestion_id,
                'input_folder': str(input_path),
                'output_folder': str(output_path),
                'processing_time': datetime.now().isoformat(),
                'datasets_requested': num_datasets if not specific_datasets else None,
                'specific_datasets_requested': specific_datasets if specific_datasets else None,
                'specific_subfolders_requested': subfolders_filter if subfolders_filter else None,
                'datasets_processed': len(datasets_to_process),
                'total_files_processed': total_files_processed,
                'total_files_failed': total_files_failed,
                'processed_datasets': [d.name for d in datasets_to_process],
            },
            'dataset_summaries': dataset_summaries
        }

        overall_summary_path = self.output_writer.write_ingestion_summary(
            overall_summary,
            output_path,
            ingestion_id
        )

        self.logger.info(f"Ingestion complete!")
        self.logger.info(f"Total files processed: {total_files_processed}")
        self.logger.info(f"Total files failed: {total_files_failed}")

        return overall_summary