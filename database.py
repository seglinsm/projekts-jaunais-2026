from pathlib import Path
import sqlite3

from flask import current_app, g


PAMATMAPE = Path(__file__).resolve().parent
NOKLUSETA_DATUBAZE = PAMATMAPE / "goalbloom.db"
SHEMAS_CELS = PAMATMAPE / "schema.sql"


def iegut_datubazi():
    if "db" not in g:
        savienojums = sqlite3.connect(current_app.config["DATABASE"])
        savienojums.row_factory = sqlite3.Row
        savienojums.execute("PRAGMA foreign_keys = ON")
        g.db = savienojums
    return g.db


def aizvert_datubazi(_kluda=None):
    savienojums = g.pop("db", None)
    if savienojums is not None:
        savienojums.close()


def inicializet_datubazi(datubazes_cels=None):
    datubazes_cels = Path(datubazes_cels or NOKLUSETA_DATUBAZE)
    datubazes_cels.parent.mkdir(parents=True, exist_ok=True)

    savienojums = sqlite3.connect(datubazes_cels)
    savienojums.execute("PRAGMA foreign_keys = ON")
    savienojums.executescript(SHEMAS_CELS.read_text(encoding="utf-8"))
    _parnest_veco_shemu_uz_latviesu_valodu(savienojums)
    savienojums.commit()
    savienojums.close()


def inicializet_lietotni(lietotne):
    lietotne.teardown_appcontext(aizvert_datubazi)


def _parnest_veco_shemu_uz_latviesu_valodu(savienojums):
    tabulas = {
        rinda[0]
        for rinda in savienojums.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
    }

    if "users" in tabulas:
        savienojums.execute(
            """
            INSERT OR IGNORE INTO lietotaji (id, lietotajvards, paroles_jaukums, izveidots_laiks)
            SELECT id, username, password_hash, created_at
            FROM users
            """
        )

    if "savings_profiles" in tabulas:
        savienojums.execute(
            """
            INSERT OR IGNORE INTO krajsanas_plani (
                id,
                lietotaja_id,
                merka_nosaukums,
                merka_summa,
                pasreizejais_atlikums,
                ikmenesa_iemaksa,
                merka_datums,
                piezime,
                atjauninats_laiks
            )
            SELECT
                id,
                user_id,
                goal_name,
                goal_amount,
                current_balance,
                monthly_contribution,
                target_date,
                note,
                updated_at
            FROM savings_profiles
            """
        )

    if "savings_profiles" in tabulas:
        savienojums.execute("DROP TABLE savings_profiles")

    if "users" in tabulas:
        savienojums.execute("DROP TABLE users")
