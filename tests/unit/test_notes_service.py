"""Tests for claim notes (get/save) in DecisionDossierService."""

import json
from pathlib import Path

import pytest

from context_builder.api.services.decision_dossier import DecisionDossierService


@pytest.fixture()
def svc(tmp_path: Path) -> DecisionDossierService:
    """Create a DecisionDossierService with a temporary claims directory."""
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()
    workspace_path = tmp_path
    return DecisionDossierService(claims_dir, workspace_path)


@pytest.fixture()
def claim_folder(svc: DecisionDossierService) -> Path:
    """Create a claim folder and return its path."""
    folder = svc.claims_dir / "CLM-001"
    folder.mkdir()
    return folder


class TestGetNotes:
    def test_missing_claim_returns_empty(self, svc: DecisionDossierService):
        result = svc.get_notes("NONEXISTENT")
        assert result == {"content": "", "updated_at": None, "updated_by": None}

    def test_no_notes_file_returns_empty(self, svc: DecisionDossierService, claim_folder: Path):
        result = svc.get_notes("CLM-001")
        assert result["content"] == ""
        assert result["updated_at"] is None

    def test_existing_notes_returned(self, svc: DecisionDossierService, claim_folder: Path):
        notes_data = {
            "content": "Test note",
            "updated_at": "2026-02-11T10:00:00+00:00",
            "updated_by": "alice",
        }
        (claim_folder / "notes.json").write_text(json.dumps(notes_data), encoding="utf-8")

        result = svc.get_notes("CLM-001")
        assert result["content"] == "Test note"
        assert result["updated_at"] == "2026-02-11T10:00:00+00:00"
        assert result["updated_by"] == "alice"


class TestSaveNotes:
    def test_create_new(self, svc: DecisionDossierService, claim_folder: Path):
        result = svc.save_notes("CLM-001", "First note", "bob")
        assert result["content"] == "First note"
        assert result["updated_by"] == "bob"
        assert result["updated_at"] is not None

        # Verify file on disk
        saved = json.loads((claim_folder / "notes.json").read_text(encoding="utf-8"))
        assert saved["content"] == "First note"

    def test_overwrite_existing(self, svc: DecisionDossierService, claim_folder: Path):
        svc.save_notes("CLM-001", "Version 1", "alice")
        result = svc.save_notes("CLM-001", "Version 2", "bob")
        assert result["content"] == "Version 2"
        assert result["updated_by"] == "bob"

    def test_bad_claim_id_raises(self, svc: DecisionDossierService):
        with pytest.raises(ValueError, match="Claim folder not found"):
            svc.save_notes("NONEXISTENT", "note", "admin")

    def test_empty_content(self, svc: DecisionDossierService, claim_folder: Path):
        result = svc.save_notes("CLM-001", "", "admin")
        assert result["content"] == ""
