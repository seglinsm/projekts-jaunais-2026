from services import build_dashboard_overview


def get_demo_dashboard_context():
    goals = [
        {
            "id": 101,
            "title": "Ceļojums uz Itāliju",
            "description": "Lidojumu, viesnīcas un ēdiena budžets vasaras atvaļinājumam.",
            "targetAmount": 500.0,
            "targetDate": "2026-08-15",
            "totalSaved": 180.0,
            "remainingAmount": 320.0,
            "progressPercentage": 36.0,
            "visualProgressPercentage": 36.0,
            "monthlySavingRate": 70.0,
            "recurringContributionAmount": 50.0,
            "estimateText": "Ar pašreizējo tempu šo mērķi var sasniegt 5 mēnešos. Paredzamā pabeigšana: 2026. gada augusts.",
            "recommendation": "Jūs stabili virzāties uz savu mērķi.",
        },
        {
            "id": 102,
            "title": "Jauns klēpjdators",
            "description": "Uzkrājums klēpjdatoram skolas projektiem un programmēšanai.",
            "targetAmount": 1200.0,
            "targetDate": "2026-11-30",
            "totalSaved": 420.0,
            "remainingAmount": 780.0,
            "progressPercentage": 35.0,
            "visualProgressPercentage": 35.0,
            "monthlySavingRate": 110.0,
            "recurringContributionAmount": 100.0,
            "estimateText": "Ar pašreizējo tempu šo mērķi var sasniegt 8 mēnešos. Paredzamā pabeigšana: 2026. gada novembris.",
            "recommendation": "Jūs stabili virzāties uz savu mērķi.",
        },
        {
            "id": 103,
            "title": "Drošības fonds",
            "description": "Drošības uzkrājums neparedzētiem izdevumiem.",
            "targetAmount": 1000.0,
            "targetDate": "2026-12-31",
            "totalSaved": 250.0,
            "remainingAmount": 750.0,
            "progressPercentage": 25.0,
            "visualProgressPercentage": 25.0,
            "monthlySavingRate": 60.0,
            "recurringContributionAmount": 40.0,
            "estimateText": "Ar pašreizējo tempu šo mērķi var sasniegt 13 mēnešos. Paredzamā pabeigšana: 2027. gada aprīlis.",
            "recommendation": "Apsveriet regulārās iemaksas palielināšanu, lai mērķi sasniegtu ātrāk.",
        },
    ]

    overview = build_dashboard_overview(goals)
    return {
        "goals": goals,
        "overview": overview,
        "demo_mode": True,
    }
