"""Build a POWERED GEFS forecast store: dense inits across the full 2016-2019
ERA5-label overlap (heatwave season Mar-May), with BOTH forecast tmax (daily-max)
and forecast specific humidity (daily-mean) per init -- so train_p0 can build a
forecast heat-index covariate AND have enough matched positives for the antecedent
baseline to be non-random (the power the 52-init subset lacked).

Idempotent: inits already complete (fc_spfh present) are skipped. Each global file
is deleted right after extraction, so disk stays small; only the parquet store grows.
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from scripts.fetch_gefs_reforecast import RAW, STORE, _download, gefs_tmax_url, daily_max_rows
from scripts.fetch_gefs_spfh import spfh_url, daily_mean_spfh_rows


def season_inits(years, m_start=3, m_end=5, stride=3):
    out = []
    for y in years:
        d, end = date(y, m_start, 1), date(y, m_end, 31)
        while d <= end:
            out.append(d); d += timedelta(days=stride)
    return out


def init_rows(ds_tmax, ds_spfh, provinces):
    rows = []
    for _, p in provinces.iterrows():
        pid, lat, lon = int(p["id"]), float(p["lat"]), float(p["lon"])
        tmax = pd.DataFrame(daily_max_rows(ds_tmax, pid, lat, lon))
        spfh = pd.DataFrame(daily_mean_spfh_rows(ds_spfh, pid, lat, lon))
        if tmax.empty or spfh.empty:
            continue
        merged = tmax.merge(spfh, on=["province_id", "issue_date", "target_date", "lead_k"], how="inner")
        rows.append(merged)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _merge_and_write(existing, new_frames):
    """Merge accumulated new-init frames with the existing store and persist.

    Used for BOTH periodic checkpoints and the final write (identical logic) so a
    crash mid-pull never loses processed inits -- a re-run resumes via the ``done``
    set, which is recomputed from whatever was last written here.
    """
    new = pd.concat(new_frames, ignore_index=True) if new_frames else pd.DataFrame()
    if not existing.empty:
        keep_cols = [c for c in ["province_id", "issue_date", "target_date", "lead_k", "fc_tmax", "fc_spfh"] if c in existing.columns]
        existing = existing[keep_cols]
        if "fc_spfh" in existing.columns:
            existing = existing[existing["fc_spfh"].notna()]
    out = pd.concat([existing, new], ignore_index=True).drop_duplicates(
        subset=["province_id", "issue_date", "target_date", "lead_k"], keep="last")
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    out.to_parquet(STORE, index=False)
    return out


def main():
    import xarray as xr
    provinces = load_provinces()
    # Years can be passed on the CLI (e.g. ``build_gefs_store 2016 2017``) to pull a
    # subset first; default is the full 2016-2019 ERA5-label overlap. GEFSv12
    # reforecast archive ends at 2019, so later years are unavailable by design.
    years = [int(a) for a in sys.argv[1:]] or [2016, 2017, 2018, 2019]
    inits = season_inits(years)
    existing = pd.read_parquet(STORE) if os.path.exists(STORE) else pd.DataFrame()
    done = set()
    if not existing.empty and "fc_spfh" in existing.columns:
        ok = existing[existing["fc_spfh"].notna()]
        done = set(ok["issue_date"].unique())

    new_frames = []
    for j, init in enumerate(inits, 1):
        iso = init.isoformat()
        if iso in done:
            continue
        ts = os.path.join(RAW, f"tmax_2m_{init.strftime('%Y%m%d')}00_c00.grib2")
        ss = os.path.join(RAW, f"spfh_2m_{init.strftime('%Y%m%d')}00_c00.grib2")
        if not _download(gefs_tmax_url(init), ts):
            continue
        if not _download(spfh_url(iso), ss):
            os.remove(ts) if os.path.exists(ts) else None
            continue
        try:
            dt = xr.open_dataset(ts, engine="cfgrib", backend_kwargs={"indexpath": ""})
            dh = xr.open_dataset(ss, engine="cfgrib", backend_kwargs={"indexpath": ""})
            new_frames.append(init_rows(dt, dh, provinces))
            dt.close(); dh.close()
        finally:
            for f in (ts, ss):
                if os.path.exists(f):
                    os.remove(f)
        # crash-safe checkpoint: persist every 10 successfully-processed inits so a
        # multi-hour pull that dies (or is killed) resumes instead of restarting.
        if len(new_frames) and len(new_frames) % 10 == 0:
            _merge_and_write(existing, new_frames)
            tot = sum(len(x) for x in new_frames)
            print(f"  checkpoint @ {j}/{len(inits)} inits ({len(new_frames)} new), "
                  f"rows this run {tot} -> store written", flush=True)

    out = _merge_and_write(existing, new_frames)
    print(f"GEFS store powered: {len(out)} rows, {out['issue_date'].nunique()} inits, "
          f"{out['province_id'].nunique()} provinces, fc_spfh coverage "
          f"{out['fc_spfh'].notna().mean()*100:.0f}%", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
