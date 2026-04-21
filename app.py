import csv
import io
import os
from functools import wraps

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

from database import (
    NOKLUSETA_DATUBAZE,
    iegut_datubazi,
    inicializet_datubazi,
    inicializet_lietotni as inicializet_datubazes_lietotni,
)
from services import (
    AutentifikacijasKluda,
    ValidacijasKluda,
    autentificet_lietotaju,
    iegut_lietotaju_pec_id,
    iegut_panela_datus,
    pievienot_atro_iemaksu,
    registret_lietotaju,
    saglabat_krajsanas_planu,
)
from valutas_serviss import ATLAUTAS_VALUTAS, ValutasKluda, konvertet_summu


def _novirzit_ar_pazinojumu(marsruts, pazinojums, limenis="success", **vertibas):
    vertibas["pazinojums"] = pazinojums
    vertibas["pazinojuma_limenis"] = limenis
    return redirect(url_for(marsruts, **vertibas))


def _neautorizeta_atbilde():
    pazinojums = "Sesija beidzās. Ieej vēlreiz."
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "statuss": "error",
                    "kluda": "nav_autorizets",
                    "pazinojums": pazinojums,
                }
            ),
            401,
        )
    return _novirzit_ar_pazinojumu("ieeja", pazinojums, "error")


def _ieeja_nepieciesama(skats):
    @wraps(skats)
    def ietinais_skats(*args, **kwargs):
        lietotaja_id = session.get("lietotaja_id")
        if lietotaja_id is None:
            return _neautorizeta_atbilde()

        lietotajs = iegut_lietotaju_pec_id(iegut_datubazi(), lietotaja_id)
        if lietotajs is None:
            session.clear()
            return _neautorizeta_atbilde()

        return skats(*args, **kwargs)

    return ietinais_skats


def izveidot_lietotni(testa_konfiguracija=None):
    lietotne = Flask(__name__, template_folder="templates", static_folder="static")
    lietotne.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "development-secret-key"),
        DATABASE=str(NOKLUSETA_DATUBAZE),
    )

    if testa_konfiguracija:
        lietotne.config.update(testa_konfiguracija)

    inicializet_datubazi(lietotne.config["DATABASE"])
    inicializet_datubazes_lietotni(lietotne)
    _registreet_marsrutus(lietotne)
    return lietotne


def _registreet_marsrutus(lietotne):
    @lietotne.get("/")
    def sakums():
        if session.get("lietotaja_id"):
            return redirect(url_for("panelis"))
        return redirect(url_for("ieeja"))

    @lietotne.route("/registracija", methods=["GET", "POST"])
    def registracija():
        if session.get("lietotaja_id"):
            return redirect(url_for("panelis"))

        if request.method == "POST":
            try:
                lietotajs = registret_lietotaju(iegut_datubazi(), request.form)
                return _novirzit_ar_pazinojumu(
                    "ieeja",
                    "Konts izveidots. Tagad vari ieiet.",
                    "success",
                    lietotajvards=lietotajs["lietotajvards"],
                )
            except ValidacijasKluda as kluda:
                return _novirzit_ar_pazinojumu("registracija", str(kluda), "error")

        return render_template("register.html")

    @lietotne.route("/ieeja", methods=["GET", "POST"])
    def ieeja():
        if session.get("lietotaja_id"):
            return redirect(url_for("panelis"))

        if request.method == "POST":
            try:
                lietotajs = autentificet_lietotaju(iegut_datubazi(), request.form)
                session.clear()
                session["lietotaja_id"] = lietotajs["id"]
                return _novirzit_ar_pazinojumu("panelis", "Prieks redzēt atkal.", "success")
            except AutentifikacijasKluda as kluda:
                lietotajvards = (request.form.get("lietotajvards") or "").strip()
                return _novirzit_ar_pazinojumu("ieeja", str(kluda), "error", lietotajvards=lietotajvards)

        return render_template("login.html")

    @lietotne.route("/iziet", methods=["GET", "POST"])
    def iziet():
        session.clear()
        return _novirzit_ar_pazinojumu("ieeja", "Tu esi izrakstījies.", "success")

    @lietotne.route("/panelis", methods=["GET", "POST"])
    @_ieeja_nepieciesama
    def panelis():
        if request.method == "POST":
            try:
                saglabat_krajsanas_planu(iegut_datubazi(), session["lietotaja_id"], request.form)
                return _novirzit_ar_pazinojumu("panelis", "Tavs krājuma plāns ir atjaunināts.", "success")
            except ValidacijasKluda as kluda:
                return _novirzit_ar_pazinojumu("panelis", str(kluda), "error")

        return render_template("dashboard.html")

    @lietotne.post("/panelis/atra-iemaksa")
    @_ieeja_nepieciesama
    def atra_iemaksa():
        try:
            pievienot_atro_iemaksu(iegut_datubazi(), session["lietotaja_id"], request.form)
            return _novirzit_ar_pazinojumu("panelis", "Pašreizējais atlikums atjaunināts.", "success")
        except ValidacijasKluda as kluda:
            return _novirzit_ar_pazinojumu("panelis", str(kluda), "error")

    @lietotne.get("/api/panela-dati")
    @_ieeja_nepieciesama
    def api_panela_dati():
        lietotajs = iegut_lietotaju_pec_id(iegut_datubazi(), session["lietotaja_id"])
        panela_dati = iegut_panela_datus(iegut_datubazi(), session["lietotaja_id"])
        return jsonify(
            {
                **panela_dati,
                "lietotajvards": lietotajs["lietotajvards"],
            }
        )

    @lietotne.get("/api/valuta")
    @_ieeja_nepieciesama
    def api_valuta():
        no_valutas = request.args.get("no", "EUR")
        uz_valutu = request.args.get("uz", "USD")
        summa_teksts = request.args.get("summa", "0")

        try:
            summa = float(summa_teksts)
        except ValueError:
            return (
                jsonify({"statuss": "error", "pazinojums": "Ievadi derīgu summu."}),
                400,
            )

        try:
            konvertets = konvertet_summu(summa, no_valutas, uz_valutu)
        except ValutasKluda as kluda:
            return (
                jsonify({"statuss": "error", "pazinojums": str(kluda)}),
                502,
            )

        return jsonify(
            {
                "statuss": "ok",
                "no": no_valutas.upper(),
                "uz": uz_valutu.upper(),
                "summa": summa,
                "konvertets": konvertets,
                "atlautasValutas": list(ATLAUTAS_VALUTAS),
            }
        )

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


lietotne = izveidot_lietotni()


if __name__ == "__main__":
    print("Atver http://127.0.0.1:5000/ pārlūkā. Neatver templates mapes failus pa tiešo.")
    lietotne.run(debug=True)
