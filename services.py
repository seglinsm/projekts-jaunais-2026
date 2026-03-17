from __future__ import annotations

from datetime import date
import math
import re

from werkzeug.security import check_password_hash, generate_password_hash


MILESTONES = (25, 50, 75, 100)
QUICK_AMOUNTS = (10, 25, 50)


def _format_currency(value):
    amount = float(value or 0)
    whole, fraction = f"{amount:,.2f}".split(".")
    return f"{whole.replace(',', ' ')},{fraction} €"


class ValidationError(ValueError):
    pass


class AuthenticationError(ValueError):
    pass


def register_user(connection, payload):
    username = _require_username(payload.get("username"))
    password = _require_password(
        payload.get("password"),
        payload.get("confirm_password") or payload.get("confirmPassword"),
    )

    existing = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if existing is not None:
        raise ValidationError("Šis lietotājvārds jau ir aizņemts.")

    cursor = connection.execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
        """,
        (username, generate_password_hash(password)),
    )
    connection.commit()
    return get_user_by_id(connection, cursor.lastrowid)


def authenticate_user(connection, payload):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        raise AuthenticationError("Ievadi gan lietotājvārdu, gan paroli.")

    row = connection.execute(
        """
        SELECT id, username, password_hash, created_at
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        raise AuthenticationError("Nepareizs lietotājvārds vai parole.")

    return _serialize_user(row)


def get_user_by_id(connection, user_id):
    row = connection.execute(
        """
        SELECT id, username, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return _serialize_user(row)


def get_dashboard_data(connection, user_id):
    row = _get_profile_row(connection, user_id)
    return _build_dashboard_data(row)


def save_profile(connection, user_id, payload):
    goal_name = _require_goal_name(payload.get("goal_name"))
    goal_amount = _require_amount(payload.get("goal_amount"), "mērķa summu", allow_zero=False)
    current_balance = _require_amount(
        payload.get("current_balance"),
        "pašreizējo atlikumu",
        allow_zero=True,
    )
    monthly_contribution = _require_amount(
        payload.get("monthly_contribution"),
        "ikmēneša iemaksu",
        allow_zero=True,
    )
    target_date = _optional_date(payload.get("target_date"))
    note = _clean_note(payload.get("note"))

    connection.execute(
        """
        INSERT INTO savings_profiles (
            user_id,
            goal_name,
            goal_amount,
            current_balance,
            monthly_contribution,
            target_date,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            goal_name = excluded.goal_name,
            goal_amount = excluded.goal_amount,
            current_balance = excluded.current_balance,
            monthly_contribution = excluded.monthly_contribution,
            target_date = excluded.target_date,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            goal_name,
            goal_amount,
            current_balance,
            monthly_contribution,
            target_date,
            note,
        ),
    )
    connection.commit()
    return get_dashboard_data(connection, user_id)


