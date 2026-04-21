"""Ārēja API integrācija: valūtas kursi no Frankfurter (ECB dati).

Dokumentācija: https://www.frankfurter.app/docs/ — bezmaksas, bez atslēgas.
Servisa uzdevums: lietotājs redz savu EUR atlikumu citā valūtā, lai
salīdzinātu mērķa lielumu, ja mērķis ir saistīts ar ceļojumu vai ārzemju
pirkumu. Šī ir lietderīga papildu funkcija uzkrājumu lietotnei.
"""

from __future__ import annotations

import json
import time
from urllib import error, parse, request


FRANKFURTER_BAZE = "https://api.frankfurter.app/latest"
ATLAUTAS_VALUTAS = ("EUR", "USD", "GBP", "SEK", "NOK", "CHF", "PLN")
_MEMUARA_KESS_TTL_SEK = 300


class ValutasKluda(Exception):
    """Visu šī servisa kļūdu bāzes klase."""


class _AtminasKess:
    def __init__(self, dzives_ilgums_sek):
        self._dzives_ilgums_sek = dzives_ilgums_sek
        self._krajums = {}

    def iegut(self, atslega):
        ieraksts = self._krajums.get(atslega)
        if ieraksts is None:
            return None
        laiks, vertiba = ieraksts
        if time.monotonic() - laiks > self._dzives_ilgums_sek:
            self._krajums.pop(atslega, None)
            return None
        return vertiba

    def ielikt(self, atslega, vertiba):
        self._krajums[atslega] = (time.monotonic(), vertiba)

    def iztirit(self):
        self._krajums.clear()


_kess = _AtminasKess(_MEMUARA_KESS_TTL_SEK)


def iztirit_kesu():
    """Izmanto testos, lai katrs tests sāktos ar tīru kešu."""
    _kess.iztirit()


def iegut_valutas_kursu(no_valutas, uz_valutu, atversanas_funkcija=None):
    """Atgriež, cik vienību "uz_valutu" var saņemt par 1 vienību "no_valutas"."""
    no_valutas = _parbaudit_valutu(no_valutas)
    uz_valutu = _parbaudit_valutu(uz_valutu)

    if no_valutas == uz_valutu:
        return 1.0

    kesa_atslega = f"{no_valutas}->{uz_valutu}"
    kesa_vertiba = _kess.iegut(kesa_atslega)
    if kesa_vertiba is not None:
        return kesa_vertiba

    vaicajuma_virkne = parse.urlencode({"from": no_valutas, "to": uz_valutu})
    url = f"{FRANKFURTER_BAZE}?{vaicajuma_virkne}"
    atversanas_funkcija = atversanas_funkcija or request.urlopen

    try:
        with atversanas_funkcija(url, timeout=5) as atbilde:
            neapstradats = atbilde.read().decode("utf-8")
    except (error.URLError, TimeoutError, OSError) as kluda:
        raise ValutasKluda("Nevar sazināties ar valūtas kursu pakalpojumu.") from kluda

    try:
        dati = json.loads(neapstradats)
    except ValueError as kluda:
        raise ValutasKluda("Valūtas kursu atbilde nav derīgs JSON.") from kluda

    kurss = _izvilkt_kursu(dati, uz_valutu)
    _kess.ielikt(kesa_atslega, kurss)
    return kurss


def konvertet_summu(summa, no_valutas, uz_valutu, atversanas_funkcija=None):
    """Konvertē summu starp divām valūtām un atgriež noapaļotu rezultātu."""
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


def _izvilkt_kursu(dati, uz_valutu):
    kursi = dati.get("rates") if isinstance(dati, dict) else None
    if not isinstance(kursi, dict) or uz_valutu not in kursi:
        raise ValutasKluda("Valūtas kursu atbildē nav vajadzīgo datu.")
    try:
        return float(kursi[uz_valutu])
    except (TypeError, ValueError) as kluda:
        raise ValutasKluda("Valūtas kursu atbildē ir nederīga vērtība.") from kluda
