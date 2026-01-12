"""Unit tests for pipeline runner and result writer."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
from uuid import uuid4
from typing import Optional

import pytest

from context_builder.pipeline.stages import PipelineRunner
from context_builder.pipeline.writer import ResultWriter


@dataclass
class DummyContext:
    """Minimal context for runner tests."""

    status: str = "success"
    steps: list[str] = field(default_factory=list)


class AppendStage:
    """Stage that appends its name and optionally sets a status."""

    def __init__(self, name: str, status: Optional[str] = None) -> None:
        self.name = name
        self._status = status

    def run(self, context: DummyContext) -> DummyContext:
        context.steps.append(self.name)
        if self._status:
            context.status = self._status
        return context


@pytest.fixture
def tmp_path() -> Path:
    base = Path.cwd() / "output" / "pytest-tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"tmp-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_pipeline_runner_runs_in_order():
    ctx = DummyContext()
    runner = PipelineRunner([AppendStage("one"), AppendStage("two"), AppendStage("three")])
    result = runner.run(ctx)
    assert result.steps == ["one", "two", "three"]


def test_pipeline_runner_stops_on_skip():
    ctx = DummyContext()
    runner = PipelineRunner([AppendStage("one", status="skipped"), AppendStage("two")])
    result = runner.run(ctx)
    assert result.steps == ["one"]


def test_result_writer_writes_json_atomic(tmp_path):
    writer = ResultWriter()
    path = tmp_path / "data.json"
    writer.write_json_atomic(path, {"ok": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}


def test_result_writer_copy_and_text(tmp_path):
    writer = ResultWriter()
    src = tmp_path / "source.txt"
    src.write_text("hello", encoding="utf-8")
    dest = tmp_path / "nested" / "dest.txt"
    writer.copy_file(src, dest)
    assert dest.read_text(encoding="utf-8") == "hello"

    text_path = tmp_path / "nested2" / "out.txt"
    writer.write_text(text_path, "world")
    assert text_path.read_text(encoding="utf-8") == "world"
