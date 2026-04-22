"""GoalBloom — vienkāršs krājumu panelis.

Viss lietotnes kods ir šajā vienā failā, lai projekts būtu viegli pārskatāms.

Sadaļas:
  1. Datubāze (SQLite, divas saistītas tabulas + paroles jaukums)
  2. Krājumu plāna klases (OOP ar mantošanu: bāzes + 2 atvasinātās)
  3. Valūtas kurss (ārējā API: Frankfurter, ECB dati)
  4. Validācija un biznesa loģika
  5. Flask aplikācija un maršruti
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import time
from datetime import date
from functools import wraps
from pathlib import Path
from urllib import error, parse, request

from flask import Flask, Response, g, jsonify, redirect, render_template, request as flask_request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


# =============================================================================
# 1. DATUBĀZE
# =============================================================================

PAMATMAPE = Path(__file__).resolve().parent
NOKLUSETA_DATUBAZE = PAMATMAPE / "goalbloom.db"

SHEMA = """
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
"""


def iegut_datubazi():
    if "db" not in g:
        savienojums = sqlite3.connect(lietotne.config["DATABASE"])
        savienojums.row_factory = sqlite3.Row
        savienojums.execute("PRAGMA foreign_keys = ON")
        g.db = savienojums
    return g.db


def aizvert_datubazi(_kluda=None):
    savienojums = g.pop("db", None)
    if savienojums is not None:
        savienojums.close()


def inicializet_datubazi(datubazes_cels):
    datubazes_cels = Path(datubazes_cels)
    datubazes_cels.parent.mkdir(parents=True, exist_ok=True)
    savienojums = sqlite3.connect(datubazes_cels)
    savienojums.execute("PRAGMA foreign_keys = ON")
    savienojums.executescript(SHEMA)
    savienojums.commit()
    savienojums.close()


# =============================================================================
# 2. KRĀJUMU PLĀNA KLASES (OOP ar mantošanu)
# =============================================================================

class BazesKrajsanasPlans:
    """Bāzes klase jebkuram uzkrājumu plānam."""

    STATUSS_GAIDA = "Gaida ievadi"
    STATUSS_SASNIEGTS = "Mērķis sasniegts"
    STATUSS_BRIVAKS = "Brīvāks temps"

    def __init__(self, merka_nosaukums, merka_summa, pasreizejais_atlikums, piezime=""):
        self.merka_nosaukums = merka_nosaukums
        self.merka_summa = round(float(merka_summa), 2)
        self.pasreizejais_atlikums = round(float(pasreizejais_atlikums), 2)
        self.piezime = piezime or ""

    @property
    def atlikusi_summa(self):
        return round(max(self.merka_summa - self.pasreizejais_atlikums, 0.0), 2)

    @property
    def progresa_procenti(self):
        if self.merka_summa <= 0:
            return 0.0
        return round((self.pasreizejais_atlikums / self.merka_summa) * 100, 1)

    @property
    def redzamie_progresa_procenti(self):
        return min(self.progresa_procenti, 100.0)

    @property
    def ir_sasniegts(self):
        return self.atlikusi_summa <= 0 and self.merka_summa > 0

    def statusa_uzraksts(self):
        if self.ir_sasniegts:
            return self.STATUSS_SASNIEGTS
        return self.STATUSS_BRIVAKS

    def statusa_tonis(self):
        return "labs" if self.ir_sasniegts else "mierigs"

    def prognozes_teksts(self):
        if self.ir_sasniegts:
            return "Tu šo mērķi jau esi sasniedzis."
        return "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku."

    def termina_teksts(self):
        if self.ir_sasniegts:
            return "Viss pēc šī punkta jau ir ekstra rezerve."
        return "Pievieno mērķa datumu, lai redzētu, vai tavs mēneša plāns ir pietiekams."


class RegularsKrajsanasPlans(BazesKrajsanasPlans):
    """Plāns ar ikmēneša iemaksu, bet bez konkrēta termiņa."""

    def __init__(self, merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, piezime=""):
        super().__init__(merka_nosaukums, merka_summa, pasreizejais_atlikums, piezime)
        self.ikmenesa_iemaksa = round(float(ikmenesa_iemaksa), 2)

    def menesi_lidz_merkim(self):
        if self.ikmenesa_iemaksa <= 0 or self.atlikusi_summa <= 0:
            return None
        return max(math.ceil(self.atlikusi_summa / self.ikmenesa_iemaksa), 1)

    def prognozes_teksts(self):
        if self.ir_sasniegts:
            return "Tu šo mērķi jau esi sasniedzis."
        if self.ikmenesa_iemaksa <= 0:
            return "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku."
        menesi = self.menesi_lidz_merkim()
        vards = "mēnesi" if menesi == 1 else "mēnešus"
        return f"Ar pašreizējo tempu tev vajadzēs vēl apmēram {menesi} {vards}."


class TerminetsKrajsanasPlans(RegularsKrajsanasPlans):
    """Plāns ar konkrētu mērķa datumu. Aprēķina nepieciešamo tempu."""

    STATUSS_DATUMS_GARAM = "Datums ir garām"
    STATUSS_IET_LABI = "Viss iet labi"
    STATUSS_PIESPIEST = "Jāpiespiež vairāk"
    STATUSS_NAV_PLANA = "Nav mēneša plāna"

    def __init__(self, merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, merka_datums, piezime=""):
        super().__init__(merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, piezime)
        if isinstance(merka_datums, date):
            self.merka_datums = merka_datums
        else:
            self.merka_datums = date.fromisoformat(merka_datums)

    def dienas_lidz_merkim(self, sodiena=None):
        sodiena = sodiena or date.today()
        return (self.merka_datums - sodiena).days

    def nepieciesama_ikmenesa_iemaksa(self, sodiena=None):
        if self.ir_sasniegts:
            return 0.0
        dienas = self.dienas_lidz_merkim(sodiena)
        if dienas < 0:
            return None
        menesi = max(dienas / 30.44, 0.1)
        return round(self.atlikusi_summa / menesi, 2)

    def statusa_uzraksts(self, sodiena=None):
        if self.ir_sasniegts:
            return self.STATUSS_SASNIEGTS
        dienas = self.dienas_lidz_merkim(sodiena)
        if dienas < 0:
            return self.STATUSS_DATUMS_GARAM
        vajadzigais = self.nepieciesama_ikmenesa_iemaksa(sodiena)
        if self.ikmenesa_iemaksa <= 0:
            return self.STATUSS_NAV_PLANA
        if vajadzigais is not None and self.ikmenesa_iemaksa + 0.009 >= vajadzigais:
            return self.STATUSS_IET_LABI
        return self.STATUSS_PIESPIEST

    def statusa_tonis(self, sodiena=None):
        uzraksts = self.statusa_uzraksts(sodiena)
        ja_labi = {self.STATUSS_SASNIEGTS, self.STATUSS_IET_LABI}
        ja_bridinajums = {self.STATUSS_PIESPIEST, self.STATUSS_NAV_PLANA}
        if uzraksts in ja_labi:
            return "labs"
        if uzraksts == self.STATUSS_DATUMS_GARAM:
            return "trauksme"
        if uzraksts in ja_bridinajums:
            return "bridinajums"
        return "mierigs"


def izveidot_planu(merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa=0.0, merka_datums=None, piezime=""):
    """Fabrika, kas atgriež konkrētāko klasi, kas atbilst ievadītajiem datiem."""
    if merka_datums:
        return TerminetsKrajsanasPlans(merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, merka_datums, piezime)
    if float(ikmenesa_iemaksa or 0) > 0:
        return RegularsKrajsanasPlans(merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, piezime)
    return BazesKrajsanasPlans(merka_nosaukums, merka_summa, pasreizejais_atlikums, piezime)


# =============================================================================
# 3. VALŪTAS KURSS (ārējā API: Frankfurter — ECB dati)
# =============================================================================

FRANKFURTER_BAZE = "https://api.frankfurter.app/latest"
ATLAUTAS_VALUTAS = ("EUR", "USD", "GBP", "SEK", "NOK", "CHF", "PLN")
_KESA_TTL_SEK = 300
_valutas_kess = {}


class ValutasKluda(Exception):
    pass


def iegut_valutas_kursu(no_valutas, uz_valutu, atversanas_funkcija=None):
    """Atgriež, cik vienību "uz_valutu" var saņemt par 1 vienību "no_valutas"."""
    no_valutas = _parbaudit_valutu(no_valutas)
    uz_valutu = _parbaudit_valutu(uz_valutu)
    if no_valutas == uz_valutu:
        return 1.0

    atslega = f"{no_valutas}->{uz_valutu}"
    ieraksts = _valutas_kess.get(atslega)
    if ieraksts and time.monotonic() - ieraksts[0] <= _KESA_TTL_SEK:
        return ieraksts[1]

    url = f"{FRANKFURTER_BAZE}?{parse.urlencode({'from': no_valutas, 'to': uz_valutu})}"
    atversanas_funkcija = atversanas_funkcija or request.urlopen
    try:
        with atversanas_funkcija(url, timeout=5) as atbilde:
            dati = json.loads(atbilde.read().decode("utf-8"))
    except (error.URLError, TimeoutError, OSError) as kluda:
        raise ValutasKluda("Nevar sazināties ar valūtas kursu pakalpojumu.") from kluda
    except ValueError as kluda:
        raise ValutasKluda("Valūtas kursu atbilde nav derīgs JSON.") from kluda

    kursi = dati.get("rates") if isinstance(dati, dict) else None
    if not isinstance(kursi, dict) or uz_valutu not in kursi:
        raise ValutasKluda("Valūtas kursu atbildē nav vajadzīgo datu.")

    kurss = float(kursi[uz_valutu])
    _valutas_kess[atslega] = (time.monotonic(), kurss)
    return kurss


def konvertet_summu(summa, no_valutas, uz_valutu, atversanas_funkcija=None):
    try:
        skaitliska_summa = float(summa)
    except (TypeError, ValueError) as kluda:
        raise ValutasKluda("Summa nav derīgs skaitlis.") from kluda
    kurss = iegut_valutas_kursu(no_valutas, uz_valutu, atversanas_funkcija)
    return round(skaitliska_summa * kurss, 2)


def _parbaudit_valutu(kods):
    parbaudits = (kods or "").strip().upper()
    if parbaudits not in ATLAUTAS_VALUTAS:
        raise ValutasKluda(
            f"Valūta \"{parbaudits}\" nav atbalstīta. Atļautās: {', '.join(ATLAUTAS_VALUTAS)}."
        )
    return parbaudits


# =============================================================================
# 4. VALIDĀCIJA UN BIZNESA LOĢIKA
# =============================================================================

PROGRESA_POSMI = (25, 50, 75, 100)
ATRAS_IEMAKSAS_SUMMAS = (10, 25, 50)


class ValidacijasKluda(ValueError):
    pass


class AutentifikacijasKluda(ValueError):
    pass


def _formatet_valutu(vertiba):
    summa = float(vertiba or 0)
    veselie, dalas = f"{summa:,.2f}".split(".")
    return f"{veselie.replace(',', ' ')},{dalas} €"


def registret_lietotaju(savienojums, dati):
    lietotajvards = _pieprasit_lietotajvardu(dati.get("lietotajvards"))
    parole = _pieprasit_paroli(
        dati.get("parole"),
        dati.get("paroles_apstiprinajums") or dati.get("parolesApstiprinajums"),
    )

    esosais = savienojums.execute(
        "SELECT id FROM lietotaji WHERE lietotajvards = ?", (lietotajvards,)
    ).fetchone()
    if esosais is not None:
        raise ValidacijasKluda("Šis lietotājvārds jau ir aizņemts.")

    kursors = savienojums.execute(
        "INSERT INTO lietotaji (lietotajvards, paroles_jaukums) VALUES (?, ?)",
        (lietotajvards, generate_password_hash(parole)),
    )
    savienojums.commit()
    return iegut_lietotaju_pec_id(savienojums, kursors.lastrowid)


def autentificet_lietotaju(savienojums, dati):
    lietotajvards = (dati.get("lietotajvards") or "").strip()
    parole = dati.get("parole") or ""
    if not lietotajvards or not parole:
        raise AutentifikacijasKluda("Ievadi gan lietotājvārdu, gan paroli.")

    rinda = savienojums.execute(
        "SELECT id, lietotajvards, paroles_jaukums, izveidots_laiks FROM lietotaji WHERE lietotajvards = ?",
        (lietotajvards,),
    ).fetchone()
    if rinda is None or not check_password_hash(rinda["paroles_jaukums"], parole):
        raise AutentifikacijasKluda("Nepareizs lietotājvārds vai parole.")
    return _serializet_lietotaju(rinda)


def iegut_lietotaju_pec_id(savienojums, lietotaja_id):
    rinda = savienojums.execute(
        "SELECT id, lietotajvards, izveidots_laiks FROM lietotaji WHERE id = ?",
        (lietotaja_id,),
    ).fetchone()
    return _serializet_lietotaju(rinda) if rinda else None


def saglabat_krajsanas_planu(savienojums, lietotaja_id, dati):
    merka_nosaukums = _pieprasit_merka_nosaukumu(dati.get("merka_nosaukums"))
    merka_summa = _pieprasit_summu(dati.get("merka_summa"), "mērķa summu", "Mērķa summai", atlaut_nulli=False)
    pasreizejais_atlikums = _pieprasit_summu(dati.get("pasreizejais_atlikums"), "pašreizējo atlikumu", "Pašreizējam atlikumam", atlaut_nulli=True)
    ikmenesa_iemaksa = _pieprasit_summu(dati.get("ikmenesa_iemaksa"), "ikmēneša iemaksu", "Ikmēneša iemaksai", atlaut_nulli=True)
    merka_datums = _neobligats_datums(dati.get("merka_datums"))
    piezime = (dati.get("piezime") or "").strip()[:240]

    savienojums.execute(
        """
        INSERT INTO krajsanas_plani (
            lietotaja_id, merka_nosaukums, merka_summa, pasreizejais_atlikums,
            ikmenesa_iemaksa, merka_datums, piezime
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lietotaja_id) DO UPDATE SET
            merka_nosaukums = excluded.merka_nosaukums,
            merka_summa = excluded.merka_summa,
            pasreizejais_atlikums = excluded.pasreizejais_atlikums,
            ikmenesa_iemaksa = excluded.ikmenesa_iemaksa,
            merka_datums = excluded.merka_datums,
            piezime = excluded.piezime,
            atjauninats_laiks = CURRENT_TIMESTAMP
        """,
        (lietotaja_id, merka_nosaukums, merka_summa, pasreizejais_atlikums, ikmenesa_iemaksa, merka_datums, piezime),
    )
    savienojums.commit()
    return iegut_panela_datus(savienojums, lietotaja_id)


def pievienot_atro_iemaksu(savienojums, lietotaja_id, dati):
    rinda = _iegut_plana_rindu(savienojums, lietotaja_id)
    if rinda is None:
        raise ValidacijasKluda("Vispirms saglabā mērķi, tad lieto ātro iemaksu.")

    summa = _pieprasit_summu(dati.get("summa"), "ātrās iemaksas summu", "Ātrās iemaksas summai", atlaut_nulli=False)
    jaunais_atlikums = round(float(rinda["pasreizejais_atlikums"]) + summa, 2)

    savienojums.execute(
        "UPDATE krajsanas_plani SET pasreizejais_atlikums = ?, atjauninats_laiks = CURRENT_TIMESTAMP WHERE lietotaja_id = ?",
        (jaunais_atlikums, lietotaja_id),
    )
    savienojums.commit()
    return iegut_panela_datus(savienojums, lietotaja_id)


def iegut_panela_datus(savienojums, lietotaja_id):
    rinda = _iegut_plana_rindu(savienojums, lietotaja_id)
    return _uzbuvet_panela_datus(rinda)


def _iegut_plana_rindu(savienojums, lietotaja_id):
    return savienojums.execute(
        """
        SELECT lietotaja_id, merka_nosaukums, merka_summa, pasreizejais_atlikums,
               ikmenesa_iemaksa, merka_datums, piezime, atjauninats_laiks
        FROM krajsanas_plani WHERE lietotaja_id = ?
        """,
        (lietotaja_id,),
    ).fetchone()


def _uzbuvet_panela_datus(rinda):
    sodiena = date.today()
    merka_nosaukums = rinda["merka_nosaukums"] if rinda else ""
    merka_summa = round(float(rinda["merka_summa"]), 2) if rinda else 0.0
    pasreizejais_atlikums = round(float(rinda["pasreizejais_atlikums"]), 2) if rinda else 0.0
    ikmenesa_iemaksa = round(float(rinda["ikmenesa_iemaksa"]), 2) if rinda else 0.0
    merka_datums = rinda["merka_datums"] if rinda else ""
    piezime = rinda["piezime"] if rinda else ""
    atjauninats_laiks = rinda["atjauninats_laiks"] if rinda else None

    if merka_summa <= 0:
        return {
            "irSaglabatsPlans": False,
            "merkaNosaukums": merka_nosaukums,
            "merkaSumma": merka_summa,
            "pasreizejaisAtlikums": pasreizejais_atlikums,
            "ikmenesaIemaksa": ikmenesa_iemaksa,
            "merkaDatums": merka_datums,
            "piezime": piezime,
            "atlikusiSumma": 0.0,
            "progresaProcenti": 0.0,
            "redzamieProgresaProcenti": 0.0,
            "nepieciesamaIkmenesaIemaksa": None,
            "statusaUzraksts": "Gaida ievadi",
            "statusaTonis": "mierigs",
            "prognozesTeksts": "Ievadi mērķi un pašreizējo atlikumu, lai redzētu progresu.",
            "terminaTeksts": "Ikmēneša iemaksa palīdz saprast, kad vari tikt līdz mērķim.",
            "nakamaPosmaTeksts": "Pirmais progresa posms parādīsies pēc plāna saglabāšanas.",
            "dienasLidzMerkim": None,
            "progresaPosmi": _uzbuvet_progresa_posmus(0.0),
            "atrasIemaksasSummas": ATRAS_IEMAKSAS_SUMMAS,
            "atjauninatsLaiks": atjauninats_laiks,
        }

    plans = izveidot_planu(
        merka_nosaukums=merka_nosaukums,
        merka_summa=merka_summa,
        pasreizejais_atlikums=pasreizejais_atlikums,
        ikmenesa_iemaksa=ikmenesa_iemaksa,
        merka_datums=merka_datums or None,
        piezime=piezime,
    )

    ir_termines = bool(merka_datums)
    statusa_uzraksts = plans.statusa_uzraksts(sodiena) if ir_termines else plans.statusa_uzraksts()
    statusa_tonis = plans.statusa_tonis(sodiena) if ir_termines else plans.statusa_tonis()
    dienas_lidz_merkim = plans.dienas_lidz_merkim(sodiena) if ir_termines else None
    nepieciesama_ikmenesa_iemaksa = plans.nepieciesama_ikmenesa_iemaksa(sodiena) if ir_termines else None

    if ir_termines:
        if plans.ir_sasniegts:
            termina_teksts = "Mērķa datums tev vairs nav šķērslis. Smuki."
        elif dienas_lidz_merkim < 0:
            termina_teksts = "Tavs mērķa datums jau ir pagājis. Pabīdi to vai palielini krāšanas tempu."
        else:
            termina_teksts = f"Lai paspētu līdz datumam, tev vajag apmēram {_formatet_valutu(nepieciesama_ikmenesa_iemaksa)} mēnesī."
    else:
        termina_teksts = plans.termina_teksts()

    progresa_procenti = plans.progresa_procenti
    nakamais_posms = next((vertiba for vertiba in PROGRESA_POSMI if progresa_procenti < vertiba), None)
    nakama_posma_teksts = (
        "Visi progresa posmi ir sasniegti." if nakamais_posms is None
        else f"Nākamais posms ir {nakamais_posms}%."
    )

    return {
        "irSaglabatsPlans": True,
        "merkaNosaukums": merka_nosaukums,
        "merkaSumma": merka_summa,
        "pasreizejaisAtlikums": pasreizejais_atlikums,
        "ikmenesaIemaksa": ikmenesa_iemaksa,
        "merkaDatums": merka_datums,
        "piezime": piezime,
        "atlikusiSumma": plans.atlikusi_summa,
        "progresaProcenti": progresa_procenti,
        "redzamieProgresaProcenti": plans.redzamie_progresa_procenti,
        "nepieciesamaIkmenesaIemaksa": nepieciesama_ikmenesa_iemaksa,
        "statusaUzraksts": statusa_uzraksts,
        "statusaTonis": statusa_tonis,
        "prognozesTeksts": plans.prognozes_teksts(),
        "terminaTeksts": termina_teksts,
        "nakamaPosmaTeksts": nakama_posma_teksts,
        "dienasLidzMerkim": dienas_lidz_merkim,
        "progresaPosmi": _uzbuvet_progresa_posmus(progresa_procenti),
        "atrasIemaksasSummas": ATRAS_IEMAKSAS_SUMMAS,
        "atjauninatsLaiks": atjauninats_laiks,
    }


def _uzbuvet_progresa_posmus(progresa_procenti):
    return [
        {"etikete": f"{vertiba}%", "sasniegts": progresa_procenti >= vertiba}
        for vertiba in PROGRESA_POSMI
    ]


def _serializet_lietotaju(rinda):
    return {
        "id": rinda["id"],
        "lietotajvards": rinda["lietotajvards"],
        "izveidotsLaiks": rinda["izveidots_laiks"],
    }


def _pieprasit_lietotajvardu(vertiba):
    lietotajvards = (vertiba or "").strip()
    if len(lietotajvards) < 3:
        raise ValidacijasKluda("Lietotājvārdam jābūt vismaz 3 simbolus garam.")
    if len(lietotajvards) > 24:
        raise ValidacijasKluda("Lietotājvārdam jābūt ne garākam par 24 simboliem.")
    if re.fullmatch(r"[A-Za-z0-9_]+", lietotajvards) is None:
        raise ValidacijasKluda("Lietotājvārdā drīkst lietot tikai burtus, ciparus un apakšsvītru.")
    return lietotajvards


def _pieprasit_paroli(parole, apstiprinajums):
    vertiba = parole or ""
    if len(vertiba) < 6:
        raise ValidacijasKluda("Parolei jābūt vismaz 6 simbolus garai.")
    if apstiprinajums != vertiba:
        raise ValidacijasKluda("Paroles nesakrīt.")
    return vertiba


def _pieprasit_merka_nosaukumu(vertiba):
    merka_nosaukums = (vertiba or "").strip()
    if not merka_nosaukums:
        raise ValidacijasKluda("Mērķa nosaukums ir obligāts.")
    if len(merka_nosaukums) > 60:
        raise ValidacijasKluda("Mērķa nosaukumam jābūt īsākam par 60 simboliem.")
    return merka_nosaukums


def _pieprasit_summu(vertiba, ievades_nosaukums, lauka_nosaukums, atlaut_nulli):
    neapstradata = "" if vertiba is None else str(vertiba).strip()
    if neapstradata == "":
        raise ValidacijasKluda(f"Ievadi {ievades_nosaukums}.")
    try:
        summa = round(float(neapstradata), 2)
    except ValueError as kluda:
        raise ValidacijasKluda(f"Ievadi korektu {ievades_nosaukums}.") from kluda

    mazaka = 0.0 if atlaut_nulli else 0.01
    if summa < mazaka or (not atlaut_nulli and summa == 0):
        salidzinajums = "0 vai lielākai" if atlaut_nulli else "lielākai par 0"
        raise ValidacijasKluda(f"{lauka_nosaukums} jābūt {salidzinajums}.")
    return summa


def _neobligats_datums(vertiba):
    neapstradata = (vertiba or "").strip()
    if not neapstradata:
        return None
    try:
        date.fromisoformat(neapstradata)
    except ValueError as kluda:
        raise ValidacijasKluda("Ievadi korektu mērķa datumu.") from kluda
    return neapstradata


# =============================================================================
# 5. FLASK APLIKĀCIJA UN MARŠRUTI
# =============================================================================

def _novirzit_ar_pazinojumu(marsruts, pazinojums, limenis="success", **vertibas):
    vertibas["pazinojums"] = pazinojums
    vertibas["pazinojuma_limenis"] = limenis
    return redirect(url_for(marsruts, **vertibas))


def _neautorizeta_atbilde():
    pazinojums = "Sesija beidzās. Ieej vēlreiz."
    if flask_request.path.startswith("/api/"):
        return jsonify({"statuss": "error", "kluda": "nav_autorizets", "pazinojums": pazinojums}), 401
    return _novirzit_ar_pazinojumu("ieeja", pazinojums, "error")


def _ieeja_nepieciesama(skats):
    @wraps(skats)
    def ietinais_skats(*args, **kwargs):
        lietotaja_id = session.get("lietotaja_id")
        if lietotaja_id is None:
            return _neautorizeta_atbilde()
        if iegut_lietotaju_pec_id(iegut_datubazi(), lietotaja_id) is None:
            session.clear()
            return _neautorizeta_atbilde()
        return skats(*args, **kwargs)
    return ietinais_skats


lietotne = Flask(__name__, template_folder="templates", static_folder="static")
lietotne.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "development-secret-key"),
    DATABASE=str(NOKLUSETA_DATUBAZE),
)
inicializet_datubazi(lietotne.config["DATABASE"])
lietotne.teardown_appcontext(aizvert_datubazi)


@lietotne.get("/")
def sakums():
    if session.get("lietotaja_id"):
        return redirect(url_for("panelis"))
    return redirect(url_for("ieeja"))


@lietotne.route("/registracija", methods=["GET", "POST"])
def registracija():
    if session.get("lietotaja_id"):
        return redirect(url_for("panelis"))
    if flask_request.method == "POST":
        try:
            lietotajs = registret_lietotaju(iegut_datubazi(), flask_request.form)
            return _novirzit_ar_pazinojumu(
                "ieeja", "Konts izveidots. Tagad vari ieiet.", "success",
                lietotajvards=lietotajs["lietotajvards"],
            )
        except ValidacijasKluda as kluda:
            return _novirzit_ar_pazinojumu("registracija", str(kluda), "error")
    return render_template("register.html")


@lietotne.route("/ieeja", methods=["GET", "POST"])
def ieeja():
    if session.get("lietotaja_id"):
        return redirect(url_for("panelis"))
    if flask_request.method == "POST":
        try:
            lietotajs = autentificet_lietotaju(iegut_datubazi(), flask_request.form)
            session.clear()
            session["lietotaja_id"] = lietotajs["id"]
            return _novirzit_ar_pazinojumu("panelis", "Prieks redzēt atkal.", "success")
        except AutentifikacijasKluda as kluda:
            lietotajvards = (flask_request.form.get("lietotajvards") or "").strip()
            return _novirzit_ar_pazinojumu("ieeja", str(kluda), "error", lietotajvards=lietotajvards)
    return render_template("login.html")


@lietotne.route("/iziet", methods=["GET", "POST"])
def iziet():
    session.clear()
    return _novirzit_ar_pazinojumu("ieeja", "Tu esi izrakstījies.", "success")


@lietotne.route("/panelis", methods=["GET", "POST"])
@_ieeja_nepieciesama
def panelis():
    if flask_request.method == "POST":
        try:
            saglabat_krajsanas_planu(iegut_datubazi(), session["lietotaja_id"], flask_request.form)
            return _novirzit_ar_pazinojumu("panelis", "Tavs krājuma plāns ir atjaunināts.", "success")
        except ValidacijasKluda as kluda:
            return _novirzit_ar_pazinojumu("panelis", str(kluda), "error")
    return render_template("dashboard.html")


@lietotne.post("/panelis/atra-iemaksa")
@_ieeja_nepieciesama
def atra_iemaksa():
    try:
        pievienot_atro_iemaksu(iegut_datubazi(), session["lietotaja_id"], flask_request.form)
        return _novirzit_ar_pazinojumu("panelis", "Pašreizējais atlikums atjaunināts.", "success")
    except ValidacijasKluda as kluda:
        return _novirzit_ar_pazinojumu("panelis", str(kluda), "error")


@lietotne.get("/api/panela-dati")
@_ieeja_nepieciesama
def api_panela_dati():
    lietotajs = iegut_lietotaju_pec_id(iegut_datubazi(), session["lietotaja_id"])
    panela_dati = iegut_panela_datus(iegut_datubazi(), session["lietotaja_id"])
    return jsonify({**panela_dati, "lietotajvards": lietotajs["lietotajvards"]})


@lietotne.get("/api/valuta")
@_ieeja_nepieciesama
def api_valuta():
    no_valutas = flask_request.args.get("no", "EUR")
    uz_valutu = flask_request.args.get("uz", "USD")
    summa_teksts = flask_request.args.get("summa", "0")

    try:
        summa = float(summa_teksts)
    except ValueError:
        return jsonify({"statuss": "error", "pazinojums": "Ievadi derīgu summu."}), 400

    try:
        konvertets = konvertet_summu(summa, no_valutas, uz_valutu)
    except ValutasKluda as kluda:
        return jsonify({"statuss": "error", "pazinojums": str(kluda)}), 502

    return jsonify({
        "statuss": "ok",
        "no": no_valutas.upper(),
        "uz": uz_valutu.upper(),
        "summa": summa,
        "konvertets": konvertets,
        "atlautasValutas": list(ATLAUTAS_VALUTAS),
    })


@lietotne.get("/panelis/eksports.csv")
@_ieeja_nepieciesama
def eksportet_csv():
    panela_dati = iegut_panela_datus(iegut_datubazi(), session["lietotaja_id"])
    lietotajs = iegut_lietotaju_pec_id(iegut_datubazi(), session["lietotaja_id"])

    buferis = io.StringIO()
    rakstitajs = csv.writer(buferis, delimiter=";")
    rakstitajs.writerow(["Lauks", "Vērtība"])
    rakstitajs.writerow(["Lietotājvārds", lietotajs["lietotajvards"]])
    rakstitajs.writerow(["Mērķa nosaukums", panela_dati["merkaNosaukums"]])
    rakstitajs.writerow(["Mērķa summa (EUR)", panela_dati["merkaSumma"]])
    rakstitajs.writerow(["Pašreizējais atlikums (EUR)", panela_dati["pasreizejaisAtlikums"]])
    rakstitajs.writerow(["Atlikusī summa (EUR)", panela_dati["atlikusiSumma"]])
    rakstitajs.writerow(["Progress (%)", panela_dati["progresaProcenti"]])
    rakstitajs.writerow(["Ikmēneša iemaksa (EUR)", panela_dati["ikmenesaIemaksa"]])
    rakstitajs.writerow(["Mērķa datums", panela_dati["merkaDatums"] or ""])
    rakstitajs.writerow(["Statuss", panela_dati["statusaUzraksts"]])
    rakstitajs.writerow(["Piezīme", panela_dati["piezime"]])

    atbilde = Response(buferis.getvalue(), mimetype="text/csv; charset=utf-8")
    atbilde.headers["Content-Disposition"] = "attachment; filename=krajsanas_plans.csv"
    return atbilde


@lietotne.get("/veseliba")
def veseliba():
    return {"statuss": "ok"}


if __name__ == "__main__":
    print("Atver http://127.0.0.1:5000/ pārlūkā. Neatver templates mapes failus pa tiešo.")
    lietotne.run(debug=True)
