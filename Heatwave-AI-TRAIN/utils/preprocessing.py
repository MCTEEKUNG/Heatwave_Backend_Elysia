# -*- coding: utf-8 -*-
"""
utils/preprocessing.py
Feature engineering, label generation, normalization, and train/val/test splitting.


Key components:
  - _compute_rh_from_era5()     : August-Roche-Magnus formula for relative humidity
  - _compute_derived_features() : Rothfusz Heat Index, wind speed, WBGT
  - _generate_labels()           : delegates to utils.heatwave_labels (wbgt default)
                                   legacy modes: "heat_index" | "temperature"
  - _merge_ndvi_features()       : merge MODIS NDVI; skips gracefully when ndvi.enabled: false
  - fit_transform() pipeline     : ordering aligned to Heatwave-definition.md Section 2
  - _split_by_year()             : year-based split (no temporal leakage)
  - _split_random()              : legacy stratified random split (reproducibility only)
"""
import logging
import warnings
import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import joblib
import os

logger = logging.getLogger(__name__)

KELVIN_OFFSET = 273.15


class HeatwavePreprocessor:
    """Transforms raw ERA5 DataFrame into ML-ready X, y arrays."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        self.threshold_c = self.cfg["data"]["heatwave_threshold_celsius"]
        self.features    = self.cfg["data"]["features"]
        self.label_col   = self.cfg["data"]["label_col"]
        self.split_cfg   = self.cfg["split"]
        self.scaler      = StandardScaler()
        self.imputer     = SimpleImputer(strategy="median")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(self, df: pd.DataFrame):
        """
        Apply full preprocessing pipeline.
        Pipeline ordering:
          1. _engineer_features        — unit conversions (K → °C)
          2. _compute_rh_from_era5     — Relative Humidity (Magnus formula)
          3. _compute_derived_features — Heat Index (Rothfusz), wind speed
          4. _aggregate_to_daily       — collapse hourly ERA5 → 1 row/day/cell [FIX #1]
          5. _merge_ndvi_features      — MODIS NDVI (skipped if ndvi.enabled: false)
          6. _generate_labels          — binary heatwave label (WBGT consecutive-day)
          7. _drop_na
        Returns (X_train, X_val, X_test, y_train, y_val, y_test, feature_names)

        Split strategy (config.split.method):
          year_based — train on train_years; val = first half of val_years (chrono);
                       test = second half of val_years (truly held out) [FIX #2]
          random     — legacy stratified random split (kept for reproducibility checks)
        """
        df = self._engineer_features(df)
        df = self._compute_rh_from_era5(df)
        df = self._compute_derived_features(df)
        df = self._aggregate_to_daily(df)       # FIX #1: hourly → daily before labeling
        df = self._merge_ndvi_features(df)
        df = self._generate_labels(df)
        df = self._drop_na(df)

        feature_names = self._get_feature_names(df)

        logger.info(
            "Label distribution: heatwave=%.2f%% | Total samples: %d | Features: %d",
            100 * df[self.label_col].mean(), len(df), len(feature_names),
        )

        if self.split_cfg.get("method") == "year_based":
            X_train, X_val, X_test, y_train, y_val, y_test = self._split_by_year(df, feature_names)
        else:
            X_train, X_val, X_test, y_train, y_val, y_test = self._split_random(df, feature_names)

        # FIX #3: impute NaN → median, then scale (fit only on train to prevent leakage)
        X_train = self.imputer.fit_transform(X_train)
        X_val   = self.imputer.transform(X_val)
        X_test  = self.imputer.transform(X_test)

        X_train = self.scaler.fit_transform(X_train)
        X_val   = self.scaler.transform(X_val)
        X_test  = self.scaler.transform(X_test)

        logger.info("Split — Train: %d | Val: %d | Test: %d", len(X_train), len(X_val), len(X_test))
        return X_train, X_val, X_test, y_train, y_val, y_test, feature_names

    def _split_by_year(self, df: pd.DataFrame, feature_names: list):
        """
        Year-based temporal split — no leakage, with a true held-out test set.

        Train : train_years  (e.g. 2020–2024)
        Val   : first half of val_years data, sorted chronologically
        Test  : second half of val_years data, sorted chronologically

        Splitting val_years 50/50 chronologically (e.g. Jan–Jun 2025 = val,
        Jul–Dec 2025 = test) gives a held-out test set that was never seen during
        hyperparameter tuning or early stopping.
        """
        train_years = set(self.split_cfg["train_years"])
        val_years   = set(self.split_cfg["val_years"])

        if "year" in df.columns:
            year_col = df["year"]
        else:
            year_col = pd.to_datetime(df["time"]).dt.year

        train_mask = year_col.isin(train_years).values
        val_mask   = year_col.isin(val_years).values

        # Hard leakage check — must never overlap
        assert not np.any(train_mask & val_mask), (
            "BUG: some rows are in both train and val splits!"
        )

        # Chronological split of val_years → val (first half) and test (second half)
        val_indices = np.where(val_mask)[0]
        if "time" in df.columns and len(val_indices) > 1:
            val_times = pd.to_datetime(df["time"].iloc[val_indices])
            sorted_val_idx = val_indices[np.argsort(val_times.values)]
        else:
            sorted_val_idx = val_indices

        mid = len(sorted_val_idx) // 2
        val_only_mask  = np.zeros(len(df), dtype=bool)
        test_only_mask = np.zeros(len(df), dtype=bool)
        val_only_mask[sorted_val_idx[:mid]]  = True
        test_only_mask[sorted_val_idx[mid:]] = True

        X = df[feature_names].values
        y = df[self.label_col].values

        logger.info(
            "year_based split — train: %d rows %s | val: %d rows (first-half %s) | test: %d rows (second-half %s)",
            train_mask.sum(), sorted(train_years),
            val_only_mask.sum(), sorted(val_years),
            test_only_mask.sum(), sorted(val_years),
        )
        return (
            X[train_mask],    X[val_only_mask],    X[test_only_mask],
            y[train_mask],    y[val_only_mask],    y[test_only_mask],
        )

    def _split_random(self, df: pd.DataFrame, feature_names: list):
        """Legacy stratified random split — kept for reproducibility checks only."""
        X = df[feature_names].values
        y = df[self.label_col].values
        stratify = y if self.split_cfg.get("stratify", True) else None
        X_tr_full, X_test, y_tr_full, y_test = train_test_split(
            X, y,
            test_size=self.split_cfg.get("test", 0.15),
            random_state=self.split_cfg.get("random_state", 42),
            stratify=stratify,
        )
        val_ratio = self.split_cfg.get("val", 0.15) / (1 - self.split_cfg.get("test", 0.15))
        stratify_tr = y_tr_full if self.split_cfg.get("stratify", True) else None
        X_train, X_val, y_train, y_val = train_test_split(
            X_tr_full, y_tr_full,
            test_size=val_ratio,
            random_state=self.split_cfg.get("random_state", 42),
            stratify=stratify_tr,
        )
        return X_train, X_val, X_test, y_train, y_val, y_test

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Apply preprocessing to new data using already-fitted scaler and imputer."""
        df = self._engineer_features(df)
        df = self._compute_rh_from_era5(df)
        df = self._compute_derived_features(df)
        df = self._merge_ndvi_features(df)
        feature_names = self._get_feature_names(df)
        X = df[feature_names].values
        X = self.imputer.transform(X)   # FIX #3: same NaN strategy as training
        return self.scaler.transform(X)

    def save_scaler(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.scaler, path)
        imputer_path = path.replace("scaler.pkl", "imputer.pkl")
        joblib.dump(self.imputer, imputer_path)
        logger.info("Scaler saved to %s", path)
        logger.info("Imputer saved to %s", imputer_path)

    def load_scaler(self, path: str):
        self.scaler = joblib.load(path)
        imputer_path = path.replace("scaler.pkl", "imputer.pkl")
        if os.path.isfile(imputer_path):
            self.imputer = joblib.load(imputer_path)
            logger.info("Imputer loaded from %s", imputer_path)
        else:
            logger.warning(
                "imputer.pkl not found at %s — re-run preprocessing to generate it. "
                "Falling back to median imputation with unfitted imputer.",
                imputer_path,
            )
        logger.info("Scaler loaded from %s", path)

    # ------------------------------------------------------------------
    # Step 1 — Unit Conversions
    # ------------------------------------------------------------------

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert raw ERA5 Kelvin values to Celsius."""
        df = df.copy()

        temp_vars = ["t2m", "d2m"]
        for col in temp_vars:
            if col in df.columns:
                # Only convert if values look like Kelvin (> 200)
                if df[col].median() > 200:
                    df[f"{col}_c"] = df[col] - KELVIN_OFFSET
                else:
                    df[f"{col}_c"] = df[col]

        return df

    # ------------------------------------------------------------------
    # Step 2 — Relative Humidity (August-Roche-Magnus formula)
    # ------------------------------------------------------------------

    def _compute_rh_from_era5(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Relative Humidity (%) from t2m_c and d2m_c.

        Formula: August-Roche-Magnus approximation
          RH = 100 × exp[(17.625 × Td)/(243.04 + Td) − (17.625 × T)/(243.04 + T)]

        Input  : t2m_c (°C), d2m_c (°C)
        Output : rh (%)
        """
        if "t2m_c" not in df.columns or "d2m_c" not in df.columns:
            logger.debug("_compute_rh_from_era5: t2m_c or d2m_c not found — skipping RH computation")
            return df

        T  = df["t2m_c"]
        Td = df["d2m_c"]

        df["rh"] = 100 * np.exp(
            (17.625 * Td) / (243.04 + Td) -
            (17.625 * T)  / (243.04 + T)
        )
        df["rh"] = df["rh"].clip(0, 100)  # enforce physical bounds [0, 100]

        rh_over = (df["rh"] > 100).sum()
        if rh_over > 0:
            logger.warning("_compute_rh_from_era5: %d rows clipped above 100%%", rh_over)

        return df

    # ------------------------------------------------------------------
    # Step 3 — Derived Features (Heat Index — Rothfusz, Wind Speed)
    # ------------------------------------------------------------------

    def _compute_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Heat Index (Rothfusz Regression) and Wind Speed.
        Must run after _compute_rh_from_era5().
        """
        df = df.copy()

        # Heat Index — Rothfusz Regression (NWS Standard) - Optimized Vectorized version
        if "t2m_c" in df.columns and "rh" in df.columns:
            T = df["t2m_c"].values
            RH = df["rh"].values
            
            # Rothfusz Regression is valid for T >= 26.7°C
            # For lower temperatures, HI is just T
            T_f = T * 9 / 5 + 32
            
            HI_f = (
                -42.379
                + 2.04901523  * T_f
                + 10.14333127 * RH
                - 0.22475541  * T_f * RH
                - 0.00683783  * T_f ** 2
                - 0.05481717  * RH ** 2
                + 0.00122874  * T_f ** 2 * RH
                + 0.00085282  * T_f      * RH ** 2
                - 0.00000199  * T_f ** 2 * RH ** 2
            )
            
            # HI in Celsius
            HI_c = (HI_f - 32) * 5 / 9
            
            # Rothfusz is only valid for T >= 26.7°C AND RH >= 40%.
            # Outside that domain, return raw temperature (NWS specification).
            valid = (T >= 26.7) & (RH >= 40.0)
            df["heat_index"] = np.where(valid, HI_c, T)
            
        elif "t2m_c" in df.columns and "d2m_c" in df.columns:
            # Fallback: compute RH inline using Steadman approximation if rh col missing
            logger.warning(
                "_compute_derived_features: 'rh' column not found. "
                "Falling back to Steadman approximation for heat_index. "
                "Ensure _compute_rh_from_era5() runs first."
            )
            T  = df["t2m_c"]
            Td = df["d2m_c"]
            RH = (100 - 5 * (T - Td)).clip(0, 100)
            df["heat_index"] = T + 0.33 * (RH / 100 * 6.105 * np.exp(17.27 * T / (237.7 + T))) - 4.0

        # Wind speed magnitude
        if "u10" in df.columns and "v10" in df.columns:
            df["wind_speed"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)

        # WBGT — always compute so it's available as a feature regardless of labeling method.
        # Lemke & Kjellstrom 2012 outdoor approximation (shaded, no globe temperature).
        if "t2m_c" in df.columns and "rh" in df.columns:
            from utils.heatwave_labels import compute_wbgt  # noqa: PLC0415
            df["wbgt"] = compute_wbgt(df["t2m_c"].values, df["rh"].values)

        return df

    def _compute_heat_index(self, T: float, RH: float) -> float:
        """
        Rothfusz Regression (NWS Standard).
        Input  : T  — temperature (°C), RH — relative humidity (%)
        Output : Heat Index (°C)

        ⚠️  Valid only when T >= 26.7°C (80°F) and RH >= 40%.
            Below this range the simple T value is returned directly.
        """
        if T < 26.7 or RH < 40.0:
            return T  # Rothfusz only valid for T >= 26.7°C AND RH >= 40%

        T_f = T * 9 / 5 + 32  # convert to Fahrenheit (formula uses °F)

        HI_f = (
            -42.379
            + 2.04901523  * T_f
            + 10.14333127 * RH
            - 0.22475541  * T_f * RH
            - 0.00683783  * T_f ** 2
            - 0.05481717  * RH ** 2
            + 0.00122874  * T_f ** 2 * RH
            + 0.00085282  * T_f      * RH ** 2
            - 0.00000199  * T_f ** 2 * RH ** 2
        )

        return (HI_f - 32) * 5 / 9  # convert back to Celsius

    # ------------------------------------------------------------------
    # Step 4 — Daily Aggregation (FIX #1: collapse hourly ERA5 → 1 row/day/cell)
    # ------------------------------------------------------------------

    def _aggregate_to_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Collapse sub-daily ERA5 rows into one row per (date, latitude, longitude).

        Aggregation rules:
          - t2m_c, heat_index : max  — peak heat drives heatwave labels
          - d2m_c, rh, sp     : mean
          - u10, v10          : mean — wind components preserve directionality
          - wind_speed        : mean
          - year              : first (constant within a year)

        No-op when input is already at daily or coarser resolution, so the
        pipeline is safe to call on pre-aggregated data too.
        """
        if "time" not in df.columns:
            return df

        times = pd.to_datetime(df["time"])
        unique_times = times.nunique()
        unique_dates = times.dt.date.nunique()

        if unique_times == unique_dates:
            return df  # already daily — nothing to do

        logger.info(
            "_aggregate_to_daily: %d rows | %d timestamps → %d dates — aggregating to daily...",
            len(df), unique_times, unique_dates,
        )

        df = df.copy()
        df["_date"] = times.dt.date
        group_cols = [c for c in ["latitude", "longitude", "_date"] if c in df.columns]

        agg: dict = {}
        for col in ["t2m_c", "heat_index", "t2m"]:
            if col in df.columns:
                agg[col] = "max"
        for col in ["d2m_c", "rh", "sp", "u10", "v10", "wind_speed", "d2m"]:
            if col in df.columns:
                agg[col] = "mean"
        if "year" in df.columns:
            agg["year"] = "first"

        daily = df.groupby(group_cols).agg(agg).reset_index()
        daily = daily.rename(columns={"_date": "time"})
        daily["time"] = pd.to_datetime(daily["time"])

        logger.info("_aggregate_to_daily: → %d daily rows", len(daily))
        return daily

    # ------------------------------------------------------------------
    # Step 5 — NDVI Merge (skipped gracefully when ndvi.enabled: false)
    # ------------------------------------------------------------------

    def _merge_ndvi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge MODIS NDVI features (ndvi, ndvi_lag1, ndvi_lag2) into df.
        Skips automatically if ndvi.enabled is false in config.
        Requires: latitude, longitude, time columns in df.
        """
        ndvi_cfg = self.cfg.get("ndvi", {})
        if not ndvi_cfg.get("enabled", False):
            logger.debug("_merge_ndvi_features: ndvi.enabled=false — skipping NDVI merge")
            return df

        ndvi_path = ndvi_cfg["processed_file"]
        if not os.path.isfile(ndvi_path):
            warnings.warn(
                f"[NDVI Merge] processed_file not found: {ndvi_path}. "
                "Skipping NDVI merge. Run utils/ndvi_processor.py to generate it first.",
                UserWarning
            )
            return df

        try:
            import xarray as xr
            ndvi_ds  = xr.open_dataset(ndvi_path)
            ndvi_df  = ndvi_ds.to_dataframe().reset_index()
            
            # Standardize coordinate names for NDVI
            rename_map = {
                "lat": "latitude", "lon": "longitude",
                "y": "latitude", "x": "longitude"
            }
            ndvi_df = ndvi_df.rename(columns={k: v for k, v in rename_map.items() if k in ndvi_df.columns})
        except Exception as exc:
            warnings.warn(f"[NDVI Merge] Failed to load NDVI dataset: {exc}. Skipping.", UserWarning)
            return df

        # Align on monthly period to handle daily ERA5 vs monthly MODIS
        ndvi_df["time_month"] = pd.to_datetime(ndvi_df["time"]).dt.to_period("M")
        df = df.copy()
        df["time_month"]      = pd.to_datetime(df["time"]).dt.to_period("M")

        # Round coordinates to avoid float precision mismatch
        for frame in [df, ndvi_df]:
            frame["lat_r"] = frame["latitude"].round(2)
            frame["lon_r"] = frame["longitude"].round(2)

        ndvi_cols = [c for c in ndvi_df.columns if c.startswith("ndvi")]
        df = df.merge(
            ndvi_df[["time_month", "lat_r", "lon_r"] + ndvi_cols],
            on=["time_month", "lat_r", "lon_r"],
            how="left"
        )

        # Warn if too many rows have missing NDVI after merge
        if "ndvi" in df.columns:
            missing_pct = df["ndvi"].isna().mean()
            if missing_pct > 0.05:
                warnings.warn(
                    f"[NDVI Merge] {missing_pct:.1%} of rows have missing NDVI. "
                    "Check grid/time alignment between MODIS and ERA5.",
                    UserWarning
                )

        return df.drop(columns=["time_month", "lat_r", "lon_r"], errors="ignore")

    # ------------------------------------------------------------------
    # Step 6 — Label Generation (dual-mode)
    # ------------------------------------------------------------------

    def _generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate binary heatwave labels.

        When config contains a 'heatwave_label' section, delegates to
        utils.heatwave_labels.dispatch (multi-criteria, Thailand-aware).

        Legacy modes (config.data.labeling_method):
          "heat_index" : HI >= heatwave_heat_index_threshold (default 35°C)
          "temperature": t2m_c >= heatwave_threshold_celsius (35°C)
        """
        df = df.copy()

        # New multi-criteria labeler takes priority when configured
        if "heatwave_label" in self.cfg:
            from utils.heatwave_labels import dispatch
            df = dispatch(df, self.cfg)
            return df.rename(columns={"is_heatwave": self.label_col})

        method = self.cfg["data"].get("labeling_method", "heat_index")

        if method == "heat_index":
            if "heat_index" not in df.columns:
                raise ValueError(
                    "[_generate_labels] Column 'heat_index' not found. "
                    "Ensure _compute_derived_features() runs before _generate_labels()."
                )
            threshold = self.cfg["data"].get("heatwave_heat_index_threshold", 41.0)
            min_days  = self.cfg["data"].get("heatwave_min_consecutive_days", 3)

            # Step 1: flag individual hot days
            hot = (df["heat_index"] >= threshold).astype(int)

            # Step 2: require min_days consecutive hot days at each location.
            # A single-day spike must NOT trigger a heatwave label.
            sort_cols  = [c for c in ["latitude", "longitude", "time"] if c in df.columns]
            group_cols = [c for c in ["latitude", "longitude"] if c in df.columns]

            if sort_cols:
                df = df.sort_values(sort_cols).reset_index(drop=True)
                hot = hot.reindex(df.index)

            def _mark_runs(s: pd.Series, min_len: int) -> pd.Series:
                """Label every day that belongs to a run of ≥ min_len consecutive 1s."""
                # Consecutive-run groups (value changes flip the group id)
                groups   = (s != s.shift()).cumsum()
                run_lens = s.groupby(groups).transform("sum")
                return ((s == 1) & (run_lens >= min_len)).astype(int)

            if group_cols:
                df["_hot"] = hot
                df[self.label_col] = (
                    df.groupby(group_cols)["_hot"]
                    .transform(lambda s: _mark_runs(s, min_days))
                )
                df = df.drop(columns=["_hot"])
            else:
                df[self.label_col] = _mark_runs(hot, min_days)

            logger.info(
                "_generate_labels: mode=heat_index, threshold=%.1f°C, "
                "min_consecutive_days=%d, heatwave_rate=%.2f%%",
                threshold, min_days, 100 * df[self.label_col].mean()
            )

        else:  # "temperature" — legacy / backward compat
            threshold = self.cfg["data"].get("heatwave_threshold_celsius", 35.0)
            if "t2m_c" in df.columns:
                df[self.label_col] = (df["t2m_c"] >= threshold).astype(int)
            elif "t2m" in df.columns:
                df[self.label_col] = (df["t2m"] - KELVIN_OFFSET >= threshold).astype(int)
            else:
                raise ValueError("Temperature variable 't2m' not found in DataFrame")
            logger.info(
                "_generate_labels: mode=temperature, threshold=%.1f°C, heatwave_rate=%.2f%%",
                threshold, 100 * df[self.label_col].mean()
            )

        return df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _drop_na(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.dropna(subset=[self.label_col])
        dropped = before - len(df)
        if dropped:
            logger.debug("Dropped %d rows with NaN labels", dropped)
        return df

    def _get_feature_names(self, df: pd.DataFrame) -> list:
        """Return ordered list of available, non-empty engineered feature columns.

        Columns that are entirely NaN (e.g. ndvi when the NDVI file is missing)
        are excluded — an all-NaN column gives SimpleImputer a NaN median, which
        then propagates NaN into the scaler and crashes fit_transform.
        """
        candidates = [
            "t2m_c", "d2m_c",       # temperature (°C)
            "rh",                    # relative humidity
            "heat_index",            # Heat Index (Rothfusz)
            "wbgt",                  # Wet-Bulb Globe Temperature (Lemke & Kjellstrom 2012)
            "wind_speed",            # speed magnitude
            "sp",                    # surface pressure
            "ndvi", "ndvi_lag1", "ndvi_lag2",  # MODIS NDVI (if merged)
        ]
        return [
            c for c in candidates
            if c in df.columns and df[c].notna().any()
        ]


# ------------------------------------------------------------------
def preprocess(df: pd.DataFrame, config_path: str = "config/config.yaml"):
    """Convenience function used by the pipeline."""
    preprocessor = HeatwavePreprocessor(config_path)
    return preprocessor.fit_transform(df)
