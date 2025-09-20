# intake/processors/content_support/handlers/spreadsheet_handler.py
# Handler for spreadsheet files (CSV, Excel)
# Processes tabular data and extracts insights

from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseContentHandler
from ..models import FileContentOutput, ContentProcessorError
from ..services import track_processing_time


class SpreadsheetContentHandler(BaseContentHandler):
    """Handler for spreadsheet files."""

    SUPPORTED_EXTENSIONS = {'.csv', '.xls', '.xlsx'}

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported spreadsheet type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process spreadsheet file."""
        with track_processing_time("spreadsheet_processing") as metrics:
            try:
                # Lazy import pandas
                import pandas as pd

                # Read spreadsheet data
                df = self._read_spreadsheet(file_path, pd)

                # Convert to JSON for AI analysis
                json_data = df.to_json(orient="records")

                # Truncate if necessary
                truncated_data = self._truncate_json(json_data)

                # Get prompt configuration
                prompt_name = "spreadsheet_analysis"
                prompt_config = self.prompt_manager.get_active_prompt(prompt_name)
                prompt_version = self.prompt_manager.get_active_version(prompt_name)

                if not prompt_config or not prompt_version:
                    raise ContentProcessorError(
                        f"Prompt '{prompt_name}' not found",
                        error_type="prompt_not_found"
                    )

                # Get AI analysis
                prompt_template = self.prompt_manager.get_prompt_template(
                    prompt_name,
                    content=truncated_data
                )

                ai_response = self.ai_service.analyze_content(
                    prompt_template,
                    model=prompt_config.model,
                    max_tokens=prompt_config.max_tokens,
                    temperature=prompt_config.temperature
                )

                # Parse response
                parsed_data, summary = self.response_parser.parse_ai_response(
                    ai_response,
                    expected_format=prompt_config.output_format or "text"
                )

                # Create output
                default_summary = f"Spreadsheet with {len(df)} rows and {len(df.columns)} columns"
                content_metadata = self.create_content_metadata(
                    content_type="spreadsheet",
                    file_category="spreadsheet",
                    summary=summary if parsed_data else default_summary
                )

                processing_info = self.create_processing_info(
                    status="success",
                    ai_model=prompt_config.model,
                    prompt_version=prompt_version,
                    processing_time=metrics.duration_seconds,
                    extraction_method="Direct Parsing"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    content_data=parsed_data,
                    data_spreadsheet_content=json_data
                )

            except Exception as e:
                self.logger.error(f"Spreadsheet processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="spreadsheet",
                    file_category="spreadsheet"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata
                )

    def _read_spreadsheet(self, file_path: Path, pd):
        """Read spreadsheet file based on extension."""
        try:
            if file_path.suffix.lower() == '.csv':
                return pd.read_csv(file_path)
            else:
                return pd.read_excel(file_path)
        except Exception as e:
            raise ContentProcessorError(
                f"Failed to read spreadsheet: {str(e)}",
                error_type="spreadsheet_read_error"
            )

    def _truncate_json(self, json_data: str) -> str:
        """Truncate JSON data if too large."""
        max_chars = self.config.get('json_truncation_chars', 6000)
        if len(json_data) > max_chars:
            return json_data[:max_chars] + "\n[... data truncated ...]"
        return json_data