import numpy as np, pandas as pd
from pipeline.frame_cache import cached_build_frames, frame_cache_key
from pipeline.train import build_frames
from tests.test_train import _synth_dataset  # reuse the synthetic dataset


def test_cached_frame_matches_build_frames(tmp_path):
    ds = _synth_dataset()
    ds.to_parquet(tmp_path / "ds.parquet")
    direct = build_frames(ds, horizons=range(1, 4))
    cached = cached_build_frames(str(tmp_path / "ds.parquet"), horizons=range(1, 4),
                                 cache_dir=str(tmp_path / "cache"))
    pd.testing.assert_frame_equal(direct.reset_index(drop=True), cached.reset_index(drop=True))


def test_second_call_hits_cache(tmp_path):
    ds = _synth_dataset(); ds.to_parquet(tmp_path / "ds.parquet")
    key = frame_cache_key(str(tmp_path / "ds.parquet"), range(1, 4))
    cache_dir = tmp_path / "cache"
    cached_build_frames(str(tmp_path / "ds.parquet"), range(1, 4), cache_dir=str(cache_dir))
    assert (cache_dir / f"{key}.parquet").exists()  # cache written


def test_cache_invalidates_when_dataset_changes(tmp_path):
    p = tmp_path / "ds.parquet"
    _synth_dataset(seed=0).to_parquet(p)
    k1 = frame_cache_key(str(p), range(1, 4))
    _synth_dataset(seed=1).to_parquet(p)  # rewrite -> new mtime/size
    k2 = frame_cache_key(str(p), range(1, 4))
    assert k1 != k2
