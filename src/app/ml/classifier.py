"""CLAP classifier — zero-shot audio classification against UCS labels."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.models import ClassificationMatch

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


def _softmax(logits: "np.ndarray") -> "np.ndarray":
    """Numerically stable softmax: logits -> [0, 1] probabilities."""
    import numpy as np

    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / exp.sum()


class CLAPClassifier:
    """Wraps MS-CLAP 2023 for zero-shot classification of sound effects."""

    def __init__(self) -> None:
        self._model = None
        self._text_embeddings: np.ndarray | None = None
        self._text_meta: list[dict] | None = None

    def load_model(self) -> None:
        """Load CLAP 2023 model (CPU only) and apply librosa patch."""
        from msclap import CLAP

        from app.ml.clap_compat import patch_clap_audio

        self._model = CLAP(version="2023", use_cuda=False)
        patch_clap_audio(self._model)
        logger.info("CLAP 2023 model loaded")

    def precompute_embeddings(self, phrases: list[str], meta: list[dict]) -> None:
        """Compute text embeddings for all label phrases."""
        self._text_embeddings = self._model.get_text_embeddings(phrases)
        self._text_meta = meta
        logger.info("Precomputed %d text embeddings", len(phrases))

    def save_embeddings(self, path: str, label_hash: str) -> None:
        """Save text embeddings + metadata to .npz file."""
        import numpy as np

        meta_json = json.dumps(self._text_meta)
        np.savez(
            path,
            embeddings=self._text_embeddings,
            meta_json=np.array([meta_json]),
            label_hash=np.array([label_hash]),
        )

    def load_embeddings(self, path: str, expected_hash: str) -> bool:
        """Load cached embeddings. Returns False if hash mismatch or missing."""
        import numpy as np
        import torch

        try:
            data = np.load(path, allow_pickle=False)
            stored_hash = str(data["label_hash"][0])
            if stored_hash != expected_hash:
                logger.info("Embedding cache hash mismatch, will recompute")
                return False
            # Convert back to torch tensor — compute_similarity requires it
            self._text_embeddings = torch.from_numpy(data["embeddings"])
            self._text_meta = json.loads(str(data["meta_json"][0]))
            logger.info("Loaded %d cached text embeddings", len(self._text_meta))
            return True
        except (FileNotFoundError, KeyError):
            return False

    def classify(self, audio_path: str, top_n: int = 5) -> list[ClassificationMatch]:
        """Classify an audio file against precomputed text embeddings."""
        import numpy as np

        audio_emb = self._model.get_audio_embeddings([audio_path])
        similarity = self._model.compute_similarity(audio_emb, self._text_embeddings)
        squeezed = similarity.squeeze(0)
        if hasattr(squeezed, "detach"):
            squeezed = squeezed.detach()
        logits = (
            squeezed.numpy() if hasattr(squeezed, "numpy") else np.asarray(squeezed)
        )

        # Group by CatID, take max logit per CatID
        catid_best: dict[str, tuple[float, dict]] = {}
        for i, meta in enumerate(self._text_meta):
            cid = meta["cat_id"]
            if cid not in catid_best or logits[i] > catid_best[cid][0]:
                catid_best[cid] = (float(logits[i]), meta)

        # Sort by raw logit descending, take top_n, softmax only over those
        sorted_items = sorted(catid_best.items(), key=lambda x: x[1][0], reverse=True)
        top_items = sorted_items[:top_n]
        top_logits = np.array([score for _, (score, _) in top_items])
        top_probs = _softmax(top_logits)

        return [
            ClassificationMatch(
                cat_id=cid,
                category=meta["category"],
                subcategory=meta["subcategory"],
                category_full=f"{meta['category']}-{meta['subcategory']}",
                confidence=round(float(top_probs[i]), 6),
            )
            for i, (cid, (_, meta)) in enumerate(top_items)
        ]

    def is_ready(self) -> bool:
        return self._model is not None and self._text_embeddings is not None
