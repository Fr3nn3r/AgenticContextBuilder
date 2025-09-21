# intake/processors/enrichment.py

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel

from .base import BaseProcessor
from ..models import DocumentInsights, KeyDataPoint, EnrichmentMetadata
from ..services import PromptProvider
from .content_support.interfaces.ai_provider import AIProviderInterface
from .content_support.services.ai_analysis import OpenAIProvider
from .content_support.config import AIConfig


class EnrichmentProcessor(BaseProcessor):
    """
    Enriches documents with business-oriented insights and key data extraction.

    This processor analyzes document content to provide:
    - Meaningful document summaries
    - Business category classification
    - Key data point extraction
    - Confidence scoring for all extractions
    """

    VERSION = "2.0.0"
    DESCRIPTION = "Enriches documents with business insights and key data extraction"
    SUPPORTED_EXTENSIONS = ["*"]  # Supports all file types

    def __init__(self, config: Optional[Union[Dict[str, Any], BaseModel]] = None):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        # Default configuration
        self.config.setdefault('enable_document_insights', True)
        self.config.setdefault('enable_key_extraction', True)
        self.config.setdefault('max_key_points', 10)
        self.config.setdefault('confidence_threshold', 0.7)
        self.config.setdefault('max_retries', 2)
        self.config.setdefault('timeout_seconds', 30)
        self.config.setdefault('batch_pages', True)
        self.config.setdefault('max_pages_per_batch', 10)

        # Initialize components
        self._init_prompt_provider()
        self._init_ai_provider()
        self._enrichment_cache = {}

    def _init_prompt_provider(self):
        """Initialize the prompt provider with enrichment configuration."""
        config_file = self.config.get('prompts_config_file', 'config/enrichment_config.json')
        config_path = Path(config_file)

        if config_path.exists():
            with open(config_path, 'r') as f:
                enrichment_config = json.load(f)
                self.prompt_provider = PromptProvider(
                    prompts_dir=Path('prompts'),
                    config=enrichment_config
                )
        else:
            self.logger.warning(f"Enrichment config not found at {config_path}")
            self.prompt_provider = None

    def _init_ai_provider(self):
        """Initialize the AI provider for document analysis."""
        try:
            ai_config = AIConfig()
            self.ai_provider = OpenAIProvider(ai_config)
        except Exception as e:
            self.logger.error(f"Failed to initialize AI provider: {e}")
            self.ai_provider = None

    def process_file(self, file_path: Path, existing_metadata: Optional[Union[Dict[str, Any], BaseModel]] = None) -> Dict[str, Any]:
        """
        Enrich document metadata with business insights.

        Args:
            file_path: Path to the file to process
            existing_metadata: Metadata from previous processors

        Returns:
            Dictionary containing document insights
        """
        if not self.config.get('enable_document_insights', True):
            return {}

        # Check if content was extracted by ContentProcessor
        if not existing_metadata or 'file_content' not in existing_metadata:
            self.logger.info(f"No content found for enrichment: {file_path.name}")
            return {}

        start_time = time.time()

        try:
            # Extract content data
            file_content = existing_metadata.get('file_content', {})
            content_data = file_content.get('content_data', {})
            content_metadata = file_content.get('content_metadata', {})

            # Process based on extraction method
            if 'pages' in content_data:
                # Vision API results - synthesize from pages
                insights = self._synthesize_pages(content_data, content_metadata)
            elif 'text' in content_data:
                # OCR/text results - analyze directly
                insights = self._analyze_text(content_data['text'], content_metadata)
            else:
                self.logger.warning(f"No processable content in file: {file_path.name}")
                return {}

            # Build enrichment metadata
            processing_time_ms = (time.time() - start_time) * 1000

            enrichment = EnrichmentMetadata(
                document_insights=insights,
                enrichment_version=self.VERSION,
                enrichment_timestamp=datetime.now().isoformat(),
                processing_time_ms=processing_time_ms
            )

            return {'enrichment_metadata': enrichment.model_dump()}

        except Exception as e:
            self.logger.error(f"Enrichment failed for {file_path.name}: {str(e)}")
            return {
                'enrichment_metadata': {
                    'error': str(e),
                    'enrichment_version': self.VERSION,
                    'enrichment_timestamp': datetime.now().isoformat()
                }
            }

    def _synthesize_pages(self, content_data: Dict, content_metadata: Dict) -> DocumentInsights:
        """
        Synthesize document insights from multi-page Vision API results.

        Args:
            content_data: Content data with pages
            content_metadata: Metadata about content extraction

        Returns:
            DocumentInsights object
        """
        pages = content_data.get('pages', [])
        extraction_method = content_data.get('_extraction_method', 'Vision API')

        if not pages:
            raise ValueError("No pages to synthesize")

        # Prepare pages summary for synthesis prompt
        pages_summary = json.dumps(pages[:self.config.get('max_pages_per_batch', 10)])

        # Get synthesis prompt
        prompt = self.prompt_provider.get_prompt_template(
            'document-enrichment',
            role='synthesis',
            pages_summary=pages_summary,
            page_count=len(pages),
            extraction_method=extraction_method
        )

        # Call AI for synthesis
        response = self._call_ai_with_retry(prompt)

        # Parse response
        insights_data = self._parse_json_response(response)

        # Create DocumentInsights
        return DocumentInsights(
            summary=insights_data.get('summary', 'Document processed'),
            content_category=insights_data.get('content_category', 'other'),
            key_data_points=[
                KeyDataPoint(**kdp) for kdp in insights_data.get('key_data_points', [])
            ][:self.config.get('max_key_points', 10)],
            category_confidence=insights_data.get('category_confidence', 0.5),
            language=insights_data.get('language'),
            total_pages_analyzed=len(pages),
            extraction_method=extraction_method
        )

    def _analyze_text(self, text_content: str, content_metadata: Dict) -> DocumentInsights:
        """
        Analyze text content to extract document insights.

        Args:
            text_content: Text to analyze
            content_metadata: Metadata about content extraction

        Returns:
            DocumentInsights object
        """
        # Truncate if needed
        max_chars = 8000
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n[... content truncated ...]"

        # Get analysis prompt
        prompt = self.prompt_provider.get_prompt_template(
            'document-enrichment',
            role='analysis',
            content=text_content
        )

        # Call AI for analysis
        response = self._call_ai_with_retry(prompt)

        # Parse response
        insights_data = self._parse_json_response(response)

        # Create DocumentInsights
        return DocumentInsights(
            summary=insights_data.get('summary', 'Document analyzed'),
            content_category=insights_data.get('content_category', 'other'),
            key_data_points=[
                KeyDataPoint(**kdp) for kdp in insights_data.get('key_data_points', [])
            ][:self.config.get('max_key_points', 10)],
            category_confidence=insights_data.get('category_confidence', 0.5),
            language=insights_data.get('language'),
            extraction_method=content_metadata.get('extraction_method', 'OCR')
        )

    def _call_ai_with_retry(self, prompt: str) -> str:
        """
        Call AI provider with retry logic.

        Args:
            prompt: The prompt to send

        Returns:
            AI response string
        """
        if not self.ai_provider:
            raise ValueError("AI provider not initialized")

        max_retries = self.config.get('max_retries', 2)

        for attempt in range(max_retries + 1):
            try:
                response = self.ai_provider.analyze_text(
                    prompt,
                    model="gpt-4o",
                    max_tokens=1500,
                    temperature=0.3
                )
                return response
            except Exception as e:
                if attempt == max_retries:
                    raise
                self.logger.warning(f"AI call failed (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

    def _parse_json_response(self, response: str) -> Dict:
        """
        Parse JSON response from AI.

        Args:
            response: Raw AI response

        Returns:
            Parsed JSON dictionary
        """
        try:
            # Clean response if needed
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]

            return json.loads(response)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {e}")
            # Return minimal valid structure
            return {
                'summary': 'Failed to parse document insights',
                'content_category': 'other',
                'key_data_points': [],
                'category_confidence': 0.0
            }

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid
        """
        # Required components
        if not self.prompt_provider:
            self.logger.warning("Prompt provider not initialized")
            return False

        if not self.ai_provider:
            self.logger.warning("AI provider not initialized")
            return False

        # Validate configuration values
        required_configs = [
            'enable_document_insights',
            'enable_key_extraction',
            'max_key_points',
            'confidence_threshold'
        ]

        for config_key in required_configs:
            if config_key not in self.config:
                self.logger.warning(f"Missing required config: {config_key}")
                return False

        # Validate numeric ranges
        if self.config['max_key_points'] < 1 or self.config['max_key_points'] > 50:
            self.logger.warning("max_key_points should be between 1 and 50")
            return False

        if self.config['confidence_threshold'] < 0.0 or self.config['confidence_threshold'] > 1.0:
            self.logger.warning("confidence_threshold should be between 0.0 and 1.0")
            return False

        return True