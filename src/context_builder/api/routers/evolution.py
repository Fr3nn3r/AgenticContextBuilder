"""Evolution router - endpoints for pipeline evolution tracking."""

from fastapi import APIRouter

from context_builder.api.dependencies import get_evolution_service

router = APIRouter(tags=["evolution"])


@router.get("/api/evolution/timeline")
def get_evolution_timeline():
    """Get pipeline evolution timeline with scope and accuracy metrics.

    Returns timeline data showing how the pipeline's scope (doc types, fields)
    and accuracy have evolved across version bundles over time.
    """
    return get_evolution_service().get_evolution_timeline()


@router.get("/api/evolution/doc-types")
def get_evolution_doc_types():
    """Get doc type evolution matrix.

    Returns per-doc-type evolution data showing field counts and accuracy
    across all spec versions.
    """
    return get_evolution_service().get_doc_type_matrix()
