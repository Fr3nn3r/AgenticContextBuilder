"""FastAPI backend for Extraction QA Console."""

from context_builder.api.main import app
from context_builder.api.dependencies import set_data_dir

__all__ = ["app", "set_data_dir"]