def add_quick_amount(connection, user_id, payload):
    row = _get_profile_row(connection, user_id)
    if row is None:
        raise ValidationError("Vispirms saglabā mērķi, tad lieto ātro iemaksu.")

    amount = _require_amount(payload.get("amount"), "ātrās iemaksas summu", allow_zero=False)
    new_balance = round(float(row["current_balance"]) + amount, 2)

    connection.execute(
        """
        UPDATE savings_profiles
        SET current_balance = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (new_balance, user_id),
    )
    connection.commit()
    return get_dashboard_data(connection, user_id)


def _get_profile_row(connection, user_id):
    return connection.execute(
        """
        SELECT
            user_id,
            goal_name,
            goal_amount,
            current_balance,
            monthly_contribution,
            target_date,
            note,
            updated_at
        FROM savings_profiles
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def _build_dashboard_data(row):
    today = date.today()
    has_saved_plan = row is not None
    goal_name = row["goal_name"] if row else ""
    goal_amount = round(float(row["goal_amount"]), 2) if row else 0.0
    current_balance = round(float(row["current_balance"]), 2) if row else 0.0
    monthly_contribution = round(float(row["monthly_contribution"]), 2) if row else 0.0
    target_date = row["target_date"] if row else ""
    note = row["note"] if row else ""
    updated_at = row["updated_at"] if row else None

    if goal_amount <= 0:
        return {
            "hasSavedPlan": False,
            "goalName": goal_name,
            "goalAmount": goal_amount,
            "currentBalance": current_balance,
            "monthlyContribution": monthly_contribution,
            "targetDate": target_date,
            "note": note,
            "remainingAmount": 0.0,
            "progressPercentage": 0.0,
            "visualProgressPercentage": 0.0,
            "requiredMonthlyAmount": None,
            "statusLabel": "Var sākt",
            "statusTone": "calm",
            "forecastText": "Ievadi mērķi un pašreizējo atlikumu, lai redzētu progresu.",
            "timelineText": "Ikmēneša iemaksa palīdz saprast, kad vari tikt līdz mērķim.",
            "nextMilestoneText": "Pirmais progresa posms parādīsies pēc plāna saglabāšanas.",
            "daysUntilTarget": None,
            "milestones": _build_milestones(0.0),
            "quickAmounts": QUICK_AMOUNTS,
            "updatedAt": updated_at,
        }

    remaining_amount = round(max(goal_amount - current_balance, 0), 2)
    raw_progress = round((current_balance / goal_amount) * 100, 1)
    visual_progress = min(raw_progress, 100.0)
    required_monthly = None
    days_until_target = None
    status_label = "Brīvāks temps"
    status_tone = "calm"
    timeline_text = "Pievieno mērķa datumu, lai redzētu, vai tavs mēneša plāns ir pietiekams."

    if remaining_amount <= 0:
        forecast_text = "Tu šo mērķi jau esi sasniedzis."
        status_label = "Mērķis sasniegts"
        status_tone = "good"
        timeline_text = "Viss pēc šī punkta jau ir ekstra rezerve."
    elif monthly_contribution > 0:
        months_to_goal = max(math.ceil(remaining_amount / monthly_contribution), 1)
        month_label = "mēnesi" if months_to_goal == 1 else "mēnešus"
        forecast_text = f"Ar pašreizējo tempu tev vajadzēs vēl apmēram {months_to_goal} {month_label}."
    else:
        forecast_text = "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku."

    if target_date:
        target = date.fromisoformat(target_date)
        days_until_target = (target - today).days

        if remaining_amount <= 0:
            status_label = "Mērķis sasniegts"
            status_tone = "good"
            required_monthly = 0.0
            timeline_text = "Mērķa datums tev vairs nav šķērslis. Smuki."
        elif days_until_target < 0:
            status_label = "Datums ir garām"
            status_tone = "alert"
            timeline_text = "Tavs mērķa datums jau ir pagājis. Pabīdi to vai palielini krāšanas tempu."
        else:
            months_until_target = max(days_until_target / 30.44, 0.1)
            required_monthly = round(remaining_amount / months_until_target, 2)
            timeline_text = f"Lai paspētu līdz datumam, tev vajag apmēram {_format_currency(required_monthly)} mēnesī."
            if monthly_contribution <= 0:
                status_label = "Nav mēneša plāna"
                status_tone = "warning"
            elif monthly_contribution + 0.009 >= required_monthly:
                status_label = "Viss iet labi"
                status_tone = "good"
            else:
                status_label = "Jāpiespiež vairāk"
                status_tone = "warning"

    next_milestone = next((value for value in MILESTONES if raw_progress < value), None)
    if next_milestone is None:
        next_milestone_text = "Visi progresa posmi ir sasniegti."
    else:
        next_milestone_text = f"Nākamais posms ir {next_milestone}%."

    return {
        "hasSavedPlan": has_saved_plan,
        "goalName": goal_name,
        "goalAmount": goal_amount,
        "currentBalance": current_balance,
        "monthlyContribution": monthly_contribution,
        "targetDate": target_date,
        "note": note,
        "remainingAmount": remaining_amount,
        "progressPercentage": raw_progress,
        "visualProgressPercentage": visual_progress,
        "requiredMonthlyAmount": required_monthly,
        "statusLabel": status_label,
        "statusTone": status_tone,
        "forecastText": forecast_text,
        "timelineText": timeline_text,
        "nextMilestoneText": next_milestone_text,
        "daysUntilTarget": days_until_target,
        "milestones": _build_milestones(raw_progress),
        "quickAmounts": QUICK_AMOUNTS,
        "updatedAt": updated_at,
    }


def _build_milestones(progress):
    return [
        {
            "label": f"{value}%",
            "reached": progress >= value,
        }
        for value in MILESTONES
    ]


def _serialize_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "createdAt": row["created_at"],
    }


def _require_username(value):
    username = (value or "").strip()
    if len(username) < 3:
        raise ValidationError("Lietotājvārdam jābūt vismaz 3 simbolus garam.")
    if len(username) > 24:
        raise ValidationError("Lietotājvārdam jābūt ne garākam par 24 simboliem.")
    if re.fullmatch(r"[A-Za-z0-9_]+", username) is None:
        raise ValidationError("Lietotājvārdā drīkst lietot tikai burtus, ciparus un apakšsvītru.")
    return username


def _require_password(password, confirmation):
    value = password or ""
    if len(value) < 6:
        raise ValidationError("Parolei jābūt vismaz 6 simbolus garai.")
    if confirmation != value:
        raise ValidationError("Paroles nesakrīt.")
    return value


def _require_goal_name(value):
    goal_name = (value or "").strip()
    if not goal_name:
        raise ValidationError("Mērķa nosaukums ir obligāts.")
    if len(goal_name) > 60:
        raise ValidationError("Mērķa nosaukumam jābūt īsākam par 60 simboliem.")
    return goal_name


def _require_amount(value, label, allow_zero):
    raw_value = "" if value is None else str(value).strip()
    if raw_value == "":
        raise ValidationError(f"Ievadi {label}.")

    try:
        amount = round(float(raw_value), 2)
    except ValueError as error:
        raise ValidationError(f"Ievadi korektu {label}.") from error

    minimum = 0.0 if allow_zero else 0.01
    if amount < minimum or (not allow_zero and amount == 0):
        comparator = "0 vai lielākai" if allow_zero else "lielākai par 0"
        raise ValidationError(f"{label[:1].upper() + label[1:]} jābūt {comparator}.")
    return amount


def _optional_date(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    try:
        date.fromisoformat(raw_value)
    except ValueError as error:
        raise ValidationError("Ievadi korektu mērķa datumu.") from error
    return raw_value


def _clean_note(value):
    note = (value or "").strip()
    return note[:240]
