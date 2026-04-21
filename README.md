# GoalBloom — uzkrājumu mērķu panelis

Vienkārša Flask lietotne, kas palīdz lietotājam sekot līdzi uzkrājumu
mērķim: ievadīt mērķa summu, pašreizējo atlikumu un ikmēneša iemaksu,
redzēt progresa joslu, atzīmēt mazos posmus (25 %, 50 %, 75 %, 100 %) un
saņemt ieteikumu par nepieciešamo tempu, lai paspētu līdz termiņam.

Šis repozitorijs ir centralizētā eksāmena “Programmēšana (augstākais
mācību satura apguves līmenis)” noslēguma projekts.

## Problēma un mērķis

Daudziem ir grūti saprast, cik ātri viņi reāli varēs sakrāt kādam mērķim,
jo iemaksas tiek pierakstītas dažādās vietās. Nav skaidra bilde: cik jau
ir sakrāts, cik vēl pietrūkst un vai ar pašreizējo tempu mērķis ir
sasniedzams.

**Mērķis:** viena vieta, kur ielikt mērķi, pievienot iemaksas un uzreiz
redzēt progresu, kā arī saņemt ieteikumu par nepieciešamo ikmēneša
iemaksu, ja ir norādīts termiņš.

## Lietotāju lomas

Projektā ir viena lietotāja loma — **reģistrēts lietotājs**. Viņš var:

- izveidot kontu un ieiet ar lietotājvārdu un paroli;
- saglabāt un atjaunināt savu uzkrājumu plānu;
- pievienot ātrās iemaksas (+10, +25, +50 EUR);
- redzēt progresa joslu, atlikušo summu, mēneša tempu un nepieciešamo
  tempu, ja ir norādīts termiņš;
- eksportēt savu plānu kā CSV failu;
- pārrēķināt atlikumu citā valūtā (USD, GBP, SEK, NOK, CHF, PLN), izmantojot
  ārējo Frankfurter API (ECB kursi);
- izrakstīties no konta.

## Funkcijas

| Funkcija | Apraksts |
| --- | --- |
| `registret_lietotaju` | Izveido jaunu kontu ar šifrētu paroli (Werkzeug `generate_password_hash`). |
| `autentificet_lietotaju` | Pārbauda lietotājvārdu un paroli, ievieš sesiju. |
| `saglabat_krajsanas_planu` | Saglabā vai atjaunina viena lietotāja uzkrājumu plānu. |
| `pievienot_atro_iemaksu` | Palielina pašreizējo atlikumu ar fiksētu summu. |
| `iegut_panela_datus` | Atgriež sagatavotus datus JSON formātā paneļa attēlošanai. |
| `konvertet_summu` | Ārējais API zvans uz Frankfurter valūtas kursu servisu. |
| `eksportet_csv` | Ģenerē CSV failu ar lietotāja plāna kopsavilkumu. |

## Datu klases

- `lietotaji` (id, lietotājvārds, paroles jaukums, izveides laiks).
- `krajsanas_plani` (id, lietotāja_id *(FK)*, mērķa nosaukums, mērķa
  summa, pašreizējais atlikums, ikmēneša iemaksa, mērķa datums, piezīme,
  atjaunināšanas laiks).

Datubāzes ER modelis: `lietotaji 1 —— 0..1 krajsanas_plani`
(viens lietotājs = viens plāns; saite ar `ON DELETE CASCADE`).

OOP klašu hierarhija (sk. [models.py](models.py)):

```
BazesKrajsanasPlans           (bāzes klase)
├── RegularsKrajsanasPlans    (atvasinātā — ar ikmēneša iemaksu)
└── TerminetsKrajsanasPlans   (atvasinātā — ar mērķa datumu)
```

## Tehnoloģijas

