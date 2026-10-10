from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.ai.annotations import default_annotation_paths
from pipeline.ai.config import ExtractionSettings


@dataclass(frozen=True)
class PromptBundle:
    system_instruction: str
    user_prompt: str
    fingerprint: str


@dataclass(frozen=True)
class BatchPromptBundle:
    system_instruction: str
    user_prompt: str
    request_fingerprint: str
    document_fingerprints: dict[str, str]


def _load_entities(path: Path) -> dict[str, list[dict[str, str]]]:
    entities: dict[str, list[dict[str, str]]] = {"jobs": [], "subcontractors": []}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            entity = {
                "canonical_id": row["canonical_id"],
                "observed_aliases": row["observed_aliases"],
            }
            if row["entity_type"] == "job":
                entity["division"] = row["division"]
                entity["contract_type"] = row["contract_type"]
                entities["jobs"].append(entity)
            elif row["entity_type"] == "subcontractor":
                entities["subcontractors"].append(entity)
    return entities


def _prompt_parts(settings: ExtractionSettings) -> tuple[str, dict[str, list[dict[str, str]]]]:
    prompt_path = Path(__file__).resolve().parent / "prompts" / f"{settings.prompt_version}.txt"
    system_instruction = prompt_path.read_text(encoding="utf-8")
    entities = _load_entities(default_annotation_paths(settings.project).entities)
    return system_instruction, entities


def _single_user_prompt(
    document: dict[str, Any],
    entities: dict[str, list[dict[str, str]]],
) -> str:
    payload = {
        "document": {
            "doc_id": document["doc_id"],
            "doc_type": document["doc_type"],
            "text": document["text"],
        },
        "allowed_entities": entities,
    }
    return (
        "Extract the document below using the supplied canonical entity reference. "
        "Return only the structured response required by the response schema.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _fingerprint(
    settings: ExtractionSettings,
    system_instruction: str,
    user_prompt: str,
) -> str:
    fingerprint_input = json.dumps(
        {
            "provider": settings.provider,
            "model": settings.model,
            "prompt_version": settings.prompt_version,
            "schema_version": settings.schema_version,
            "system_instruction": system_instruction,
            "user_prompt": user_prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()


def build_prompt(
    settings: ExtractionSettings,
    document: dict[str, Any],
) -> PromptBundle:
    system_instruction, entities = _prompt_parts(settings)
    user_prompt = _single_user_prompt(document, entities)
    return PromptBundle(
        system_instruction,
        user_prompt,
        _fingerprint(settings, system_instruction, user_prompt),
    )


def build_batch_prompt(
    settings: ExtractionSettings,
    documents: list[dict[str, Any]],
) -> BatchPromptBundle:
    if not documents:
        raise ValueError("cannot build an empty extraction batch")

    base_instruction, entities = _prompt_parts(settings)
    system_instruction = (
        base_instruction
        + "\n\nBatch execution rules:\n"
        + "- Apply all rules independently to every input document.\n"
        + "- Return exactly one result for every input document, in the same order.\n"
        + "- Never mix evidence or facts between documents.\n"
    )
    payload = {
        "documents": [
            {
                "doc_id": document["doc_id"],
                "doc_type": document["doc_type"],
                "text": document["text"],
            }
            for document in documents
        ],
        "allowed_entities": entities,
    }
    user_prompt = (
        "Extract every document below using the supplied canonical entity reference. "
        "Return only the structured batch response required by the response schema.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    document_fingerprints = {
        document["doc_id"]: _fingerprint(
            settings,
            base_instruction,
            _single_user_prompt(document, entities),
        )
        for document in documents
    }
    return BatchPromptBundle(
        system_instruction=system_instruction,
        user_prompt=user_prompt,
        request_fingerprint=_fingerprint(settings, system_instruction, user_prompt),
        document_fingerprints=document_fingerprints,
    )
