"""Keyword matcher for German automotive terms to policy categories.

The keyword matcher maps German automotive repair terms to policy coverage
categories using configurable keyword mappings. It uses context hints to
improve matching accuracy (e.g., VENTIL + HYDRAULIK -> chassis).

Confidence levels:
- Exact keyword match: 0.85-0.90
- Partial/context match: 0.70-0.85
- Ambiguous match: 0.60-0.70 (may still trigger LLM fallback)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class KeywordMapping:
    """A mapping from keywords to a policy category."""

    category: str  # Policy category (e.g., "engine", "chassis")
    keywords: List[str]  # German keywords that map to this category
    context_hints: List[str] = field(default_factory=list)  # Contextual modifiers
    confidence: float = 0.85  # Base confidence for this mapping
    component_name: Optional[str] = None  # Specific component if known


@dataclass
class KeywordConfig:
    """Configuration for keyword matcher."""

    mappings: List[KeywordMapping]
    min_confidence_threshold: float = 0.70
    labor_coverage_categories: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "KeywordConfig":
        """Create config from dictionary (loaded from YAML)."""
        mappings = []
        for mapping in config.get("mappings", []):
            mappings.append(
                KeywordMapping(
                    category=mapping["category"],
                    keywords=mapping["keywords"],
                    context_hints=mapping.get("context_hints", []),
                    confidence=mapping.get("confidence", 0.85),
                    component_name=mapping.get("component_name"),
                )
            )
        return cls(
            mappings=mappings,
            min_confidence_threshold=config.get("min_confidence_threshold", 0.70),
            labor_coverage_categories=config.get("labor_coverage_categories", []),
        )

    @classmethod
    def default_nsa(cls) -> "KeywordConfig":
        """Create default NSA German automotive mappings."""
        return cls(
            mappings=[
                # Engine components (German + French)
                KeywordMapping(
                    category="engine",
                    keywords=[
                        # German terms
                        "MOTOR", "KOLBEN", "KURBELWELLE", "NOCKENWELLE",
                        "ZYLINDER", "VENTIL", "PLEUEL", "ÖLPUMPE", "OELPUMPE",
                        "ZÜNDSPULE", "ZUENDSPULE", "ZÜNDKERZE", "ZUENDKERZE",
                        # Timing chain/belt (German)
                        "STEUERKETTE", "KETTENSPANNER", "KETTENFÜHRUNG",
                        "KETTENFUEHRUNG", "STEUERKETTENSPANNER",
                        "ZAHNRIEMEN", "RIEMENSPANNER", "UMLENKROLLE",
                        "SPANNROLLE", "RIEMENSCHEIBE",
                        # French terms
                        "MOTEUR", "PISTON", "VILEBREQUIN", "CULASSE",
                        "SOUPAPE", "BIELLE", "POMPE À HUILE", "POMPE A HUILE",
                        # Timing chain/belt (French)
                        "CHAÎNE", "CHAINE", "DISTRIBUTION", "TENDEUR",
                        "GUIDE", "POULIE", "PIGNON",
                    ],
                    context_hints=["MOTOR", "ENGINE", "MOTEUR", "DISTRIBUTION"],
                    confidence=0.88,
                ),
                # Transmission (German + French)
                KeywordMapping(
                    category="mechanical_transmission",
                    keywords=[
                        # German
                        "GETRIEBE", "SCHALTGABEL", "SYNCHRON",
                        "ANTRIEBSWELLE", "KUPPLUNG",
                        # French
                        "BOÎTE DE VITESSES", "BOITE DE VITESSES", "EMBRAYAGE",
                        "TRANSMISSION", "FOURCHETTE", "SYNCHRONISEUR",
                        "ARBRE DE TRANSMISSION",
                    ],
                    confidence=0.85,
                ),
                # Chassis/Suspension - includes hydraulic level control (German + French)
                KeywordMapping(
                    category="chassis",
                    keywords=[
                        # German
                        "FAHRWERK", "STOSSDÄMPFER", "STOSSDAEMPFER",
                        "FEDERBEIN", "STABILISATOR", "HÖHENVERSTELLUNG",
                        "NIVEAUREGULIERUNG", "NIVEAU", "HYDRAULIK",
                        # French
                        "AMORTISSEUR", "RESSORT", "SUSPENSION",
                        "RÉGLAGE DE NIVEAU", "HYDRAULIQUE",
                    ],
                    context_hints=["NIVEAU", "HOEHE", "HÖHE", "HAUTEUR"],
                    confidence=0.85,
                    component_name="Height control",
                ),
                # Suspension arms and links (German + French)
                KeywordMapping(
                    category="suspension",
                    keywords=[
                        # German
                        "QUERLENKER", "LÄNGSLENKER", "LAENGSLENKER",
                        "SPURSTANGE", "ACHSE", "AUFHÄNGUNG", "AUFHAENGUNG",
                        # French
                        "BRAS DE SUSPENSION", "TRIANGLE", "BIELLETTE",
                        "ROTULE", "ESSIEU", "TRAIN ROULANT",
                    ],
                    confidence=0.85,
                ),
                # Brakes (German + French)
                KeywordMapping(
                    category="brakes",
                    keywords=[
                        # German
                        "BREMSE", "BREMSSCHEIBE", "BREMSSATTEL",
                        "ABS", "BREMSBELAG", "HAUPTBREMSZYLINDER",
                        "BREMSKRAFTVERSTÄRKER", "BREMSDRUCKREGLER",
                        # French
                        "FREIN", "DISQUE DE FREIN", "ÉTRIER", "ETRIER",
                        "PLAQUETTE", "MAÎTRE CYLINDRE", "MAITRE CYLINDRE",
                        "SERVOFREIN",
                    ],
                    confidence=0.88,
                ),
                # Steering (German + French)
                KeywordMapping(
                    category="steering",
                    keywords=[
                        # German
                        "LENKUNG", "SERVOLENKUNG", "LENKGETRIEBE",
                        "SERVOPUMPE", "LENKSÄULE", "LENKSAEULE",
                        # French
                        "DIRECTION", "SERVODIRECTION", "CRÉMAILLÈRE",
                        "CREMAILLERE", "COLONNE DE DIRECTION",
                        "POMPE DE DIRECTION",
                    ],
                    confidence=0.85,
                ),
                # Electrical system (German + French)
                KeywordMapping(
                    category="electrical_system",
                    keywords=[
                        # German
                        "LICHTMASCHINE", "ANLASSER", "STARTER",
                        "SCHEIBENWISCHERMOTOR", "ZENTRALVERRIEGELUNG",
                        "STEUERGERÄT", "STEUERGERAET", "STG",
                        # French
                        "ALTERNATEUR", "DÉMARREUR", "DEMARREUR",
                        "MOTEUR ESSUIE-GLACE", "VERROUILLAGE CENTRAL",
                        "CALCULATEUR", "MODULE DE COMMANDE", "BOÎTIER",
                    ],
                    confidence=0.85,
                ),
                # Air conditioning (German + French)
                KeywordMapping(
                    category="air_conditioning",
                    keywords=[
                        # German
                        "KLIMAANLAGE", "KLIMA", "KOMPRESSOR",
                        "KLIMAKOMPRESSOR", "VERDAMPFER", "KONDENSATOR",
                        # French
                        "CLIMATISATION", "CLIM", "COMPRESSEUR",
                        "ÉVAPORATEUR", "EVAPORATEUR", "CONDENSEUR",
                    ],
                    context_hints=["KLIMA", "A/C", "AC", "CLIM"],
                    confidence=0.88,
                ),
                # Cooling system (German + French)
                KeywordMapping(
                    category="cooling_system",
                    keywords=[
                        # German
                        "KÜHLER", "KUEHLER", "WASSERPUMPE", "THERMOSTAT",
                        "LÜFTER", "LUEFTER", "KÜHLMITTELPUMPE",
                        # French
                        "RADIATEUR", "POMPE À EAU", "POMPE A EAU",
                        "VENTILATEUR", "REFROIDISSEMENT",
                    ],
                    confidence=0.85,
                ),
                # Electronics
                KeywordMapping(
                    category="electronics",
                    keywords=[
                        "SPURWECHSELASSISTENT", "ESP", "SENSOR",
                        "DISPLAY", "COMPUTER", "BOARDCOMPUTER",
                        "ALARMANLAGE",
                    ],
                    confidence=0.80,
                ),
                # Fuel system (German + French)
                KeywordMapping(
                    category="fuel_system",
                    keywords=[
                        # German
                        "KRAFTSTOFFPUMPE", "BENZINPUMPE", "EINSPRITZPUMPE",
                        "EINSPRITZVENTIL", "DRUCKREGLER",
                        # French
                        "POMPE À CARBURANT", "POMPE A CARBURANT",
                        "POMPE À ESSENCE", "POMPE A ESSENCE",
                        "INJECTEUR", "RÉGULATEUR DE PRESSION",
                        "RAMPE D'INJECTION",
                    ],
                    context_hints=["KRAFTSTOFF", "BENZIN", "DIESEL", "CARBURANT", "ESSENCE"],
                    confidence=0.85,
                ),
                # Axle drive (German + French)
                KeywordMapping(
                    category="axle_drive",
                    keywords=[
                        # German
                        "KARDANWELLE", "ANTRIEBSWELLE", "GELENKWELLE",
                        "DIFFERENTIAL", "ACHSANTRIEB",
                        # French
                        "CARDAN", "ARBRE DE TRANSMISSION", "DIFFÉRENTIEL",
                        "DIFFERENTIEL", "PONT ARRIÈRE", "PONT ARRIERE",
                    ],
                    confidence=0.85,
                ),
            ],
            min_confidence_threshold=0.70,
            labor_coverage_categories=[
                "engine", "mechanical_transmission", "chassis", "suspension",
                "brakes", "steering", "electrical_system", "air_conditioning",
                "cooling_system", "electronics", "fuel_system", "axle_drive",
            ],
        )


class KeywordMatcher:
    """German keyword-based coverage matching.

    The keyword matcher is the second matcher in the coverage analysis pipeline,
    handling items that passed through the rule engine. It maps German automotive
    terms to policy coverage categories.
    """

    def __init__(self, config: Optional[KeywordConfig] = None):
        """Initialize the keyword matcher.

        Args:
            config: Keyword configuration. Uses NSA defaults if not provided.
        """
        self.config = config or KeywordConfig.default_nsa()

        # Build lookup structures for fast matching
        self._build_lookup_tables()

    def _build_lookup_tables(self) -> None:
        """Build keyword lookup tables for efficient matching."""
        self._keyword_to_mapping: Dict[str, KeywordMapping] = {}
        self._context_hints: Dict[str, Set[str]] = {}

        for mapping in self.config.mappings:
            for keyword in mapping.keywords:
                # Store uppercase for case-insensitive matching
                self._keyword_to_mapping[keyword.upper()] = mapping

            # Build context hint lookup
            for hint in mapping.context_hints:
                hint_upper = hint.upper()
                if hint_upper not in self._context_hints:
                    self._context_hints[hint_upper] = set()
                self._context_hints[hint_upper].add(mapping.category)

    def match(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str] = None,
        total_price: float = 0.0,
        covered_categories: Optional[List[str]] = None,
    ) -> Optional[LineItemCoverage]:
        """Attempt to match a line item using keyword mappings.

        Args:
            description: Item description (usually in German)
            item_type: Item type (parts, labor, fee)
            item_code: Optional item code
            total_price: Item total price
            covered_categories: List of categories covered by the policy

        Returns:
            LineItemCoverage if matched by keywords, None otherwise
        """
        covered_categories = covered_categories or []
        description_upper = description.upper()

        # Find all matching keywords in the description
        matches: List[Tuple[str, KeywordMapping, float]] = []

        for keyword, mapping in self._keyword_to_mapping.items():
            if keyword in description_upper:
                # Base confidence from mapping
                confidence = mapping.confidence

                # Boost confidence if context hints match
                for hint in mapping.context_hints:
                    if hint.upper() in description_upper:
                        confidence = min(0.95, confidence + 0.05)
                        break

                matches.append((keyword, mapping, confidence))

        if not matches:
            return None

        # Select the best match (highest confidence)
        matches.sort(key=lambda x: x[2], reverse=True)
        keyword, best_mapping, confidence = matches[0]

        # Check if the category is covered by policy
        category = best_mapping.category
        is_covered = self._is_category_covered(category, covered_categories)

        # Labor items may be covered if they relate to covered components
        if item_type.lower() == "labor":
            # Labor is covered if working on covered components
            if category in self.config.labor_coverage_categories and is_covered:
                pass  # Keep as covered
            else:
                # Labor for non-covered categories
                confidence *= 0.9  # Reduce confidence

        if is_covered:
            return LineItemCoverage(
                item_code=item_code,
                description=description,
                item_type=item_type,
                total_price=total_price,
                coverage_status=CoverageStatus.COVERED,
                coverage_category=category,
                matched_component=best_mapping.component_name,
                match_method=MatchMethod.KEYWORD,
                match_confidence=confidence,
                match_reasoning=f"Keyword '{keyword}' maps to covered category '{category}'",
                covered_amount=total_price,
                not_covered_amount=0.0,
            )
        else:
            return LineItemCoverage(
                item_code=item_code,
                description=description,
                item_type=item_type,
                total_price=total_price,
                coverage_status=CoverageStatus.NOT_COVERED,
                coverage_category=category,
                matched_component=best_mapping.component_name,
                match_method=MatchMethod.KEYWORD,
                match_confidence=confidence,
                match_reasoning=f"Keyword '{keyword}' maps to category '{category}' which is not covered",
                covered_amount=0.0,
                not_covered_amount=total_price,
            )

    def _is_category_covered(
        self, category: str, covered_categories: List[str]
    ) -> bool:
        """Check if a category is covered by the policy.

        Args:
            category: Category name (e.g., "engine", "chassis")
            covered_categories: List of categories from policy

        Returns:
            True if the category is covered
        """
        # Normalize category names for comparison
        category_lower = category.lower().replace("_", " ")
        for covered in covered_categories:
            covered_lower = covered.lower().replace("_", " ")
            if category_lower == covered_lower:
                return True
            # Handle variations
            if category_lower in covered_lower or covered_lower in category_lower:
                return True
        return False

    def batch_match(
        self,
        items: List[Dict[str, Any]],
        covered_categories: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match multiple items, returning matched and unmatched lists.

        Args:
            items: List of line item dictionaries
            covered_categories: List of categories from policy
            min_confidence: Minimum confidence to accept match (defaults to config)

        Returns:
            Tuple of (matched items, unmatched items for LLM processing)
        """
        min_conf = min_confidence or self.config.min_confidence_threshold
        matched = []
        unmatched = []

        for item in items:
            result = self.match(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
                item_code=item.get("item_code"),
                total_price=item.get("total_price") or 0.0,
                covered_categories=covered_categories,
            )

            if result and result.match_confidence >= min_conf:
                matched.append(result)
            else:
                unmatched.append(item)

        logger.debug(
            f"Keyword matcher: {len(matched)} matched, {len(unmatched)} unmatched"
        )
        return matched, unmatched
