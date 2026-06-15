"""Predict an electronic sub-genre from the waveform using the Discogs-MAEST model.

Runs the MAEST ONNX model on the CPU (onnxruntime) to label audio with one of 400
Discogs styles. onnxruntime and the ~344 MB model are optional and downloaded on
first use; any failure returns None so the resolver falls back gracefully.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import platformdirs

MODEL_NAME = "discogs-maest-10s-pw-1"
_BASE_URL = "https://essentia.upf.edu/models/feature-extractors/maest"
MODEL_URL = f"{_BASE_URL}/{MODEL_NAME}.onnx"
METADATA_URL = f"{_BASE_URL}/{MODEL_NAME}.json"

# Front-end parameters copied from the MAEST HF feature extractor; must match
# exactly or the model receives out-of-distribution input.
_SAMPLE_RATE = 16000
_FRAME = 512
_HOP = 256
_MEL_BANDS = 96
_PATCH_FRAMES = 626  # the model's fixed time dimension (~10 s at 16 kHz / hop 256)
_MAX_PATCHES = 6  # cap per track so a long mix doesn't run dozens of inferences
_MIN_CONFIDENCE = 0.10  # below this the model is guessing — defer to the fallback
# Discogs20 training-set normalization constants (from the MAEST preprocessor).
_NORM_MEAN = 2.06755686098554
_NORM_STD = 1.268292820667291


def model_dir() -> Path:
    return Path(platformdirs.user_cache_dir("cratemind")) / "models"


def model_path() -> Path:
    return model_dir() / f"{MODEL_NAME}.onnx"


def metadata_path() -> Path:
    return model_dir() / f"{MODEL_NAME}.json"


def download_model() -> Path:  # pragma: no cover - network/IO, run on demand
    """Download the MAEST ONNX model + metadata into the cache (once). ~344 MB."""
    import httpx

    model_dir().mkdir(parents=True, exist_ok=True)
    for url, dest in ((METADATA_URL, metadata_path()), (MODEL_URL, model_path())):
        if dest.exists():
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        with httpx.stream("GET", url, timeout=None, follow_redirects=True) as response:
            _ = response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1 << 20):
                    _ = handle.write(chunk)
        _ = tmp.replace(dest)
    _labels.cache_clear()  # drop any session/labels primed from an older model
    _session.cache_clear()
    return model_path()


def is_available() -> bool:
    """True when the model is downloaded and onnxruntime is importable."""
    if not model_path().exists() or not metadata_path().exists():
        return False
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _labels() -> list[str]:
    data = json.loads(metadata_path().read_text())
    classes = data.get("classes")
    if not isinstance(classes, list):
        raise ValueError("model metadata has no class list")
    return [str(c) for c in classes]


@lru_cache(maxsize=1)
def _session():  # pragma: no cover - exercised via validation, not unit tests
    import onnxruntime as ort

    return ort.InferenceSession(str(model_path()), providers=["CPUExecutionProvider"])


@lru_cache(maxsize=1)
def _mel_filter():  # pragma: no cover - numeric helper, covered by validation
    import librosa

    # slaney scale + slaney norm to match the HF feature extractor's mel_filter_bank.
    return librosa.filters.mel(
        sr=_SAMPLE_RATE,
        n_fft=_FRAME,
        n_mels=_MEL_BANDS,
        fmin=0.0,
        fmax=_SAMPLE_RATE / 2,
        htk=False,
        norm="slaney",
    )


def _patches(path: Path):  # pragma: no cover - numeric helper, covered by validation
    """Return a stack of normalized [_PATCH_FRAMES, 96] log-mel patches for the audio."""
    import librosa
    import numpy as np

    samples, _ = librosa.load(str(path), sr=_SAMPLE_RATE, mono=True)
    if samples.size < _FRAME:
        return None
    power = (
        np.abs(
            librosa.stft(
                samples,
                n_fft=_FRAME,
                hop_length=_HOP,
                win_length=_FRAME,
                window="hann",
                center=True,
                pad_mode="constant",
            )
        )
        ** 2  # power spectrogram (power=2), not magnitude
    )
    mel = np.maximum(_mel_filter() @ power, 1e-30)  # [96, frames], mel_floor
    log_mel = np.log10(1.0 + 10000.0 * mel).T.astype(np.float32)  # [frames, 96]
    log_mel = (log_mel - _NORM_MEAN) / (_NORM_STD * 2.0)  # dataset normalization

    total = log_mel.shape[0]
    if total < _PATCH_FRAMES:  # pad a short track up to one full patch
        pad = np.zeros((_PATCH_FRAMES - total, _MEL_BANDS), dtype=np.float32)
        return np.stack([np.vstack([log_mel, pad])])
    starts = list(range(0, total - _PATCH_FRAMES + 1, _PATCH_FRAMES))[:_MAX_PATCHES]
    return np.stack([log_mel[s : s + _PATCH_FRAMES] for s in starts])


def _predict(path: Path):  # pragma: no cover - exercised via validation
    """Mean class probabilities over the track's patches, or None."""
    import numpy as np

    patches = _patches(path)
    if patches is None:
        return None
    session = _session()
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: patches})
    n_classes = len(_labels())
    preds = next(
        (np.asarray(o) for o in outputs if np.ndim(o) == 2 and np.shape(o)[-1] == n_classes),
        None,
    )
    if preds is None:
        return None
    if preds.min() < 0.0 or preds.max() > 1.0:  # logits → probabilities
        preds = 1.0 / (1.0 + np.exp(-preds))
    return preds.mean(axis=0)  # [400]


def _clean_label(raw: str) -> str:
    # "Electronic---Hard Techno" → "Hard Techno"; canonicalize lowercases later.
    return raw.split("---")[-1].strip()


def lookup_audio_genre(path: Path) -> str | None:
    """Predict a raw sub-genre label (e.g. "Hard Techno"), or None if unavailable/unsure."""
    if not is_available():
        return None
    try:
        scores = _predict(path)
        if scores is None:
            return None
        best = int(scores.argmax())
        if scores[best] < _MIN_CONFIDENCE:
            return None
        return _clean_label(_labels()[best])
    except Exception:
        return None
