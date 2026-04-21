from __future__ import annotations

from datetime import date
import math


class BazesKrajsanasPlans:
    """Bāzes klase jebkuram uzkrājumu plānam.

    Apraksta visu, kas ir kopīgs starp plāna variācijām:
    mērķa nosaukumu, mērķa summu, pašreizējo atlikumu un piezīmi,
    kā arī aprēķinus, kas nav atkarīgi no termiņa vai tempa.
    """

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

    def __init__(
        self,
        merka_nosaukums,
        merka_summa,
        pasreizejais_atlikums,
        ikmenesa_iemaksa,
        piezime="",
    ):
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

    def __init__(
        self,
        merka_nosaukums,
        merka_summa,
        pasreizejais_atlikums,
        ikmenesa_iemaksa,
        merka_datums,
        piezime="",
    ):
        super().__init__(
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            piezime,
        )
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


def izveidot_planu(
    merka_nosaukums,
    merka_summa,
    pasreizejais_atlikums,
    ikmenesa_iemaksa=0.0,
    merka_datums=None,
    piezime="",
):
    """Fabrika, kas atgriež konkrētāko klasi, kas atbilst ievadītajiem datiem."""
    if merka_datums:
        return TerminetsKrajsanasPlans(
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            merka_datums,
            piezime,
        )
    if float(ikmenesa_iemaksa or 0) > 0:
        return RegularsKrajsanasPlans(
            merka_nosaukums,
            merka_summa,
            pasreizejais_atlikums,
            ikmenesa_iemaksa,
            piezime,
        )
    return BazesKrajsanasPlans(
        merka_nosaukums,
        merka_summa,
        pasreizejais_atlikums,
        piezime,
    )
