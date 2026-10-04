"""Source-faithful ingestion for the supplied static extracts."""

from pipeline.ingest.runner import IngestionError, SourceLoadResult, ingest_all

__all__ = ["IngestionError", "SourceLoadResult", "ingest_all"]
