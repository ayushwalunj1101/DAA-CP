-- SQLite schema for the momentum system. Dates are ISO text (YYYY-MM-DD), so they sort correctly.

CREATE TABLE IF NOT EXISTS stocks (
    symbol  TEXT PRIMARY KEY,
    isin    TEXT,
    sector  TEXT NOT NULL DEFAULT 'OTHER'
);

-- Daily bars, adjusted for splits and bonuses. traded_value is in rupees (unadjusted).
CREATE TABLE IF NOT EXISTS prices (
    symbol        TEXT NOT NULL,
    date          TEXT NOT NULL,
    open          REAL NOT NULL,
    high          REAL NOT NULL,
    low           REAL NOT NULL,
    close         REAL NOT NULL,
    volume        REAL NOT NULL,
    traded_value  REAL NOT NULL,
    source        TEXT NOT NULL CHECK (source IN ('local', 'fyers')),
    PRIMARY KEY (symbol, date)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS indices (
    name   TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL NOT NULL,
    PRIMARY KEY (name, date)
) WITHOUT ROWID;

-- Monthly universe. month = 'YYYY-MM'; members are rank <= 500, ranks up to 650 are a buffer.
CREATE TABLE IF NOT EXISTS universe (
    month             TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    rank              INTEGER NOT NULL,
    avg_traded_value  REAL NOT NULL,
    PRIMARY KEY (month, symbol)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS holidays (
    date      TEXT PRIMARY KEY,
    occasion  TEXT
);

-- Overnight moves above the flag threshold, for a manual corporate-action check.
CREATE TABLE IF NOT EXISTS update_flags (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    prev_close  REAL NOT NULL,
    close       REAL NOT NULL,
    change_pct  REAL NOT NULL,
    reviewed    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- Daily classification of every scored universe stock (phase 2). cls: -2 est. bearish .. 2 est. bullish.
-- quadrant: 0 accumulation, 1 weak rally, 2 distribution, 3 weak selloff, -1 unknown.
-- flags: rule bits that do not depend on score weights (1 est. bull, 2 dev. bull, 4 est. bear, 8 dev. bear).
CREATE TABLE IF NOT EXISTS signals (
    date         TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    cls          INTEGER NOT NULL,
    quadrant     INTEGER NOT NULL,
    flags        INTEGER NOT NULL,
    bull_score   REAL NOT NULL,
    bear_score   REAL NOT NULL,
    bull_rank    INTEGER NOT NULL,
    bear_rank    INTEGER NOT NULL,
    p_trend      REAL NOT NULL,
    p_cons_bull  REAL NOT NULL,
    p_cons_bear  REAL NOT NULL,
    p_rs         REAL NOT NULL,
    p_volume     REAL NOT NULL,
    p_vwap       REAL NOT NULL,
    close        REAL NOT NULL,
    change_pct   REAL,
    atr14        REAL,
    PRIMARY KEY (date, symbol)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol, date);

CREATE TABLE IF NOT EXISTS daily_stats (
    date              TEXT PRIMARY KEY,
    scanned           INTEGER NOT NULL,
    est_bull          INTEGER NOT NULL,
    dev_bull          INTEGER NOT NULL,
    neutral           INTEGER NOT NULL,
    dev_bear          INTEGER NOT NULL,
    est_bear          INTEGER NOT NULL,
    bull_cut_est      REAL,
    bull_cut_dev      REAL,
    bear_cut_est      REAL,
    bear_cut_dev      REAL,
    churn_inversions  INTEGER,
    churn_pairs       INTEGER
);
