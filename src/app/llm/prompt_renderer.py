"""Render the locked LLM rerank prompt for production.

Loads ``prompts/prompt.yaml`` once and produces (system, user) prompt strings
for a single WAV given filename, descriptive metadata, and the CLAP top-N
candidates. Production-only: supports the ``clap_top_n`` / ``raw_ucs_block``
path that the locked prompt uses. For dev experiments with ``full_taxonomy``
or ``full_acoustic`` variants, see ``dev/ollama_tests/prompt_builders.py``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import yaml

from app.models import ClassificationMatch
from app.ucs.engine import get_catid_info

_PROMPT_PACKAGE = "app.llm.prompts"
_PROMPT_FILENAME = "prompt.yaml"


@dataclass(frozen=True)
class PromptConfig:
    """Parsed prompt definition from prompt.yaml."""

    name: str
    version: str
    system: str
    user_template: str
    candidate_template: str
    candidates_n: int


@lru_cache(maxsize=1)
def load_prompt() -> PromptConfig:
    """Read and parse the production prompt YAML once per process.

    Raises ``ValueError`` if the YAML declares a candidates source/format
    that the production renderer does not support.
    """
    raw = resources.files(_PROMPT_PACKAGE).joinpath(_PROMPT_FILENAME).read_text("utf-8")
    data = yaml.safe_load(raw)
    cands = data["candidates"]
    source = cands["source"]
    fmt = cands["format"]
    if source != "clap_top_n" or fmt != "raw_ucs_block":
        raise ValueError(
            f"prompt.yaml has unsupported source/format: {source}/{fmt} "
            "(production renderer requires clap_top_n / raw_ucs_block)"
        )
    return PromptConfig(
        name=data["name"],
        version=hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12],
        system=data["system"].strip(),
        user_template=data["user_template"],
        candidate_template=data["candidate_template"],
        candidates_n=cands["n"],
    )


def render_prompt(
    config: PromptConfig,
    *,
    filename: str,
    metadata: dict[str, str],
    candidates: list[ClassificationMatch],
) -> tuple[str, str]:
    """Build (system, user) prompts for one file.

    ``candidates`` should already be trimmed to ``config.candidates_n`` by
    the caller (the renderer does not slice it).
    """
    file_info = _render_file_info(filename, metadata)
    candidates_block = _render_candidates(config, candidates)
    user = config.user_template.format(
        file_info=file_info,
        n_candidates=len(candidates),
        candidates=candidates_block,
    )
    return config.system, user


def _render_file_info(filename: str, metadata: dict[str, str]) -> str:
    """Render the file-info block: filename, then non-empty metadata fields."""
    lines = [f"  filename: {filename}"]
    for key, value in metadata.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _render_candidates(
    config: PromptConfig,
    candidates: list[ClassificationMatch],
) -> str:
    """Render one ``- {cat_id} [{cat}/{sub}] ...`` block per candidate."""
    lines: list[str] = []
    for match in candidates:
        info = get_catid_info(match.cat_id)
        explanation = info.explanation if info else "(not in UCS spreadsheet)"
        synonyms = ", ".join(info.synonyms) if info else ""
        lines.append(
            config.candidate_template.format(
                cat_id=match.cat_id,
                category=match.category,
                subcategory=match.subcategory,
                explanation=explanation,
                synonyms=synonyms,
            )
        )
    return "\n".join(lines).rstrip()
