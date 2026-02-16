"""CLAP captioner — audio caption generation via clapcap model."""

import logging

logger = logging.getLogger(__name__)


class CLAPCaptioner:
    """Wraps MS-CLAP clapcap model for audio caption generation."""

    def __init__(self) -> None:
        self._model = None

    def load_model(self) -> None:
        """Load clapcap model (CPU only) and apply librosa patch."""
        from msclap import CLAP

        from app.ml.clap_compat import patch_clap_audio

        self._model = CLAP(version="clapcap", use_cuda=False)
        patch_clap_audio(self._model)
        logger.info("CLAPCaptioner model loaded")

    def caption(self, audio_path: str) -> str:
        """Generate a caption for an audio file."""
        raw = self._model.generate_caption([audio_path])[0]
        return _cleanup_caption(raw)

    def is_loaded(self) -> bool:
        return self._model is not None


def _cleanup_caption(text: str) -> str:
    """Clean up raw caption text: strip, capitalize, punctuate, truncate."""
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    if len(text) > 256:
        text = text[:253] + "..."
    return text
