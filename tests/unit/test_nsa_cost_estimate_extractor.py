"""Unit tests for NSA Cost Estimate extractor — labor placeholder price fix.

Tests the _fix_labor_placeholder_prices() method and its integration with
_merge_page_results().  The extractor is instantiated via a lightweight mock
that avoids real LLM / OpenAI dependencies.
"""

import copy
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from context_builder.extraction.spec_loader import get_spec
from context_builder.extraction.normalizers import safe_float

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NSA_EXTRACTOR = _PROJECT_ROOT / "workspaces" / "nsa" / "config" / "extractors" / "nsa_cost_estimate.py"
_nsa_available = _NSA_EXTRACTOR.exists()

pytestmark = pytest.mark.skipif(
    not _nsa_available,
    reason="NSA workspace extractor not available",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extractor():
    """Return a NsaCostEstimateExtractor with all external I/O mocked out."""
    spec = get_spec("cost_estimate")

    with patch("workspaces.nsa.config.extractors.nsa_cost_estimate.OpenAI"), \
         patch("workspaces.nsa.config.extractors.nsa_cost_estimate.get_llm_audit_service"), \
         patch("workspaces.nsa.config.extractors.nsa_cost_estimate.AuditedOpenAIClient"), \
         patch("workspaces.nsa.config.extractors.nsa_cost_estimate.load_prompt", return_value={
             "config": {"model": "gpt-4o", "temperature": 0.1, "max_tokens": 4096},
             "messages": [],
         }), \
         patch("workspaces.nsa.config.extractors.nsa_cost_estimate.DecisionLedger"):
        from workspaces.nsa.config.extractors.nsa_cost_estimate import NsaCostEstimateExtractor
        return NsaCostEstimateExtractor(spec=spec)


def _labor_item(price=1.0, qty=None, desc="Labor op"):
    """Shorthand for a labor line-item dict."""
    item = {"item_type": "labor", "total_price": price, "description": desc}
    if qty is not None:
        item["quantity"] = qty
    return item


def _parts_item(price=50.0, desc="Screw M8"):
    return {"item_type": "parts", "total_price": price, "description": desc}


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------

class TestDetection:
    """Verify that the placeholder-detection heuristic fires correctly."""

    def setup_method(self):
        self.ext = _make_extractor()

    def test_placeholder_pattern_detected(self):
        items = [_labor_item(1.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {"labor_total": 759.80}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is True

    def test_not_triggered_on_real_prices(self):
        items = [
            _labor_item(400.0, qty=5),
            _labor_item(359.80, qty=3),
        ]
        summary = {"labor_total": 759.80}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False

    def test_not_triggered_on_mixed_prices(self):
        """One real price + one placeholder → not all in {0,1}."""
        items = [_labor_item(250.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {"labor_total": 759.80}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False

    def test_not_triggered_without_labor_total(self):
        items = [_labor_item(1.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False

    def test_not_triggered_with_zero_labor_total(self):
        items = [_labor_item(1.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {"labor_total": 0}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False

    def test_not_triggered_on_single_item(self):
        items = [_labor_item(1.0, qty=5)]
        summary = {"labor_total": 759.80}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False

    def test_not_triggered_when_sum_exceeds_15_percent(self):
        """If placeholder sum >= 15% of labor_total, skip."""
        # 10 items × 1.0 = 10.0;  labor_total = 50.0  → 20% → skip
        items = [_labor_item(1.0, qty=1) for _ in range(10)]
        summary = {"labor_total": 50.0}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is False


# ---------------------------------------------------------------------------
# Redistribution tests
# ---------------------------------------------------------------------------

class TestRedistribution:
    """Verify price redistribution logic."""

    def setup_method(self):
        self.ext = _make_extractor()

    def test_proportional_to_quantity(self):
        items = [_labor_item(1.0, qty=6), _labor_item(1.0, qty=4)]
        summary = {"labor_total": 100.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert items[0]["total_price"] == 60.0
        assert items[1]["total_price"] == 40.0

    def test_equal_split_fallback(self):
        """When quantities are missing, split equally."""
        items = [_labor_item(1.0), _labor_item(1.0)]
        summary = {"labor_total": 100.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert items[0]["total_price"] == 50.0
        assert items[1]["total_price"] == 50.0

    def test_equal_split_when_quantities_zero(self):
        items = [_labor_item(1.0, qty=0), _labor_item(1.0, qty=0)]
        summary = {"labor_total": 100.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert items[0]["total_price"] == 50.0
        assert items[1]["total_price"] == 50.0

    def test_rounding_correction(self):
        """Three equal items for 100 → 33.33 + 33.33 + 33.34."""
        items = [_labor_item(1.0, qty=1) for _ in range(3)]
        summary = {"labor_total": 100.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        total = sum(i["total_price"] for i in items)
        assert total == pytest.approx(100.0, abs=0.001)
        # Last item absorbs rounding
        assert items[2]["total_price"] == pytest.approx(33.34, abs=0.01)

    def test_preserves_zero_price_items(self):
        """Items with total_price == 0.0 are left at 0."""
        items = [
            _labor_item(0.0, qty=0),
            _labor_item(1.0, qty=5),
            _labor_item(1.0, qty=3),
        ]
        summary = {"labor_total": 200.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert items[0]["total_price"] == 0.0
        assert "_price_source" not in items[0]
        assert items[1]["total_price"] + items[2]["total_price"] == pytest.approx(200.0, abs=0.01)

    def test_preserves_parts_items(self):
        """Parts items are completely untouched."""
        parts = _parts_item(55.0)
        items = [parts, _labor_item(1.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {"labor_total": 200.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert parts["total_price"] == 55.0
        assert "_price_source" not in parts

    def test_adds_price_source_marker(self):
        items = [_labor_item(1.0, qty=5), _labor_item(1.0, qty=3)]
        summary = {"labor_total": 100.0}
        self.ext._fix_labor_placeholder_prices(items, summary)
        assert items[0]["_price_source"] == "redistributed_from_labor_total"
        assert items[1]["_price_source"] == "redistributed_from_labor_total"

    def test_return_dict_when_corrected(self):
        items = [_labor_item(1.0, qty=6), _labor_item(1.0, qty=4)]
        summary = {"labor_total": 100.0}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is True
        assert result["original_sum"] == 2.0
        assert result["corrected_sum"] == pytest.approx(100.0)
        assert result["items_corrected"] == 2

    def test_string_labor_total_handled(self):
        """labor_total may come as a string from LLM output."""
        items = [_labor_item(1.0, qty=5), _labor_item(1.0, qty=5)]
        summary = {"labor_total": "200.00"}
        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is True
        assert items[0]["total_price"] == 100.0
        assert items[1]["total_price"] == 100.0


# ---------------------------------------------------------------------------
# Integration with _merge_page_results
# ---------------------------------------------------------------------------

class TestMergeIntegration:
    """Verify that _merge_page_results calls the fix and records metadata."""

    def setup_method(self):
        self.ext = _make_extractor()

    def _page(self, page_number, items, summary=None, header=None):
        result = {"page_number": page_number, "line_items": items}
        if summary is not None:
            result["summary"] = summary
        if header is not None:
            result["header"] = header
        return result

    def test_merge_applies_correction(self):
        page1 = self._page(1, [
            _labor_item(1.0, qty=6, desc="Stossfaenger aus/einbauen"),
            _labor_item(1.0, qty=4, desc="Kotfluegel richten"),
        ], header={"document_number": "KV-123"})
        page2 = self._page(2, [
            _parts_item(50.0),
        ], summary={
            "labor_total": 200.0,
            "parts_total": 50.0,
            "subtotal_before_vat": 250.0,
        })

        merged = self.ext._merge_page_results([page1, page2], total_pages=2)
        labor_items = [i for i in merged["line_items"] if i["item_type"] == "labor"]
        assert labor_items[0]["total_price"] == pytest.approx(120.0)
        assert labor_items[1]["total_price"] == pytest.approx(80.0)
        assert merged["_meta"]["labor_price_correction"]["corrected"] is True

    def test_merge_no_correction_when_not_needed(self):
        page1 = self._page(1, [
            {"item_type": "labor", "total_price": 400.0, "quantity": 6, "description": "Op A"},
            {"item_type": "labor", "total_price": 360.0, "quantity": 4, "description": "Op B"},
        ])
        page2 = self._page(2, [], summary={
            "labor_total": 760.0,
            "parts_total": 0,
            "subtotal_before_vat": 760.0,
        })

        merged = self.ext._merge_page_results([page1, page2], total_pages=2)
        assert merged["_meta"]["labor_price_correction"]["corrected"] is False

    def test_meta_records_correction_details(self):
        page = self._page(1, [
            _labor_item(1.0, qty=3, desc="Spachteln"),
            _labor_item(1.0, qty=7, desc="Lackieren"),
        ], summary={"labor_total": 500.0, "subtotal_before_vat": 500.0})

        merged = self.ext._merge_page_results([page], total_pages=1)
        fix = merged["_meta"]["labor_price_correction"]
        assert fix["corrected"] is True
        assert fix["original_sum"] == 2.0
        assert fix["corrected_sum"] == pytest.approx(500.0)
        assert fix["items_corrected"] == 2


# ---------------------------------------------------------------------------
# Regression test — claim 64984
# ---------------------------------------------------------------------------

class TestClaim64984Regression:
    """Exact data from claim 64984 to verify correct redistribution."""

    def setup_method(self):
        self.ext = _make_extractor()

    def test_claim_64984_redistribution(self):
        """Claim 64984: 6 labor items each with price=1, labor_total=759.80."""
        items = [
            _labor_item(1.0, qty=3.0),   # Stossfänger v. aus/einbauen
            _labor_item(1.0, qty=2.5),   # Kotflügel v.l. richten
            _labor_item(1.0, qty=1.0),   # Scheinwerfer l. aus/einbauen
            _labor_item(1.0, qty=0.5),   # Nebelscheinwerfer l. aus/einbauen
            _labor_item(1.0, qty=2.0),   # Spachteln/Schleifen/Füller
            _labor_item(1.0, qty=4.0),   # Lackieren: Stossfänger v., Kotflügel v.l.
        ]
        summary = {"labor_total": 759.80}

        result = self.ext._fix_labor_placeholder_prices(items, summary)
        assert result["corrected"] is True

        total_qty = 3.0 + 2.5 + 1.0 + 0.5 + 2.0 + 4.0  # 13.0
        assert total_qty == 13.0

        # Verify proportional distribution
        expected = [
            round((3.0 / 13.0) * 759.80, 2),   # 175.34
            round((2.5 / 13.0) * 759.80, 2),   # 146.12
            round((1.0 / 13.0) * 759.80, 2),   # 58.45
            round((0.5 / 13.0) * 759.80, 2),   # 29.22
            round((2.0 / 13.0) * 759.80, 2),   # 116.89
            round((4.0 / 13.0) * 759.80, 2),   # 233.78
        ]
        # Last item gets rounding correction
        rounding_diff = round(759.80 - sum(expected), 2)
        expected[-1] = round(expected[-1] + rounding_diff, 2)

        for i, exp in enumerate(expected):
            assert items[i]["total_price"] == pytest.approx(exp, abs=0.01), (
                f"Item {i}: expected {exp}, got {items[i]['total_price']}"
            )

        # Sum must match labor_total exactly
        actual_sum = sum(i["total_price"] for i in items)
        assert actual_sum == pytest.approx(759.80, abs=0.01)
        assert result["corrected_sum"] == pytest.approx(759.80, abs=0.01)
