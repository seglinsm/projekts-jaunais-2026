import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import izveidot_lietotni


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
        self.assertNotIn("Ceļojums uz Itāliju", skripts)

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


if __name__ == "__main__":
    unittest.main()
