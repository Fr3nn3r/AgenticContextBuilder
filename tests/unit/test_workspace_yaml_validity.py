"""Smoke tests: validate all workspace YAML files parse correctly.

These tests catch YAML syntax errors (like unquoted regex brackets)
that would silently break config loading at runtime. They also verify
that regex patterns embedded in config files actually compile.

Skipped automatically when workspace config files are not present
(e.g., CI environments where customer config is not checked in).
"""

import re
from pathlib import Path
from typing import List

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACES_DIR = _REPO_ROOT / "workspaces"


def _all_workspace_yaml_files() -> List[Path]:
    """Collect all .yaml/.yml files under workspaces/*/config/."""
    if not _WORKSPACES_DIR.exists():
        return []
    files = []
    for ws_dir in _WORKSPACES_DIR.iterdir():
        config_dir = ws_dir / "config"
        if config_dir.is_dir():
            files.extend(config_dir.rglob("*.yaml"))
            files.extend(config_dir.rglob("*.yml"))
    return sorted(files)


_YAML_FILES = _all_workspace_yaml_files()


@pytest.mark.skipif(not _YAML_FILES, reason="No workspace config YAML files found")
class TestWorkspaceYamlValidity:
    """Every workspace YAML file must parse without errors."""

    @pytest.mark.parametrize(
        "yaml_path",
        _YAML_FILES,
        ids=[str(p.relative_to(_REPO_ROOT)) for p in _YAML_FILES],
    )
    def test_yaml_parses(self, yaml_path: Path):
        """YAML file must load without syntax errors."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None, f"YAML file is empty: {yaml_path}"


# ── Regex pattern validation ────────────────────────────────────────────


def _collect_regex_patterns_from_keyword_mappings(data: dict) -> List[str]:
    """Extract all keyword strings from a keyword mappings YAML."""
    patterns = []
    for entry in data.get("mappings", []):
        for kw in entry.get("keywords", []):
            if any(c in str(kw) for c in r"[]\.*+?(){}|^$"):
                patterns.append(str(kw))
    return patterns


def _collect_regex_patterns_from_rule_config(data: dict) -> List[str]:
    """Extract regex patterns from a coverage rule config YAML."""
    patterns = []
    rules = data.get("rules", {})
    for key in (
        "exclusion_patterns",
        "consumable_patterns",
        "non_covered_labor_patterns",
        "component_override_patterns",
        "generic_description_patterns",
        "fastener_patterns",
        "seal_gasket_standalone_patterns",
    ):
        for p in rules.get(key, []):
            patterns.append(str(p))
    return patterns


def _find_files(glob_pattern: str) -> List[Path]:
    """Find workspace config files matching a glob."""
    if not _WORKSPACES_DIR.exists():
        return []
    return sorted(_WORKSPACES_DIR.glob(glob_pattern))


_KEYWORD_FILES = _find_files("*/config/coverage/*_keyword_mappings.yaml")
_RULE_CONFIG_FILES = _find_files("*/config/coverage/*_coverage_config.yaml")


@pytest.mark.skipif(
    not _KEYWORD_FILES and not _RULE_CONFIG_FILES,
    reason="No workspace coverage config files found",
)
class TestRegexPatternsCompile:
    """All regex patterns in coverage configs must be valid."""

    @pytest.mark.parametrize(
        "yaml_path",
        _KEYWORD_FILES,
        ids=[str(p.relative_to(_REPO_ROOT)) for p in _KEYWORD_FILES],
    )
    def test_keyword_mapping_regexes_compile(self, yaml_path: Path):
        """Every keyword pattern must compile as a valid regex."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        patterns = _collect_regex_patterns_from_keyword_mappings(data)
        for pattern in patterns:
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                pytest.fail(
                    f"Invalid regex in {yaml_path.name}: {pattern!r} -- {e}"
                )

    @pytest.mark.parametrize(
        "yaml_path",
        _RULE_CONFIG_FILES,
        ids=[str(p.relative_to(_REPO_ROOT)) for p in _RULE_CONFIG_FILES],
    )
    def test_rule_config_regexes_compile(self, yaml_path: Path):
        """Every rule engine pattern must compile as a valid regex."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        patterns = _collect_regex_patterns_from_rule_config(data)
        for pattern in patterns:
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                pytest.fail(
                    f"Invalid regex in {yaml_path.name}: {pattern!r} -- {e}"
                )