- **Valoda:** Python 3.11+
- **Ietvars:** Flask 3
- **Datubāze:** SQLite (`goalbloom.db`), `PRAGMA foreign_keys = ON`
- **Kriptogrāfija:** `werkzeug.security` paroļu jaukumiem
- **Ārējs API:** [Frankfurter](https://www.frankfurter.app/) — ECB
  valūtas kursi bez atslēgas
- **Izstrādes modelis:** Waterfall — prasības ➝ dizains ➝ izstrāde ➝
  testēšana ➝ nodošana
- **Izstrādes vide:** VS Code, `python -m unittest`

## Darbības uzsākšana

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
python app.py
```

Pēc palaišanas atver [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

Windows lietotāji var izmantot gatavo skriptu: `start_app.bat`.

## Lietotāja ceļvedis

1. **Reģistrācija.** Atver `/registracija`, izvēlies lietotājvārdu
   (3–24 simboli, tikai burti, cipari un `_`) un paroli (vismaz 6 simboli),
   apstiprini paroli un nospied **Izveidot kontu**.
2. **Ieeja.** Atver `/ieeja`, ievadi lietotājvārdu un paroli,
   nospied **Atvērt paneli**.
3. **Plāna saglabāšana.** Panelī aizpildi mērķa nosaukumu, mērķa summu,
   pašreizējo atlikumu, ikmēneša iemaksu un, ja vēlies, mērķa datumu un
   piezīmi. Nospied **Saglabāt plānu**.
4. **Ātrās iemaksas.** Zem formas ir pogas **+10**, **+25**, **+50** —
   tās uzreiz palielina pašreizējo atlikumu.
5. **Valūtas pārrēķins.** Sadaļā *Atlikums citā valūtā* izvēlies valūtu
   un nospied **Pārrēķināt** — sistēma parādīs pašreizējo atlikumu
   izvēlētajā valūtā, izmantojot ECB kursus.
6. **CSV eksports.** Sadaļā *Eksports* nospied **Lejupielādēt CSV**, lai
   saglabātu sava plāna kopsavilkumu failā.
7. **Iziešana.** Augšējā labajā stūrī nospied **Iziet**.

## Testēšanas plāns

| Sistēmas daļa | Kā testē | Gaidāmais rezultāts |
| --- | --- | --- |
| Reģistrācija / ieeja / izrakstīšanās | `unittest` integrācijas testi | Statusa kodi 302 un pareizas novirzīšanās |
| Paneļa datu API | `unittest` + `test_client` | 401 viesim, 200 ar korektiem datiem lietotājam |
| Plāna saglabāšana un ātrā iemaksa | `unittest` + SQLite pārbaude | Datubāzē saglabāti korekti dati |
| OOP modeļi | `unittest` moduļtesti | Pareizi aprēķini trim plāna variācijām |
| Valūtas API | `unittest` ar viltus `urlopen` | Korekta reakcija uz API atbildi un kļūdām |
| CSV eksports | `unittest` + `test_client` | Pareizs `Content-Type` un saturs |

Testu palaišana:

```bash
python -m unittest discover -s tests -v
```

## Failu struktūra

```
.
├── app.py                    # Flask maršruti un lietotnes fabrika
├── models.py                 # OOP klases uzkrājumu plāniem
├── services.py               # Biznesa loģika, validācija, paroļu jaukumi
├── database.py               # SQLite savienojums un migrēšana
├── valutas_serviss.py        # Ārējs API (Frankfurter) un kešs
├── schema.sql                # Datubāzes shēma (lietotaji, krajsanas_plani)
├── goalbloom.db              # Projekta datubāze (piesaistīta repozitorijam)
├── templates/                # Jinja HTML veidnes
├── static/                   # CSS un JS
├── tests/                    # unittest testi
├── requirements.txt
└── start_app.bat
```

## Atbilstība eksāmena kritērijiem

- **Datubāzes izstrāde (4. pielikums, 1. kr.):** 2 saistītas tabulas,
  paroļu šifrēšana (Werkzeug).
- **API izmantošana (4. pielikums, 2. kr.):** Frankfurter valūtas kursu
  API ar paša veidotu `valutas_serviss` moduli un atmiņas kešu.
- **Datu ievadizvade (4. pielikums, 3. kr.):** dati tiek ievadīti,
  glabāti SQLite, apstrādāti un izvadīti (JSON + CSV eksports datnē).
- **OOP (4. pielikums, 4. kr.):** 1 bāzes klase + 2 atvasinātās klases
  ar metožu pārrakstīšanu.
- **Akcepttestēšanas pārskats (3. pielikums, 4. kr.):** `unittest`
  bibliotēka, testēšanas plāns šajā README.
- **Lietotāja ceļvedis (3. pielikums, 5. kr.):** šis README ar
  viegli saprotamām sadaļām un vizuālu struktūru.
- **Datubāze commit-otaGitHub repozitorijā (PPS 9. kr.):** `goalbloom.db`
  ir iekļauts repozitorijā (izņemts no `.gitignore`).
