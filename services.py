from __future__ import annotations

from datetime import date
import math
import re

from werkzeug.security import check_password_hash, generate_password_hash


PROGRESA_POSMI = (25, 50, 75, 100)
ATRAS_IEMAKSAS_SUMMAS = (10, 25, 50)


def _formatet_valutu(vertiba):
    summa = float(vertiba or 0)
    veselie, dalas = f"{summa:,.2f}".split(".")
    return f"{veselie.replace(',', ' ')},{dalas} €"


class ValidacijasKluda(ValueError):
    pass


class AutentifikacijasKluda(ValueError):
    pass


def registret_lietotaju(savienojums, dati):
    lietotajvards = _pieprasit_lietotajvardu(dati.get("lietotajvards"))
    parole = _pieprasit_paroli(
        dati.get("parole"),
        dati.get("paroles_apstiprinajums") or dati.get("parolesApstiprinajums"),
    )

    esosais = savienojums.execute(
        "SELECT id FROM lietotaji WHERE lietotajvards = ?",
        (lietotajvards,),
    ).fetchone()
    if esosais is not None:
        raise ValidacijasKluda("Šis lietotājvārds jau ir aizņemts.")

    kursors = savienojums.execute(
        """
        INSERT INTO lietotaji (lietotajvards, paroles_jaukums)
        VALUES (?, ?)
        """,
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
        """
        SELECT id, lietotajvards, paroles_jaukums, izveidots_laiks
        FROM lietotaji
        WHERE lietotajvards = ?
        """,
        (lietotajvards,),
    ).fetchone()
    if rinda is None or not check_password_hash(rinda["paroles_jaukums"], parole):
        raise AutentifikacijasKluda("Nepareizs lietotājvārds vai parole.")

    return _serializet_lietotaju(rinda)


def iegut_lietotaju_pec_id(savienojums, lietotaja_id):
    rinda = savienojums.execute(
        """
        SELECT id, lietotajvards, izveidots_laiks
        FROM lietotaji
        WHERE id = ?
        """,
        (lietotaja_id,),
    ).fetchone()
    if rinda is None:
        return None
    return _serializet_lietotaju(rinda)


def iegut_panela_datus(savienojums, lietotaja_id):
    rinda = _iegut_plana_rindu(savienojums, lietotaja_id)
    return _uzbuvet_panela_datus(rinda)


