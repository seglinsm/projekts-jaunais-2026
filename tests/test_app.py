import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import izveidot_lietotni
from models import (
    BazesKrajsanasPlans,
    RegularsKrajsanasPlans,
    TerminetsKrajsanasPlans,
    izveidot_planu,
)
import valutas_serviss
from valutas_serviss import ValutasKluda, iztirit_kesu, konvertet_summu


class GoalBloomTesti(unittest.TestCase):
    def setUp(self):
        faila_aprakstits, self.datubazes_cels = tempfile.mkstemp(suffix=".db")
        os.close(faila_aprakstits)
        self.lietotne = izveidot_lietotni(
            {
                "TESTING": True,
                "DATABASE": self.datubazes_cels,
                "SECRET_KEY": "test-secret",
            }
        )
        self.klients = self.lietotne.test_client()

    def tearDown(self):
        if os.path.exists(self.datubazes_cels):
            os.remove(self.datubazes_cels)

    def test_panelis_novirza_viesus_uz_ieeju(self):
        atbilde = self.klients.get("/panelis")
        self.assertEqual(atbilde.status_code, 302)
        self.assertIn("/ieeja", atbilde.headers["Location"])

    def test_api_panela_dati_viesiem_atgriez_401_json(self):
        atbilde = self.klients.get("/api/panela-dati")
        saturs = atbilde.get_json()

        self.assertEqual(atbilde.status_code, 401)
        self.assertEqual(saturs["statuss"], "error")
        self.assertEqual(saturs["kluda"], "nav_autorizets")
        self.assertEqual(saturs["pazinojums"], "Sesija beidzās. Ieej vēlreiz.")

    def test_lietotajs_var_registreties_ieiet_un_iziet(self):
        registracijas_atbilde = self.klients.post(
            "/registracija",
            data={
                "lietotajvards": "demo_user",
                "parole": "secret123",
                "paroles_apstiprinajums": "secret123",
            },
        )
        self.assertEqual(registracijas_atbilde.status_code, 302)
        self.assertIn("/ieeja?", registracijas_atbilde.headers["Location"])

        ieejas_atbilde = self.klients.post(
            "/ieeja",
            data={
                "lietotajvards": "demo_user",
                "parole": "secret123",
            },
        )
        self.assertEqual(ieejas_atbilde.status_code, 302)
        self.assertIn("/panelis?", ieejas_atbilde.headers["Location"])

        panela_atbilde = self.klients.get("/panelis")
        panela_html = panela_atbilde.get_data(as_text=True)
        self.assertEqual(panela_atbilde.status_code, 200)
        self.assertIn("Tavs mērķa nosaukums", panela_html)
        self.assertIn("../static/dashboard.js", panela_html)

        iziesanas_atbilde = self.klients.post("/iziet")
        self.assertEqual(iziesanas_atbilde.status_code, 302)
        self.assertIn("/ieeja?", iziesanas_atbilde.headers["Location"])

    def test_api_panela_dati_notira_nederigu_sesiju(self):
        self._registret_un_ieiet()

        with self.klients.session_transaction() as sesija:
            sesija["lietotaja_id"] = 999999

        atbilde = self.klients.get("/api/panela-dati")
        saturs = atbilde.get_json()

        self.assertEqual(atbilde.status_code, 401)
        self.assertEqual(saturs["kluda"], "nav_autorizets")

        with self.klients.session_transaction() as sesija:
            self.assertNotIn("lietotaja_id", sesija)

    def test_lietotajs_var_saglabat_planu_un_izmantot_atro_iemaksu(self):
        self._registret_un_ieiet()

        saglabasanas_atbilde = self.klients.post(
            "/panelis",
            data={
                "merka_nosaukums": "Drošības spilvens",
                "merka_summa": "1000",
                "pasreizejais_atlikums": "400",
                "ikmenesa_iemaksa": "125",
                "merka_datums": "",
                "piezime": "Trīs mēnešu izdevumiem.",
            },
        )
        self.assertEqual(saglabasanas_atbilde.status_code, 302)
        self.assertIn("/panelis?", saglabasanas_atbilde.headers["Location"])

        datu_atbilde = self.klients.get("/api/panela-dati")
        saturs = datu_atbilde.get_json()
        self.assertEqual(datu_atbilde.status_code, 200)
        self.assertEqual(saturs["merkaNosaukums"], "Drošības spilvens")
        self.assertEqual(saturs["progresaProcenti"], 40.0)
        self.assertEqual(saturs["piezime"], "Trīs mēnešu izdevumiem.")
        self.assertEqual(saturs["statusaUzraksts"], "Brīvāks temps")

        atras_iemaksas_atbilde = self.klients.post("/panelis/atra-iemaksa", data={"summa": "25"})
        self.assertEqual(atras_iemaksas_atbilde.status_code, 302)
        self.assertIn("/panelis?", atras_iemaksas_atbilde.headers["Location"])

        atjaunoto_datu_atbilde = self.klients.get("/api/panela-dati")
        atjaunotais_saturs = atjaunoto_datu_atbilde.get_json()
        self.assertEqual(atjaunotais_saturs["pasreizejaisAtlikums"], 425.0)
        self.assertEqual(atjaunotais_saturs["progresaProcenti"], 42.5)

        savienojums = sqlite3.connect(self.datubazes_cels)
        rinda = savienojums.execute(
            """
            SELECT merka_nosaukums, pasreizejais_atlikums, ikmenesa_iemaksa
            FROM krajsanas_plani
            """
        ).fetchone()
        savienojums.close()

        self.assertEqual(rinda[0], "Drošības spilvens")
        self.assertEqual(rinda[1], 425.0)
        self.assertEqual(rinda[2], 125.0)

    def test_attelotaja_paneli_nav_neapstradatu_jinja_tekstu(self):
        self._registret_un_ieiet()

        atbilde = self.klients.get("/panelis")
        html = atbilde.get_data(as_text=True)

        self.assertEqual(atbilde.status_code, 200)
        self.assertNotIn("{{", html)
        self.assertNotIn("{%", html)
        self.assertIn("../static/style.css", html)
        self.assertIn("../static/dashboard.js", html)

    def test_panelis_pec_noklusejuma_izmanto_tuksus_vietturus(self):
        self._registret_un_ieiet()

        atbilde = self.klients.get("/panelis")
        html = atbilde.get_data(as_text=True)

        self.assertEqual(atbilde.status_code, 200)
        self.assertIn('placeholder="Tavs mērķa nosaukums"', html)
        self.assertIn('placeholder="Tava gala summa"', html)
        self.assertIn('placeholder="Tavs pašreizējais atlikums"', html)
        self.assertIn('placeholder="Tava ikmēneša iemaksa"', html)
        self.assertIn(">Tava gala summa<", html)
        self.assertIn(">Tavs atlikums<", html)
        self.assertNotIn("Drošības spilvens", html)
        self.assertNotIn('placeholder="5000"', html)

    def test_prieksskata_panela_dati_paliek_tuksi(self):
        skripta_cels = Path(__file__).resolve().parent.parent / "static" / "dashboard.js"
        skripts = skripta_cels.read_text(encoding="utf-8")

        self.assertIn("const PREVIEW_DATA = {", skripts)
        self.assertIn("irSaglabatsPlans: false", skripts)
        self.assertIn('merkaNosaukums: ""', skripts)
        self.assertIn('merkaSumma: ""', skripts)
        self.assertIn('statusaUzraksts: "Gaida ievadi"', skripts)
        self.assertIn("if (response.status === 401)", skripts)
        self.assertIn('showFlash("error"', skripts)
        self.assertNotIn("Ceļojums uz Itāliju", skripts)

    def test_csv_eksports_atgriez_csv_ar_planu(self):
        self._registret_un_ieiet()
        self.klients.post(
            "/panelis",
            data={
                "merka_nosaukums": "Ceļojums",
                "merka_summa": "500",
                "pasreizejais_atlikums": "100",
                "ikmenesa_iemaksa": "50",
                "merka_datums": "",
                "piezime": "",
            },
        )

        atbilde = self.klients.get("/panelis/eksports.csv")
        self.assertEqual(atbilde.status_code, 200)
        self.assertIn("text/csv", atbilde.headers["Content-Type"])
        self.assertIn("attachment", atbilde.headers["Content-Disposition"])

        saturs = atbilde.get_data(as_text=True)
        self.assertIn("Mērķa nosaukums;Ceļojums", saturs)
        self.assertIn("Progress (%);20.0", saturs)

    def test_valutas_api_atgriez_konvertetu_summu(self):
        self._registret_un_ieiet()
        iztirit_kesu()

        def viltus_urlopen(_url, timeout=None):  # noqa: ARG001
            atbilde = json.dumps({"rates": {"USD": 1.1}}).encode("utf-8")
            return _FiktivaAtbilde(atbilde)

        with patch("valutas_serviss.request.urlopen", side_effect=viltus_urlopen):
            atbilde = self.klients.get("/api/valuta?no=EUR&uz=USD&summa=100")

        dati = atbilde.get_json()
        self.assertEqual(atbilde.status_code, 200)
        self.assertEqual(dati["statuss"], "ok")
        self.assertEqual(dati["no"], "EUR")
        self.assertEqual(dati["uz"], "USD")
        self.assertAlmostEqual(dati["konvertets"], 110.0)

    def test_valutas_api_atgriez_kludu_ja_valuta_nepareiza(self):
        self._registret_un_ieiet()
        atbilde = self.klients.get("/api/valuta?no=EUR&uz=XXX&summa=10")
        self.assertEqual(atbilde.status_code, 502)
        self.assertEqual(atbilde.get_json()["statuss"], "error")

    def _registret_un_ieiet(self):
        self.klients.post(
            "/registracija",
            data={
                "lietotajvards": "demo_user",
                "parole": "secret123",
                "paroles_apstiprinajums": "secret123",
            },
        )
        self.klients.post(
            "/ieeja",
            data={
                "lietotajvards": "demo_user",
                "parole": "secret123",
            },
        )


