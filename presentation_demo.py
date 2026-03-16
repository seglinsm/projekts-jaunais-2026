from services import build_dashboard_overview


def get_demo_dashboard_context():
    goals = [
        {
            "id": 101,
            "title": "Trip to Italy",
            "description": "Flights, hotel, and food budget for a summer vacation.",
            "targetAmount": 500.0,
            "targetDate": "2026-08-15",
            "totalSaved": 180.0,
            "remainingAmount": 320.0,
            "progressPercentage": 36.0,
            "visualProgressPercentage": 36.0,
            "monthlySavingRate": 70.0,
            "recurringContributionAmount": 50.0,
            "estimateText": "At your current pace, you may reach this goal in 5 months. Estimated completion: August 2026.",
            "recommendation": "You are on a steady path toward your goal.",
        },
        {
            "id": 102,
            "title": "New Laptop",
            "description": "Saving for a laptop for school projects and programming work.",
            "targetAmount": 1200.0,
            "targetDate": "2026-11-30",
            "totalSaved": 420.0,
            "remainingAmount": 780.0,
            "progressPercentage": 35.0,
            "visualProgressPercentage": 35.0,
            "monthlySavingRate": 110.0,
            "recurringContributionAmount": 100.0,
            "estimateText": "At your current pace, you may reach this goal in 8 months. Estimated completion: November 2026.",
            "recommendation": "You are on a steady path toward your goal.",
        },
        {
            "id": 103,
            "title": "Emergency Fund",
            "description": "Basic safety savings for unexpected expenses.",
            "targetAmount": 1000.0,
            "targetDate": "2026-12-31",
            "totalSaved": 250.0,
            "remainingAmount": 750.0,
            "progressPercentage": 25.0,
            "visualProgressPercentage": 25.0,
            "monthlySavingRate": 60.0,
            "recurringContributionAmount": 40.0,
            "estimateText": "At your current pace, you may reach this goal in 13 months. Estimated completion: April 2027.",
            "recommendation": "Consider increasing your regular contribution to reach your goal faster.",
        },
    ]

    overview = build_dashboard_overview(goals)
    return {
        "goals": goals,
        "overview": overview,
        "demo_mode": True,
    }
