import pytest

from cratemind.analysis.bpm import bucket, fold_octave


def test_fold_octave_doubles_when_below_window():
    # a 64-BPM half-time read of a 128-BPM track folds back up
    assert fold_octave(64, 70, 180) == 128


def test_fold_octave_halves_when_above_window():
    assert fold_octave(200, 70, 180) == 100


def test_fold_octave_keeps_value_already_in_window():
    assert fold_octave(118, 70, 180) == 118


def test_fold_octave_rejects_nonpositive():
    with pytest.raises(ValueError):
        fold_octave(0, 70, 180)


def test_bucket_aligns_to_fixed_band():
    assert bucket(105, 8) == "104-111"
    assert bucket(96, 8) == "96-103"


def test_bucket_rejects_nonpositive_width():
    with pytest.raises(ValueError):
        bucket(120, 0)