class _FiktivaAtbilde:
    def __init__(self, saturs):
        self._buferis = io.BytesIO(saturs)

    def read(self):
        return self._buferis.read()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self._buferis.close()
        return False


class OOPModeluTesti(unittest.TestCase):
    def test_bazes_plans_rekina_progresa_procentus(self):
        plans = BazesKrajsanasPlans("Grāmata", 200, 50)
        self.assertEqual(plans.progresa_procenti, 25.0)
        self.assertEqual(plans.atlikusi_summa, 150.0)
        self.assertFalse(plans.ir_sasniegts)

    def test_regularais_plans_rekina_menesus_lidz_merkim(self):
        plans = RegularsKrajsanasPlans("Dators", 1000, 200, 100)
        self.assertEqual(plans.menesi_lidz_merkim(), 8)
        self.assertIn("mēnešus", plans.prognozes_teksts())

    def test_terminetais_plans_rekina_nepieciesamo_tempu(self):
        sodiena = date(2026, 1, 1)
        merka_datums = sodiena + timedelta(days=152)
        plans = TerminetsKrajsanasPlans("Atvaļinājums", 1000, 0, 50, merka_datums)

        nepieciesams = plans.nepieciesama_ikmenesa_iemaksa(sodiena)
        self.assertAlmostEqual(nepieciesams, 200.26, places=2)
        self.assertEqual(plans.statusa_uzraksts(sodiena), "Jāpiespiež vairāk")

    def test_terminetais_plans_pazino_par_datumu_garam(self):
        sodiena = date(2026, 5, 1)
        plans = TerminetsKrajsanasPlans("Kavēts", 500, 100, 50, sodiena - timedelta(days=1))
        self.assertEqual(plans.statusa_uzraksts(sodiena), "Datums ir garām")
        self.assertEqual(plans.statusa_tonis(sodiena), "trauksme")

    def test_fabrika_izvelas_pareizo_klasi(self):
        self.assertIsInstance(
            izveidot_planu("A", 100, 10),
            BazesKrajsanasPlans,
        )
        self.assertIsInstance(
            izveidot_planu("B", 100, 10, ikmenesa_iemaksa=5),
            RegularsKrajsanasPlans,
        )
        self.assertIsInstance(
            izveidot_planu("C", 100, 10, ikmenesa_iemaksa=5, merka_datums="2027-01-01"),
            TerminetsKrajsanasPlans,
        )


