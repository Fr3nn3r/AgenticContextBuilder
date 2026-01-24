"""
Document field extractors.

Importing this module registers all extractors with the ExtractorFactory.
Custom extractors are loaded dynamically from workspace config/extractors/.
"""

import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Import to trigger auto-registration of generic extractor for all doc types
from context_builder.extraction.extractors.generic import GenericFieldExtractor

from context_builder.extraction.base import ExtractorFactory

# Customer-specific extractors (NSA, etc.) are loaded dynamically from
# workspace config/extractors/ folder. See _load_workspace_extractors() below.


def _load_workspace_extractors():
    """Dynamically load extractors from workspace config/extractors/ folder.

    This allows customer-specific extractors to be stored in the workspace
    (which can be a separate git repo) rather than in the main codebase.

    The workspace extractors/__init__.py should define a register_extractors()
    function that registers custom extractors with the ExtractorFactory.
    """
    from context_builder.storage.workspace_paths import get_workspace_config_dir

    try:
        config_dir = get_workspace_config_dir()
    except Exception as e:
        logger.debug(f"Could not get workspace config dir: {e}")
        return

    if config_dir is None:
        return

    extractors_dir = Path(config_dir) / "extractors"
    if not extractors_dir.exists():
        logger.debug(f"No workspace extractors dir at {extractors_dir}")
        return

    init_file = extractors_dir / "__init__.py"
    if not init_file.exists():
        logger.debug(f"No __init__.py in workspace extractors dir")
        return

    try:
        # Load the workspace extractors module
        spec = importlib.util.spec_from_file_location(
            "workspace_extractors",
            init_file,
            submodule_search_locations=[str(extractors_dir)],
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not create module spec for {init_file}")
            return

        module = importlib.util.module_from_spec(spec)

        # Add the extractors directory to the module's path for relative imports
        import sys
        sys.modules["workspace_extractors"] = module

        spec.loader.exec_module(module)

        # Call register_extractors() if it exists
        if hasattr(module, "register_extractors"):
            module.register_extractors()
            logger.info(f"Loaded workspace extractors from {extractors_dir}")
        else:
            logger.warning(f"Workspace extractors module has no register_extractors() function")

    except Exception as e:
        logger.warning(f"Failed to load workspace extractors: {e}")


# Load workspace extractors (after generic extractor is registered)
_load_workspace_extractors()


__all__ = ["GenericFieldExtractor"]
