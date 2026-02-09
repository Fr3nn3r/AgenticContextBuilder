"""Coverage analysis service for determining line item coverage.

This service provides the integration layer between the coverage analysis
components and the claim processing pipeline. It loads claim facts, extracts
relevant policy data, runs coverage analysis, and stores results.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from context_builder.coverage.analyzer import CoverageAnalyzer
from context_builder.coverage.explanation_generator import (
    ExplanationConfig,
    ExplanationGenerator,
)
from context_builder.coverage.schemas import CoverageAnalysisResult
from context_builder.storage.filesystem import FileStorage
from context_builder.utils.number_parsing import parse_european_number

logger = logging.getLogger(__name__)


class CoverageAnalysisError(Exception):
    """Raised when coverage analysis fails."""

    pass


class CoverageAnalysisService:
    """Service for analyzing line item coverage for claims.

    This service:
    1. Loads claim_facts.json from the latest claim run
    2. Extracts line items, covered components, and policy data
    3. Runs coverage analysis using the CoverageAnalyzer
    4. Writes coverage_analysis.json to the claim run

    Usage:
        service = CoverageAnalysisService(storage)
        result = service.analyze_claim(claim_id="65196")
    """

    def __init__(self, storage: FileStorage):
        """Initialize the coverage analysis service.

        Args:
            storage: Storage protocol for accessing workspace data
        """
        self.storage = storage
        self._analyzer: Optional[CoverageAnalyzer] = None
        self._explanation_generator: Optional[ExplanationGenerator] = None

    def _get_analyzer(self) -> CoverageAnalyzer:
        """Get or create the coverage analyzer with config from workspace."""
        if self._analyzer is not None:
            return self._analyzer

        # Try to load config from workspace using glob-based discovery
        workspace_root = self.storage.output_root
        coverage_dir = workspace_root / "config" / "coverage"
        config_path = None

        if coverage_dir.exists():
            matches = list(coverage_dir.glob("*_coverage_config.yaml"))
            if matches:
                config_path = matches[0]
                if len(matches) > 1:
                    logger.warning(
                        f"Multiple coverage configs found: {[m.name for m in matches]}, "
                        f"using {config_path.name}"
                    )

        if config_path and config_path.exists():
            logger.info(f"Loading coverage config from {config_path}")
            self._analyzer = CoverageAnalyzer.from_config_path(
                config_path, workspace_path=workspace_root
            )
        else:
            logger.info("No coverage config found in workspace, using default analyzer")
            self._analyzer = CoverageAnalyzer(workspace_path=workspace_root)

        return self._analyzer

    @staticmethod
    def _create_explanation_llm_client(claim_id: str) -> Any:
        """Create an audited LLM client for non-covered explanations.

        Returns None if the client cannot be created (e.g., no API key),
        which causes the generator to fall back to template mode.
        """
        try:
            from context_builder.services.llm_audit import create_audited_client

            client = create_audited_client()
            client.set_context(
                claim_id=claim_id,
                call_purpose="non_covered_explanation",
            )
            return client
        except Exception:
            logger.warning(
                "Could not create LLM client for non-covered explanations; "
                "falling back to template mode",
                exc_info=True,
            )
            return None

    def _get_explanation_generator(self) -> ExplanationGenerator:
        """Get or create the explanation generator with config from workspace."""
        if self._explanation_generator is not None:
            return self._explanation_generator

        workspace_root = self.storage.output_root
        coverage_dir = workspace_root / "config" / "coverage"
        config: Optional[ExplanationConfig] = None

        if coverage_dir.exists():
            matches = list(coverage_dir.glob("*_explanation_templates.yaml"))
            if matches:
                config_path = matches[0]
                if len(matches) > 1:
                    logger.warning(
                        f"Multiple explanation template configs found: "
                        f"{[m.name for m in matches]}, using {config_path.name}"
                    )
                logger.info(f"Loading explanation templates from {config_path}")
                config = ExplanationConfig.from_yaml(config_path)

        if config is None:
            logger.info("No explanation templates found, using default config")
            config = ExplanationConfig.default()

        self._explanation_generator = ExplanationGenerator(config)
        return self._explanation_generator

    def _get_latest_claim_run(self, claim_id: str) -> Optional[Tuple[str, Path]]:
        """Get the latest claim run ID and path for a claim.

        Args:
            claim_id: Claim identifier

        Returns:
            Tuple of (claim_run_id, claim_run_path) or None if not found
        """
        claims_dir = self.storage.output_root / "claims"
        claim_runs_dir = claims_dir / claim_id / "claim_runs"

        if not claim_runs_dir.exists():
            return None

        # Find latest claim run by timestamp in directory name
        # Format: clm_YYYYMMDD_HHMMSS_xxxxxx
        runs = [d for d in claim_runs_dir.iterdir() if d.is_dir()]
        if not runs:
            return None

        # Sort by name (timestamp-based) descending
        runs.sort(key=lambda p: p.name, reverse=True)
        latest_run = runs[0]

        return latest_run.name, latest_run

    def _load_claim_facts(self, claim_run_path: Path) -> Optional[Dict[str, Any]]:
        """Load claim_facts.json from a claim run.

        Args:
            claim_run_path: Path to the claim run directory

        Returns:
            Claim facts dictionary or None if not found
        """
        facts_path = claim_run_path / "claim_facts.json"

        if not facts_path.exists():
            logger.warning(f"claim_facts.json not found at {facts_path}")
            return None

        try:
            with open(facts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load claim_facts.json: {e}")
            return None

    def _extract_fact_value(
        self, facts: List[Dict[str, Any]], name: str, default: Any = None
    ) -> Any:
        """Extract a fact value by name from facts list.

        Also checks for prefixed names (e.g., "cost_estimate.field_name").

        Args:
            facts: List of fact dictionaries
            name: Fact name to find
            default: Default value if not found

        Returns:
            Fact value, normalized_value, or structured_value, or default
        """
        for fact in facts:
            fact_name = fact.get("name", "")
            # Check both exact match and prefixed match (e.g., "cost_estimate.field")
            if fact_name == name or fact_name.endswith(f".{name}"):
                # Prefer structured_value, then value
                if fact.get("structured_value") is not None:
                    return fact["structured_value"]
                return fact.get("value", default)
        return default

    def _extract_line_items(self, claim_facts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract line items from claim facts.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            List of line item dictionaries
        """
        # First check structured_data
        structured_data = claim_facts.get("structured_data", {})
        if structured_data and structured_data.get("line_items"):
            return structured_data["line_items"]

        # Fall back to facts list with structured_value
        facts = claim_facts.get("facts", [])
        line_items_fact = self._extract_fact_value(facts, "line_items")
        if isinstance(line_items_fact, list):
            return line_items_fact

        return []

    @staticmethod
    def _normalize_component_name(name: str) -> str:
        """Fix known PDF extraction encoding issues in component names.

        French 'à' (U+00E0) is sometimes extracted as NBSP (U+00A0) from PDFs.
        Example: "pompe \\xa0 huile" → "pompe à huile"
        """
        if isinstance(name, str):
            return name.replace("\xa0", "à")
        return name

    def _extract_covered_components(
        self, claim_facts: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Extract covered components from claim facts.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Dict mapping category to list of component names
        """
        facts = claim_facts.get("facts", [])
        covered = self._extract_fact_value(facts, "covered_components", {})

        if isinstance(covered, dict):
            return {
                k: [self._normalize_component_name(p) for p in v]
                for k, v in covered.items() if v
            }

        return {}

    def _extract_excluded_components(
        self, claim_facts: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Extract excluded components from claim facts.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Dict mapping category to list of excluded component names
        """
        facts = claim_facts.get("facts", [])
        excluded = self._extract_fact_value(facts, "excluded_components", {})

        if isinstance(excluded, dict):
            return {
                k: [self._normalize_component_name(p) for p in v]
                for k, v in excluded.items() if v
            }

        return {}

    def _extract_vehicle_km(self, claim_facts: Dict[str, Any]) -> Optional[int]:
        """Extract vehicle odometer reading from claim facts.

        Checks multiple possible field names in priority order.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Odometer reading in km or None
        """
        facts = claim_facts.get("facts", [])

        # Try multiple field names in priority order
        field_names = ["odometer_km", "km_stand", "mileage_km"]

        for name in field_names:
            value = self._extract_fact_value(facts, name)
            if value is not None:
                try:
                    # Handle string values with commas or quotes
                    if isinstance(value, str):
                        value = value.replace("'", "").replace(",", "")
                    return int(float(value))
                except (ValueError, TypeError):
                    continue

        return None

    def _extract_coverage_scale(
        self, claim_facts: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[List[Dict[str, Any]]]]:
        """Extract coverage scale from claim facts.

        Supports both old (list) and new (dict with age_threshold_years) formats
        via ``_normalize_coverage_scale``.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Tuple of (age_threshold_years, tiers_list).
        """
        from context_builder.coverage.analyzer import _normalize_coverage_scale

        facts = claim_facts.get("facts", [])
        raw_scale = self._extract_fact_value(facts, "coverage_scale")

        return _normalize_coverage_scale(raw_scale)

    def _parse_percent(self, value: Any) -> Optional[float]:
        """Parse a percentage value from various formats.

        Args:
            value: Value to parse (string like "10 %" or number)

        Returns:
            Numeric percentage or None
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Extract numeric part from strings like "10 %"
            match = re.search(r"([\d.]+)", value)
            if match:
                return float(match.group(1))

        return None

    def _parse_amount(self, value: Any) -> Optional[float]:
        """Parse a monetary amount from various formats.

        Uses parse_european_number to correctly handle European number formats:
        - "300,00 CHF" -> 300.00 (comma as decimal separator)
        - "1'000,50 CHF" -> 1000.50 (Swiss format)
        - "1.000,50 EUR" -> 1000.50 (European with dot thousands)

        Args:
            value: Value to parse (string like "150.00 CHF" or number)

        Returns:
            Numeric amount or None
        """
        return parse_european_number(value)

    def _extract_excess_info(
        self, claim_facts: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Extract excess percentage and minimum from claim facts.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Tuple of (excess_percent, excess_minimum)
        """
        facts = claim_facts.get("facts", [])

        excess_percent = self._parse_percent(
            self._extract_fact_value(facts, "excess_percent")
        )
        excess_minimum = self._parse_amount(
            self._extract_fact_value(facts, "excess_minimum")
        )

        return excess_percent, excess_minimum

    def _extract_vehicle_age(
        self, claim_facts: Dict[str, Any]
    ) -> Optional[float]:
        """Extract vehicle age in years from claim facts.

        Calculates age based on vehicle_first_registration and claim/document date.
        NSA policies use "Dès 8 ans 40%" rule for reduced coverage.

        Args:
            claim_facts: Claim facts dictionary

        Returns:
            Vehicle age in years or None if dates not available
        """
        from datetime import datetime

        facts = claim_facts.get("facts", [])

        # Get registration date (first registration)
        reg_date_str = self._extract_fact_value(
            facts, "vehicle_first_registration"
        ) or self._extract_fact_value(facts, "registration_date")

        if not reg_date_str:
            return None

        # Parse registration date (format: DD.MM.YYYY or DD.MM.YYYY XX)
        reg_date = None
        if isinstance(reg_date_str, str):
            # Remove any trailing text (like canton codes)
            date_part = reg_date_str.split()[0]
            for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    reg_date = datetime.strptime(date_part, fmt)
                    break
                except ValueError:
                    continue

        if not reg_date:
            logger.warning(f"Could not parse registration date: {reg_date_str}")
            return None

        # Get claim/document date for age calculation
        claim_date_str = self._extract_fact_value(
            facts, "cost_estimate.document_date"
        ) or self._extract_fact_value(facts, "document_date")

        claim_date = datetime.now()  # Default to current date
        if claim_date_str:
            if isinstance(claim_date_str, str):
                date_part = claim_date_str.split()[0]
                for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                    try:
                        claim_date = datetime.strptime(date_part, fmt)
                        break
                    except ValueError:
                        continue

        # Calculate age in years
        age_days = (claim_date - reg_date).days
        age_years = age_days / 365.25

        return age_years

    def _write_coverage_analysis(
        self, claim_run_path: Path, result: CoverageAnalysisResult
    ) -> Path:
        """Write coverage analysis result to claim run directory.

        Args:
            claim_run_path: Path to claim run directory
            result: Coverage analysis result

        Returns:
            Path to written file
        """
        output_path = claim_run_path / "coverage_analysis.json"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        logger.info(f"Wrote coverage analysis to {output_path}")
        return output_path

    def analyze_claim(
        self,
        claim_id: str,
        claim_run_id: Optional[str] = None,
        force: bool = False,
    ) -> CoverageAnalysisResult:
        """Analyze coverage for a claim.

        Args:
            claim_id: Claim identifier
            claim_run_id: Optional specific claim run ID (uses latest if not provided)
            force: If True, rerun even if coverage_analysis.json exists

        Returns:
            CoverageAnalysisResult

        Raises:
            CoverageAnalysisError: If analysis fails
        """
        # Get claim run
        if claim_run_id:
            claims_dir = self.storage.output_root / "claims"
            claim_run_path = claims_dir / claim_id / "claim_runs" / claim_run_id
            if not claim_run_path.exists():
                raise CoverageAnalysisError(
                    f"Claim run not found: {claim_run_id}"
                )
        else:
            result = self._get_latest_claim_run(claim_id)
            if not result:
                raise CoverageAnalysisError(
                    f"No claim runs found for claim {claim_id}"
                )
            claim_run_id, claim_run_path = result

        # Check for existing coverage analysis
        existing_path = claim_run_path / "coverage_analysis.json"
        if existing_path.exists() and not force:
            logger.info(f"Loading existing coverage analysis from {existing_path}")
            with open(existing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CoverageAnalysisResult.model_validate(data)

        # Load claim facts
        claim_facts = self._load_claim_facts(claim_run_path)
        if not claim_facts:
            raise CoverageAnalysisError(
                f"claim_facts.json not found for claim {claim_id}"
            )

        # Extract data for analysis
        line_items = self._extract_line_items(claim_facts)
        if not line_items:
            raise CoverageAnalysisError(
                f"No line items found in claim facts for {claim_id}"
            )

        covered_components = self._extract_covered_components(claim_facts)
        excluded_components = self._extract_excluded_components(claim_facts)
        vehicle_km = self._extract_vehicle_km(claim_facts)
        age_threshold_years, coverage_scale = self._extract_coverage_scale(claim_facts)
        excess_percent, excess_minimum = self._extract_excess_info(claim_facts)

        # Extract vehicle age for age-based coverage reduction
        vehicle_age_years = self._extract_vehicle_age(claim_facts)

        age_info = ""
        if vehicle_age_years is not None:
            age_info = f", age={vehicle_age_years:.1f}y"
        logger.info(
            f"Analyzing claim {claim_id}: {len(line_items)} items, "
            f"km={vehicle_km}{age_info}, {len(covered_components)} categories"
        )

        # Run analysis
        analyzer = self._get_analyzer()
        result = analyzer.analyze(
            claim_id=claim_id,
            line_items=line_items,
            covered_components=covered_components,
            excluded_components=excluded_components,
            vehicle_km=vehicle_km,
            coverage_scale=coverage_scale,
            excess_percent=excess_percent,
            excess_minimum=excess_minimum,
            claim_run_id=claim_run_id,
            vehicle_age_years=vehicle_age_years,
            age_threshold_years=age_threshold_years,
        )

        # Generate non-covered explanations (LLM rewrite when available)
        generator = self._get_explanation_generator()
        llm_client = self._create_explanation_llm_client(claim_id)
        explanations, summary = generator.generate(
            result,
            covered_components=covered_components,
            excluded_components=excluded_components,
            llm_client=llm_client,
        )
        if explanations:
            result.non_covered_explanations = explanations
            result.non_covered_summary = summary

        # Write results
        self._write_coverage_analysis(claim_run_path, result)

        return result

    def get_coverage_analysis(
        self, claim_id: str, claim_run_id: Optional[str] = None
    ) -> Optional[CoverageAnalysisResult]:
        """Get existing coverage analysis for a claim.

        Args:
            claim_id: Claim identifier
            claim_run_id: Optional specific claim run ID

        Returns:
            CoverageAnalysisResult or None if not found
        """
        if claim_run_id:
            claims_dir = self.storage.output_root / "claims"
            claim_run_path = claims_dir / claim_id / "claim_runs" / claim_run_id
        else:
            result = self._get_latest_claim_run(claim_id)
            if not result:
                return None
            _, claim_run_path = result

        coverage_path = claim_run_path / "coverage_analysis.json"
        if not coverage_path.exists():
            return None

        try:
            with open(coverage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CoverageAnalysisResult.model_validate(data)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load coverage analysis: {e}")
            return None

    def list_claims_for_analysis(self) -> List[str]:
        """List all claims that have claim_facts.json available.

        Returns:
            List of claim IDs
        """
        claims_dir = self.storage.output_root / "claims"
        if not claims_dir.exists():
            return []

        claim_ids = []
        for claim_dir in claims_dir.iterdir():
            if not claim_dir.is_dir():
                continue

            # Check if any claim run has claim_facts.json
            claim_runs_dir = claim_dir / "claim_runs"
            if claim_runs_dir.exists():
                for run_dir in claim_runs_dir.iterdir():
                    if (run_dir / "claim_facts.json").exists():
                        claim_ids.append(claim_dir.name)
                        break

        return sorted(claim_ids)
