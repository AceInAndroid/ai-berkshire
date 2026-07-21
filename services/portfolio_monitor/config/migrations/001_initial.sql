PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instruments (
  symbol TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  module TEXT NOT NULL,
  role TEXT NOT NULL,
  target_amount_cny REAL NOT NULL,
  alternative_for TEXT,
  config_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_type TEXT NOT NULL,
  symbol TEXT,
  quantity REAL NOT NULL DEFAULT 0,
  price REAL NOT NULL DEFAULT 0,
  fees REAL NOT NULL DEFAULT 0,
  traded_at TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  corrected_from_id INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY(corrected_from_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS positions (
  symbol TEXT PRIMARY KEY,
  quantity REAL NOT NULL,
  average_cost REAL NOT NULL,
  realized_pnl REAL NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(symbol) REFERENCES instruments(symbol)
);

CREATE TABLE IF NOT EXISTS market_bars (
  symbol TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  interval TEXT NOT NULL DEFAULT '1d',
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL DEFAULT 0,
  amount REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY(symbol, trade_date, interval, source)
);

CREATE TABLE IF NOT EXISTS indicator_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  data_as_of TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  UNIQUE(symbol, data_as_of)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  data_as_of TEXT NOT NULL UNIQUE,
  total_assets REAL NOT NULL,
  cash REAL NOT NULL,
  drawdown REAL NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dedup_key TEXT NOT NULL UNIQUE,
  rule_id TEXT NOT NULL,
  symbol TEXT,
  module TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  first_triggered_at TEXT NOT NULL,
  last_triggered_at TEXT NOT NULL,
  acknowledged_at TEXT,
  snoozed_until TEXT,
  delivery_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS backtest_runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  config_version TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT,
  artifact_path TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS scheduler_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  duration_ms REAL,
  details_json TEXT
);

CREATE TABLE IF NOT EXISTS system_state (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