def saglabat_krajsanas_planu(savienojums, lietotaja_id, dati):
    merka_nosaukums = _pieprasit_merka_nosaukumu(dati.get("merka_nosaukums"))
    merka_summa = _pieprasit_summu(
        dati.get("merka_summa"),
        "mērķa summu",
        "Mērķa summai",
        atlaut_nulli=False,
    )
    pasreizejais_atlikums = _pieprasit_summu(
        dati.get("pasreizejais_atlikums"),
        "pašreizējo atlikumu",
        "Pašreizējam atlikumam",
        atlaut_nulli=True,
    )
    ikmenesa_iemaksa = _pieprasit_summu(
        dati.get("ikmenesa_iemaksa"),
        "ikmēneša iemaksu",
        "Ikmēneša iemaksai",
        atlaut_nulli=True,
    )
    merka_datums = _neobligats_datums(dati.get("merka_datums"))
    piezime = _notirit_piezimi(dati.get("piezime"))

    savienojums.execute(
        """
        INSERT INTO krajsanas_plani (
            lietotaja_id,
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            merka_datums,
            piezime
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
        (
            lietotaja_id,
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            merka_datums,
            piezime,
        ),
    )
    savienojums.commit()
    return iegut_panela_datus(savienojums, lietotaja_id)


def pievienot_atro_iemaksu(savienojums, lietotaja_id, dati):
    rinda = _iegut_plana_rindu(savienojums, lietotaja_id)
    if rinda is None:
        raise ValidacijasKluda("Vispirms saglabā mērķi, tad lieto ātro iemaksu.")

    summa = _pieprasit_summu(
        dati.get("summa"),
        "ātrās iemaksas summu",
        "Ātrās iemaksas summai",
        atlaut_nulli=False,
    )
    jaunais_atlikums = round(float(rinda["pasreizejais_atlikums"]) + summa, 2)

    savienojums.execute(
        """
        UPDATE krajsanas_plani
        SET pasreizejais_atlikums = ?, atjauninats_laiks = CURRENT_TIMESTAMP
        WHERE lietotaja_id = ?
        """,
        (jaunais_atlikums, lietotaja_id),
    )
    savienojums.commit()
    return iegut_panela_datus(savienojums, lietotaja_id)


def _iegut_plana_rindu(savienojums, lietotaja_id):
    return savienojums.execute(
        """
        SELECT
            lietotaja_id,
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            merka_datums,
            piezime,
            atjauninats_laiks
        FROM krajsanas_plani
        WHERE lietotaja_id = ?
        """,
        (lietotaja_id,),
    ).fetchone()


def _uzbuvet_panela_datus(rinda):
    sodiena = date.today()
    ir_saglabats_plans = rinda is not None
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

    atlikusi_summa = round(max(merka_summa - pasreizejais_atlikums, 0), 2)
    progresa_procenti = round((pasreizejais_atlikums / merka_summa) * 100, 1)
    redzamie_progresa_procenti = min(progresa_procenti, 100.0)
    nepieciesama_ikmenesa_iemaksa = None
    dienas_lidz_merkim = None
    statusa_uzraksts = "Brīvāks temps"
    statusa_tonis = "mierigs"
    termina_teksts = "Pievieno mērķa datumu, lai redzētu, vai tavs mēneša plāns ir pietiekams."

    if atlikusi_summa <= 0:
        prognozes_teksts = "Tu šo mērķi jau esi sasniedzis."
        statusa_uzraksts = "Mērķis sasniegts"
        statusa_tonis = "labs"
        termina_teksts = "Viss pēc šī punkta jau ir ekstra rezerve."
    elif ikmenesa_iemaksa > 0:
        menesi_lidz_merkim = max(math.ceil(atlikusi_summa / ikmenesa_iemaksa), 1)
        menesa_vards = "mēnesi" if menesi_lidz_merkim == 1 else "mēnešus"
        prognozes_teksts = f"Ar pašreizējo tempu tev vajadzēs vēl apmēram {menesi_lidz_merkim} {menesa_vards}."
    else:
        prognozes_teksts = "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku."

    if merka_datums:
        merka_datuma_vertiba = date.fromisoformat(merka_datums)
        dienas_lidz_merkim = (merka_datuma_vertiba - sodiena).days

        if atlikusi_summa <= 0:
            statusa_uzraksts = "Mērķis sasniegts"
            statusa_tonis = "labs"
            nepieciesama_ikmenesa_iemaksa = 0.0
            termina_teksts = "Mērķa datums tev vairs nav šķērslis. Smuki."
        elif dienas_lidz_merkim < 0:
            statusa_uzraksts = "Datums ir garām"
            statusa_tonis = "trauksme"
            termina_teksts = "Tavs mērķa datums jau ir pagājis. Pabīdi to vai palielini krāšanas tempu."
        else:
            menesi_lidz_merka_datumam = max(dienas_lidz_merkim / 30.44, 0.1)
            nepieciesama_ikmenesa_iemaksa = round(atlikusi_summa / menesi_lidz_merka_datumam, 2)
            termina_teksts = (
                "Lai paspētu līdz datumam, tev vajag apmēram "
                f"{_formatet_valutu(nepieciesama_ikmenesa_iemaksa)} mēnesī."
            )
            if ikmenesa_iemaksa <= 0:
                statusa_uzraksts = "Nav mēneša plāna"
                statusa_tonis = "bridinajums"
            elif ikmenesa_iemaksa + 0.009 >= nepieciesama_ikmenesa_iemaksa:
                statusa_uzraksts = "Viss iet labi"
                statusa_tonis = "labs"
            else:
                statusa_uzraksts = "Jāpiespiež vairāk"
                statusa_tonis = "bridinajums"

    nakamais_posms = next((vertiba for vertiba in PROGRESA_POSMI if progresa_procenti < vertiba), None)
    if nakamais_posms is None:
        nakama_posma_teksts = "Visi progresa posmi ir sasniegti."
    else:
        nakama_posma_teksts = f"Nākamais posms ir {nakamais_posms}%."

    return {
        "irSaglabatsPlans": ir_saglabats_plans,
        "merkaNosaukums": merka_nosaukums,
        "merkaSumma": merka_summa,
        "pasreizejaisAtlikums": pasreizejais_atlikums,
        "ikmenesaIemaksa": ikmenesa_iemaksa,
        "merkaDatums": merka_datums,
        "piezime": piezime,
        "atlikusiSumma": atlikusi_summa,
        "progresaProcenti": progresa_procenti,
        "redzamieProgresaProcenti": redzamie_progresa_procenti,
        "nepieciesamaIkmenesaIemaksa": nepieciesama_ikmenesa_iemaksa,
        "statusaUzraksts": statusa_uzraksts,
        "statusaTonis": statusa_tonis,
        "prognozesTeksts": prognozes_teksts,
        "terminaTeksts": termina_teksts,
        "nakamaPosmaTeksts": nakama_posma_teksts,
        "dienasLidzMerkim": dienas_lidz_merkim,
        "progresaPosmi": _uzbuvet_progresa_posmus(progresa_procenti),
        "atrasIemaksasSummas": ATRAS_IEMAKSAS_SUMMAS,
        "atjauninatsLaiks": atjauninats_laiks,
    }


def _uzbuvet_progresa_posmus(progresa_procenti):
    return [
        {
            "etikete": f"{vertiba}%",
            "sasniegts": progresa_procenti >= vertiba,
        }
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
    neapstradata_vertiba = "" if vertiba is None else str(vertiba).strip()
    if neapstradata_vertiba == "":
        raise ValidacijasKluda(f"Ievadi {ievades_nosaukums}.")

    try:
        summa = round(float(neapstradata_vertiba), 2)
    except ValueError as kluda:
        raise ValidacijasKluda(f"Ievadi korektu {ievades_nosaukums}.") from kluda

    mazaka_atlauta_vertiba = 0.0 if atlaut_nulli else 0.01
    if summa < mazaka_atlauta_vertiba or (not atlaut_nulli and summa == 0):
        salidzinajums = "0 vai lielākai" if atlaut_nulli else "lielākai par 0"
        raise ValidacijasKluda(f"{lauka_nosaukums} jābūt {salidzinajums}.")
    return summa


def _neobligats_datums(vertiba):
    neapstradata_vertiba = (vertiba or "").strip()
    if not neapstradata_vertiba:
        return None

    try:
        date.fromisoformat(neapstradata_vertiba)
    except ValueError as kluda:
        raise ValidacijasKluda("Ievadi korektu mērķa datumu.") from kluda
    return neapstradata_vertiba


def _notirit_piezimi(vertiba):
    piezime = (vertiba or "").strip()
    return piezime[:240]
