-- P0 forward-collected forecast store (cloud twin of data/processed/forecast_store.parquet).
-- One row per (province, issue_date, target_date): Open-Meteo's forecast issued on
-- issue_date for target_date, lead_k = target_date - issue_date (0..6). Leakage-safe
-- by construction; rows are immutable once collected (a forecast already issued
-- never changes), hence ON CONFLICT DO NOTHING on the writer side.
CREATE TABLE IF NOT EXISTS heatwave.forecast_store (
    province_id      integer     NOT NULL REFERENCES heatwave.provinces(id),
    issue_date       date        NOT NULL,
    target_date      date        NOT NULL,
    lead_k           smallint    NOT NULL,
    fc_tmax          real        NOT NULL,
    fc_rh            real        NOT NULL,
    fc_heat_index    real        NOT NULL,
    fc_soil_moisture real,
    collected_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (province_id, issue_date, target_date),
    CHECK (target_date >= issue_date)
);

-- Training joins slice by issue_date (one batch per day).
CREATE INDEX IF NOT EXISTS forecast_store_issue_date_idx
    ON heatwave.forecast_store (issue_date);
