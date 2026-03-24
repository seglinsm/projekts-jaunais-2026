CREATE TABLE IF NOT EXISTS lietotaji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lietotajvards TEXT NOT NULL UNIQUE COLLATE NOCASE,
    paroles_jaukums TEXT NOT NULL,
    izveidots_laiks TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS krajsanas_plani (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lietotaja_id INTEGER NOT NULL UNIQUE,
    merka_nosaukums TEXT NOT NULL,
    merka_summa REAL NOT NULL CHECK (merka_summa > 0),
    pasreizejais_atlikums REAL NOT NULL CHECK (pasreizejais_atlikums >= 0),
    ikmenesa_iemaksa REAL NOT NULL CHECK (ikmenesa_iemaksa >= 0),
    merka_datums TEXT,
    piezime TEXT NOT NULL DEFAULT '',
    atjauninats_laiks TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lietotaja_id) REFERENCES lietotaji(id) ON DELETE CASCADE
);
