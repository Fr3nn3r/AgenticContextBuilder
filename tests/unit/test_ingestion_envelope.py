"""Tests for ingestion result envelope."""

from pathlib import Path

from context_builder.ingestion import DataIngestion


class FakeIngestion(DataIngestion):
    def _process_implementation(self, filepath: Path) -> dict:
        return {"content": "ok", "file_path": str(filepath)}


def test_ingestion_process_returns_raw_by_default(tmp_path: Path) -> None:
    fake = FakeIngestion()
    path = tmp_path / "sample.png"
    path.write_text("x", encoding="utf-8")

    result = fake.process(path)

    assert "data" not in result
    assert result["content"] == "ok"


def test_ingestion_process_returns_envelope(tmp_path: Path) -> None:
    fake = FakeIngestion()
    path = tmp_path / "sample.png"
    path.write_text("x", encoding="utf-8")

    result = fake.process(path, envelope=True)

    assert result["data"]["content"] == "ok"
    assert result["warnings"] == []
    assert result["errors"] == []
