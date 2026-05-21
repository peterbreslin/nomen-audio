"""LLM provider protocol for the CLAP -> LLM rerank step.

A provider is responsible for: rendering the locked prompt against a single
file's metadata and CLAP candidates, calling its backing model, validating
that the returned CatID is in the candidate list, retrying once on
hallucinated outputs, and falling back to CLAP top-1 if the model still
refuses to comply.

The protocol does not pick K — the caller is expected to pass the top
``load_prompt().candidates_n`` candidates already trimmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import ClassificationMatch


@dataclass(frozen=True)
class PickResult:
    """Outcome of one ``LLMProvider.pick`` call.

    ``cat_id`` is the final CatID to use downstream. It may be the model's
    first-pass choice, its second-pass choice after a corrective retry, or
    CLAP's top-1 (when both passes returned invalid CatIDs).
    """

    cat_id: str
    retried: bool
    fallback_to_clap_top1: bool
    latency_ms: int


class LLMProvider(Protocol):
    """Anything that can pick one CatID from a list of CLAP candidates."""

    @property
    def model_version(self) -> str:
        """Stable identifier for the model + quant + backend.

        Used as part of the analysis-cache key alongside the prompt version
        so that swapping models invalidates cached LLM picks.
        """
        ...

    def pick(
        self,
        *,
        filename: str,
        metadata: dict[str, str],
        candidates: list[ClassificationMatch],
    ) -> PickResult:
        """Pick the best CatID from ``candidates`` for the given file.

        ``candidates`` must be non-empty and already trimmed to the prompt's
        configured N. The first element is treated as CLAP's top-1 and used
        as the fallback CatID when the model fails validation twice.
        """
        ...
