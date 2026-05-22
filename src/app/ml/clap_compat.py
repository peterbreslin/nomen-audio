"""Patch msclap's CLAPWrapper to use librosa instead of torchaudio for audio loading.

torchaudio >= 2.9 requires torchcodec + FFmpeg shared libs on the system PATH.
On Windows this is a heavy requirement (users must install FFmpeg "full-shared").
Since we only process WAV files, librosa + soundfile handles everything we need
with zero system-level dependencies.

Usage:
    from msclap import CLAP
    from app.ml.clap_compat import patch_clap_audio

    model = CLAP(version='2023', use_cuda=False)
    patch_clap_audio(model)
    # Now model.get_audio_embeddings() uses librosa internally
"""

import types

import librosa
import numpy as np
import torch


def _librosa_read_audio(
    self: object, audio_path: str, resample: bool = True
) -> tuple[torch.Tensor, int]:
    """Drop-in replacement for CLAPWrapper.read_audio using librosa.

    Matches the original contract:
      - Returns (audio_time_series: Tensor, sample_rate: int)
      - If resample=True, resamples to self.args.sampling_rate
      - Always returns self.args.sampling_rate as the rate (matches original)
    """
    target_sr = self.args.sampling_rate if resample else None  # type: ignore[attr-defined]
    audio_np, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    audio_tensor = torch.from_numpy(audio_np)
    return audio_tensor, self.args.sampling_rate if resample else sr  # type: ignore[attr-defined]


def patch_clap_audio(clap_model: object) -> None:
    """Monkey-patch a CLAP model instance to bypass torchaudio.

    Replaces ``read_audio`` so the entire audio loading call chain
    (get_audio_embeddings → preprocess_audio → load_audio_into_tensor →
    read_audio) uses librosa instead of torchaudio.
    """
    clap_model.read_audio = types.MethodType(_librosa_read_audio, clap_model)  # type: ignore[attr-defined]


def _center_load_audio_into_tensor(
    self: object, audio_path: str, audio_duration: int, resample: bool = False
) -> torch.FloatTensor:
    """Deterministic replacement for CLAPWrapper.load_audio_into_tensor.

    The stock msclap version randomly samples a ``audio_duration``-second window
    when the clip is longer than the target. For reproducible evaluation runs
    we instead take the centre window. The pad-shorter branch is unchanged
    (msclap repeats the clip; no randomness there).
    """
    audio_time_series, sample_rate = self.read_audio(audio_path, resample=resample)  # type: ignore[attr-defined]
    audio_time_series = audio_time_series.reshape(-1)
    target_len = audio_duration * sample_rate

    if target_len >= audio_time_series.shape[0]:
        repeat_factor = int(np.ceil(target_len / audio_time_series.shape[0]))
        audio_time_series = audio_time_series.repeat(repeat_factor)
        audio_time_series = audio_time_series[0:target_len]
    else:
        start_index = (audio_time_series.shape[0] - target_len) // 2
        audio_time_series = audio_time_series[start_index : start_index + target_len]
    return torch.FloatTensor(audio_time_series)


def patch_clap_deterministic_segment(clap_model: object) -> None:
    """Swap CLAP's random segment pick for a centre-window pick.

    Use this for evaluation runs so two runs of the same pipeline against the
    same audio produce identical embeddings. Production stays on the stock
    random pick (it acts as a cheap form of test-time augmentation).
    """
    clap_model.load_audio_into_tensor = types.MethodType(  # type: ignore[attr-defined]
        _center_load_audio_into_tensor, clap_model
    )
