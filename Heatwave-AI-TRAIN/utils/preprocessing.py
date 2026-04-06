# -*- coding: utf-8 -*-
"""
utils/preprocessing.py
Feature engineering, label generation, normalization, and train/val/test splitting.


Updated:
  - _compute_rh_from_era5()     : August-Roche-Magnus formula (replaces inline RH approx)
  - _compute_heat_index()        : Rothfusz Regression (NWS standard, replaces Steadman)
  - _generate_labels()           : dual-mode — "heat_index" (default) | "temperature" (legacy)
  - _merge_ndvi_features()       : merge MODIS NDVI; skips gracefully when ndvi.enabled: false
  - fit_transform() pipeline     : ordering aligned to Heatwave-definition.md Section 2
"""
import logging
import warnings
import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(self, df: pd.DataFrame):
        """
        Apply full preprocessing pipeline.
        Pipeline ordering (Heatwave-definition.md Section 2):
          1. _engineer_features       — unit conversions
          2. _compute_rh_from_era5    — Relative Humidity (Magnus formula)
          3. _compute_derived_features — Heat Index (Rothfusz), wind speed
          4. _merge_ndvi_features     — MODIS NDVI (skipped if ndvi.enabled: false)
          5. _generate_labels         — binary heatwave label
          6. _drop_na
        Returns (X_train, X_val, X_test, y_train, y_val, y_test, feature_names)
        """
        df = self._engineer_features(df)
        df = self._compute_rh_from_era5(df)
        df = self._compute_derived_features(df)
        df = self._merge_ndvi_features(df)
        df = self._generate_labels(df)
        df = self._drop_na(df)

        feature_names = self._get_feature_names(df)
        X = df[feature_names].values
        y = df[self.label_col].values

        logger.info("Label distribution: heatwave=%.2f%%", 100 * y.mean())
        logger.info("Total samples: %d | Features: %d", len(X), len(feature_names))

        # Split
        stratify = y if self.split_cfg.get("stratify", True) else None
        X_train_full, X_test, y_train_full, y_test = train_test_split(
            X, y,
            test_size=self.split_cfg["test"],
            random_state=self.split_cfg["random_state"],
            stratify=stratify,
        )
        val_ratio = self.split_cfg["val"] / (1 - self.split_cfg["test"])
        stratify_train = y_train_full if self.split_cfg.get("stratify", True) else None
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_full, y_train_full,
            test_size=val_ratio,
            random_state=self.split_cfg["random_state"],
            stratify=stratify_train,
        )

        # Scale (fit only on train)
        X_train = self.scaler.fit_transform(X_train)
        X_val   = self.scaler.transform(X_val)
        X_test  = self.scaler.transform(X_test)

        logger.info("Split — Train: %d | Val: %d | Test: %d", len(X_train), len(X_val), len(X_test))
        return X_train, X_val, X_test, y_train, y_val, y_test, feature_names

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Apply preprocessing to new data using already-fitted scaler."""
        df = self._engineer_features(df)
        df = self._compute_rh_from_era5(df)
        df = self._compute_derived_features(df)
        df = self._merge_ndvi_features(df)
        feature_names = self._get_feature_names(df)
        X = df[feature_names].fillna(0).values
        return self.scaler.transform(X)

    def save_scaler(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.scaler, path)
        logger.info("Scaler saved to %s", path)

    def load_scaler(self, path: str):
        self.scaler = joblib.load(path)
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
    # Step 4 — NDVI Merge (skipped gracefully when ndvi.enabled: false)
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
    # Step 5 — Label Generation (dual-mode)
    # ------------------------------------------------------------------

    def _generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate binary heatwave labels.

        Modes (controlled by config.data.labeling_method):
          "heat_index" (default) : label = 1 if heat_index >= heatwave_heat_index_threshold (41.0°C)
          "temperature" (legacy)  : label = 1 if t2m_c >= heatwave_threshold_celsius (35.0°C)
        """
        df = df.copy()
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
        """Return ordered list of available engineered feature columns."""
        candidates = [
            "t2m_c", "d2m_c",       # temperature (°C)
            "rh",                    # relative humidity
            "heat_index",            # Heat Index (Rothfusz)
            "wind_speed",            # speed magnitude
            "sp",                    # surface pressure
            "ndvi", "ndvi_lag1", "ndvi_lag2",  # MODIS NDVI (if merged)
        ]
        return [c for c in candidates if c in df.columns]


# ------------------------------------------------------------------
def preprocess(df: pd.DataFrame, config_path: str = "config/config.yaml"):
    """Convenience function used by the pipeline."""
    preprocessor = HeatwavePreprocessor(config_path)
    return preprocessor.fit_transform(df)