class ValutasServisaTesti(unittest.TestCase):
    def setUp(self):
        iztirit_kesu()

    def test_viena_valuta_atgriez_vienu(self):
        self.assertEqual(konvertet_summu(10, "EUR", "EUR"), 10.0)

    def test_nepareiza_valuta_izmet_kludu(self):
        with self.assertRaises(ValutasKluda):
            konvertet_summu(10, "EUR", "XYZ")

    def test_veiksmigs_konverts_izmanto_urlopen_atbildi(self):
        @contextmanager
        def viltus_urlopen(_url, timeout=None):  # noqa: ARG001
            yield _FiktivaAtbilde(json.dumps({"rates": {"GBP": 0.85}}).encode("utf-8"))

        with patch.object(valutas_serviss.request, "urlopen", viltus_urlopen):
            rezultats = konvertet_summu(100, "EUR", "GBP")
        self.assertAlmostEqual(rezultats, 85.0)

    def test_kesh_neveic_atkartotu_pieprasijumu(self):
        zvanu_skaitlis = {"vertiba": 0}

        @contextmanager
        def viltus_urlopen(_url, timeout=None):  # noqa: ARG001
            zvanu_skaitlis["vertiba"] += 1
            yield _FiktivaAtbilde(json.dumps({"rates": {"USD": 1.1}}).encode("utf-8"))

        with patch.object(valutas_serviss.request, "urlopen", viltus_urlopen):
            konvertet_summu(10, "EUR", "USD")
            konvertet_summu(20, "EUR", "USD")

        self.assertEqual(zvanu_skaitlis["vertiba"], 1)


if __name__ == "__main__":
    unittest.main()
