"""
Policy Processing Orchestrator - Coordinates PDF → Acquisition → Symbols → Logic pipeline.

Single Responsibility: Orchestrate the end-to-end processing of a single PDF file.
"""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from context_builder.ingestion import IngestionFactory, IngestionError
from context_builder.extraction.openai_symbol_extraction import OpenAISymbolExtraction
from context_builder.extraction.openai_logic_extraction import OpenAILogicExtraction
from context_builder.extraction.progress_callback import NoOpProgressCallback
from context_builder.utils.filename_utils import (
    generate_processing_folder_name,
    get_policy_stem,
)

logger = logging.getLogger(__name__)


class PolicyProcessingOrchestrator:
    """
    Orchestrates the complete processing pipeline for a single PDF file.

    Pipeline stages:
    1. Create processing folder
    2. Copy PDF to folder
    3. Run Azure DI acquisition
    4. Extract symbol table
    5. Extract logic
    6. Generate processing summary

    Follows the Single Responsibility Principle:
    - This class coordinates the pipeline
    - Each stage is delegated to specialized components
    """

    def __init__(self):
        """Initialize the processing orchestrator."""
        self.azure_di = None
        self.symbol_extractor = None
        self.logic_extractor = None

    def _initialize_extractors(self):
        """
        Lazy-initialize Azure DI and extraction components.

        Raises:
            Exception: If initialization fails
        """
        if self.azure_di is None:
            logger.info("Initializing Azure DI acquisition...")
            self.azure_di = IngestionFactory.create("azure-di")

        if self.symbol_extractor is None:
            logger.info("Initializing symbol extractor...")
            self.symbol_extractor = OpenAISymbolExtraction()

        if self.logic_extractor is None:
            logger.info("Initializing logic extractor...")
            self.logic_extractor = OpenAILogicExtraction()

    def _create_processing_folder(
        self,
        pdf_path: Path,
        base_output_dir: Path,
        timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Create timestamped processing folder for this PDF.

        Args:
            pdf_path: Path to PDF file
            base_output_dir: Base output directory
            timestamp: Optional timestamp (default: now)

        Returns:
            Path to created processing folder
        """
        folder_name = generate_processing_folder_name(pdf_path, timestamp=timestamp)
        processing_folder = base_output_dir / folder_name

        processing_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created processing folder: {processing_folder}")

        return processing_folder

    def _copy_pdf(self, pdf_path: Path, processing_folder: Path) -> Path:
        """
        Copy PDF to processing folder.

        Args:
            pdf_path: Path to source PDF
            processing_folder: Destination folder

        Returns:
            Path to copied PDF

        Raises:
            IOError: If copy fails
        """
        dest_path = processing_folder / pdf_path.name

        try:
            shutil.copy2(pdf_path, dest_path)
            logger.info(f"Copied PDF to: {dest_path}")
            return dest_path
        except Exception as e:
            raise IOError(f"Failed to copy PDF: {e}")

    def _run_acquisition(
        self,
        pdf_path: Path,
        processing_folder: Path,
        policy_stem: str
    ) -> Dict[str, Any]:
        """
        Run Azure DI acquisition on PDF.

        Args:
            pdf_path: Path to PDF file
            processing_folder: Processing folder for outputs
            policy_stem: Policy name stem

        Returns:
            Acquisition result dictionary

        Raises:
            IngestionError: If ingestion fails
        """
        logger.info(f"[1/4] Running Azure DI acquisition on {pdf_path.name}...")

        # Configure Azure DI to output to processing folder
        self.azure_di.output_dir = processing_folder
        self.azure_di.save_markdown = True

        # Process the PDF
        result = self.azure_di.process(pdf_path)

        logger.info(
            f"Acquisition complete: {result.get('total_pages', 0)} pages, "
            f"{result.get('table_count', 0)} tables"
        )

        return result

    def _run_symbol_extraction(
        self,
        acquired_md_path: Path,
        processing_folder: Path,
        policy_stem: str
    ) -> Dict[str, Any]:
        """
        Extract symbol table from acquired markdown.

        Args:
            acquired_md_path: Path to acquired markdown file
            processing_folder: Processing folder for outputs
            policy_stem: Policy name stem

        Returns:
            Symbol extraction result dictionary

        Raises:
            Exception: If extraction fails
        """
        logger.info(f"[2/4] Extracting symbol table...")

        symbol_table_path = processing_folder / f"{policy_stem}_symbol_table.json"

        result = self.symbol_extractor.process(
            markdown_path=str(acquired_md_path),
            output_path=str(symbol_table_path)
        )

        logger.info(
            f"Symbol extraction complete: {result.get('total_symbols', 0)} symbols"
        )

        return result

    def _run_logic_extraction(
        self,
        acquired_md_path: Path,
        symbol_table_path: str,
        processing_folder: Path,
        policy_stem: str,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Extract policy logic from acquired markdown.

        Args:
            acquired_md_path: Path to acquired markdown file
            symbol_table_path: Path to symbol table JSON
            processing_folder: Processing folder for outputs
            policy_stem: Policy name stem
            progress_callback: Optional progress callback for chunk updates

        Returns:
            Logic extraction result dictionary

        Raises:
            Exception: If extraction fails
        """
        logger.info(f"[3/4] Extracting policy logic...")

        # Use NoOpProgressCallback if none provided
        if progress_callback is None:
            progress_callback = NoOpProgressCallback()

        output_base_path = processing_folder / policy_stem

        result = self.logic_extractor.process(
            markdown_path=str(acquired_md_path),
            output_base_path=str(output_base_path),
            symbol_table_json_path=symbol_table_path,
            progress_callback=progress_callback
        )

        logger.info(
            f"Logic extraction complete: {result.get('total_rules', 0)} rules, "
            f"{result.get('total_sections', 0)} sections"
        )

        return result

    def _generate_processing_summary(
        self,
        pdf_path: Path,
        processing_folder: Path,
        acquisition_result: Dict[str, Any],
        symbol_result: Dict[str, Any],
        logic_result: Dict[str, Any],
        start_time: float,
        error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Generate processing summary and save to JSON.

        Args:
            pdf_path: Path to source PDF
            processing_folder: Processing folder
            acquisition_result: Azure DI result
            symbol_result: Symbol extraction result
            logic_result: Logic extraction result
            start_time: Processing start timestamp
            error: Optional error that occurred

        Returns:
            Summary dictionary
        """
        logger.info(f"[4/4] Generating processing summary...")

        processing_time = time.time() - start_time

        summary = {
            "source_pdf": str(pdf_path),
            "processing_folder": str(processing_folder),
            "timestamp": datetime.now().isoformat(),
            "processing_time_seconds": round(processing_time, 2),
            "status": "failed" if error else "success",
        }

        if error:
            summary["error"] = str(error)
            summary["error_type"] = type(error).__name__
        else:
            # Add stage results
            summary["acquisition"] = {
                "pages": acquisition_result.get("total_pages", 0),
                "tables": acquisition_result.get("table_count", 0),
                "paragraphs": acquisition_result.get("paragraph_count", 0),
                "language": acquisition_result.get("language", "unknown"),
            }

            summary["symbols"] = {
                "total": symbol_result.get("total_symbols", 0),
            }

            summary["logic"] = {
                "total_rules": logic_result.get("total_rules", 0),
                "total_sections": logic_result.get("total_sections", 0),
                "chunked": logic_result.get("_chunked", False),
                "chunk_count": logic_result.get("_chunk_count", 0),
                "violations": logic_result.get("_validation_summary", {}).get("violations", 0),
                "critical_violations": logic_result.get("_validation_summary", {}).get("critical_violations", 0),
                "warnings": logic_result.get("_validation_summary", {}).get("warnings", 0),
            }

            # Token usage
            if "_usage" in logic_result:
                summary["token_usage"] = logic_result["_usage"]

        # Save summary to JSON
        summary_path = processing_folder / "processing_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Processing summary saved to: {summary_path.name}")

        return summary

    def process_pdf(
        self,
        pdf_path: Path,
        base_output_dir: Path,
        progress_callback=None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process a single PDF through the complete pipeline.

        Pipeline:
        1. Create processing folder
        2. Copy PDF
        3. Azure DI acquisition
        4. Symbol extraction
        5. Logic extraction
        6. Generate summary

        Args:
            pdf_path: Path to PDF file
            base_output_dir: Base directory for processing folders
            progress_callback: Optional progress callback for chunk updates
            timestamp: Optional timestamp for folder naming (default: now)

        Returns:
            Processing summary dictionary

        Raises:
            Exception: If any stage fails (caller should handle)
        """
        start_time = time.time()
        policy_stem = get_policy_stem(pdf_path)

        logger.info(f"Starting pipeline for: {pdf_path.name}")

        # Initialize progress callback if not provided
        if progress_callback is None:
            progress_callback = NoOpProgressCallback()

        # Initialize extractors
        self._initialize_extractors()

        # Create processing folder
        processing_folder = self._create_processing_folder(
            pdf_path, base_output_dir, timestamp
        )

        acquisition_result = {}
        symbol_result = {}
        logic_result = {}
        error = None
        total_stages = 4

        try:
            # Stage 1: Copy PDF to processing folder
            progress_callback.on_stage_start(1, total_stages, "Copying PDF")
            self._copy_pdf(pdf_path, processing_folder)
            progress_callback.on_stage_complete(1, total_stages, "Copying PDF")

            # Stage 2: Azure DI Acquisition
            progress_callback.on_stage_start(2, total_stages, "Azure DI Acquisition")
            acquisition_result = self._run_acquisition(
                pdf_path, processing_folder, policy_stem
            )
            progress_callback.on_stage_complete(2, total_stages, "Azure DI Acquisition")

            # Get acquired markdown path
            acquired_md_name = f"{policy_stem}_acquired.md"
            acquired_md_path = processing_folder / acquired_md_name

            if not acquired_md_path.exists():
                raise FileNotFoundError(f"Acquired markdown not found: {acquired_md_path}")

            # Stage 3: Symbol extraction
            progress_callback.on_stage_start(3, total_stages, "Symbol Extraction")
            symbol_result = self._run_symbol_extraction(
                acquired_md_path, processing_folder, policy_stem
            )
            progress_callback.on_stage_complete(3, total_stages, "Symbol Extraction")

            symbol_table_path = symbol_result.get('symbol_table_json')

            # Stage 4: Logic extraction
            progress_callback.on_stage_start(4, total_stages, "Logic Extraction")
            logic_result = self._run_logic_extraction(
                acquired_md_path,
                symbol_table_path,
                processing_folder,
                policy_stem,
                progress_callback
            )
            progress_callback.on_stage_complete(4, total_stages, "Logic Extraction")

        except Exception as e:
            logger.error(f"Pipeline failed for {pdf_path.name}: {e}")
            error = e

        # Stage 4: Generate summary (always, even on error)
        summary = self._generate_processing_summary(
            pdf_path,
            processing_folder,
            acquisition_result,
            symbol_result,
            logic_result,
            start_time,
            error
        )

        if error:
            # Re-raise to allow caller to handle
            raise error

        logger.info(f"Pipeline complete for {pdf_path.name} in {summary['processing_time_seconds']}s")

        return summary
