from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import math


DAYS_PER_MONTH = 30.44
RECENT_WINDOW_DAYS = 90


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


def list_goal_summaries(connection):
    rows = connection.execute(
        "SELECT * FROM goals ORDER BY COALESCE(target_date, created_at), created_at DESC"
    ).fetchall()
    return [get_goal_detail(connection, row["id"], include_contributions=False) for row in rows]


def get_goal_detail(connection, goal_id, include_contributions=True):
    goal_row = _get_goal_row(connection, goal_id)
    _sync_recurring_contributions(connection, goal_id)
    contribution_rows = _get_contribution_rows(connection, goal_id)
    plan_row = _get_recurring_plan_row(connection, goal_id)

    goal = _serialize_goal(goal_row)
    contributions = [_serialize_contribution(row) for row in contribution_rows]
    recurring_plan = _serialize_recurring_plan(plan_row) if plan_row else None
    metrics = _calculate_metrics(goal, contributions, recurring_plan)

    payload = {**goal, **metrics, "recurringPlan": recurring_plan}
    if include_contributions:
        payload["contributions"] = contributions
    return payload


def create_goal(connection, payload):
    title = _require_text(payload.get("title"), "title")
    target_amount = _require_positive_amount(payload.get("targetAmount"), "targetAmount")
    description = _optional_text(payload.get("description"))
    target_date = _optional_date(payload.get("targetDate"), "targetDate")

    cursor = connection.execute(
        """
        INSERT INTO goals (title, target_amount, description, target_date)
        VALUES (?, ?, ?, ?)
        """,
        (title, target_amount, description, target_date),
    )
    connection.commit()
    return get_goal_detail(connection, cursor.lastrowid)


def update_goal(connection, goal_id, payload):
    existing = _serialize_goal(_get_goal_row(connection, goal_id))

    title = _require_text(payload.get("title", existing["title"]), "title")
    target_amount = _require_positive_amount(
        payload.get("targetAmount", existing["targetAmount"]),
        "targetAmount",
    )
    description = _optional_text(payload.get("description", existing["description"]))
    target_date = _optional_date(payload.get("targetDate", existing["targetDate"]), "targetDate")

    connection.execute(
        """
        UPDATE goals
        SET title = ?, target_amount = ?, description = ?, target_date = ?
        WHERE id = ?
        """,
        (title, target_amount, description, target_date, goal_id),
    )
    connection.commit()
    return get_goal_detail(connection, goal_id)


def delete_goal(connection, goal_id):
    _get_goal_row(connection, goal_id)
    connection.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    connection.commit()


def list_contributions(connection, goal_id):
    _get_goal_row(connection, goal_id)
    _sync_recurring_contributions(connection, goal_id)
    rows = _get_contribution_rows(connection, goal_id)
    return [_serialize_contribution(row) for row in rows]


def add_contribution(connection, goal_id, payload):
    _get_goal_row(connection, goal_id)

    amount = _require_positive_amount(payload.get("amount"), "amount")
    entry_date = _optional_date(payload.get("date"), "date") or date.today().isoformat()
    note = _optional_text(payload.get("note"))
    contribution_type = _normalize_contribution_type(payload.get("type", "manual"))

    cursor = connection.execute(
        """
        INSERT INTO contributions (goal_id, amount, date, note, type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (goal_id, amount, entry_date, note, contribution_type),
    )
    connection.commit()
    return get_contribution(connection, cursor.lastrowid)


def get_contribution(connection, contribution_id):
    row = _get_contribution_row(connection, contribution_id)
    return _serialize_contribution(row)


def update_contribution(connection, contribution_id, payload):
    existing = _serialize_contribution(_get_contribution_row(connection, contribution_id))

    amount = _require_positive_amount(payload.get("amount", existing["amount"]), "amount")
    entry_date = _optional_date(payload.get("date", existing["date"]), "date") or existing["date"]
    note = _optional_text(payload.get("note", existing["note"]))
    contribution_type = _normalize_contribution_type(payload.get("type", existing["type"]))

    connection.execute(
        """
        UPDATE contributions
        SET amount = ?, date = ?, note = ?, type = ?
        WHERE id = ?
        """,
        (amount, entry_date, note, contribution_type, contribution_id),
    )
    connection.commit()
    return get_contribution(connection, contribution_id)


def delete_contribution(connection, contribution_id):
    _get_contribution_row(connection, contribution_id)
    connection.execute("DELETE FROM contributions WHERE id = ?", (contribution_id,))
    connection.commit()


def get_recurring_plan(connection, goal_id):
    _get_goal_row(connection, goal_id)
    row = _get_recurring_plan_row(connection, goal_id)
    return _serialize_recurring_plan(row) if row else None


def upsert_recurring_plan(connection, goal_id, payload):
    _get_goal_row(connection, goal_id)

    amount = _require_positive_amount(payload.get("amount"), "amount")
    frequency = _normalize_frequency(payload.get("frequency"))
    start_date = _optional_date(payload.get("startDate"), "startDate") or date.today().isoformat()
    is_active = _normalize_bool(payload.get("isActive", True))

    existing = _get_recurring_plan_row(connection, goal_id)
    if existing:
        connection.execute(
            """
            UPDATE recurring_plans
            SET amount = ?, frequency = ?, start_date = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE goal_id = ?
            """,
            (amount, frequency, start_date, int(is_active), goal_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO recurring_plans (goal_id, amount, frequency, start_date, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (goal_id, amount, frequency, start_date, int(is_active)),
        )

    connection.commit()
    _sync_recurring_contributions(connection, goal_id)
    return get_recurring_plan(connection, goal_id)


def build_dashboard_overview(goals):
    goal_count = len(goals)
    total_target = round(sum(goal["targetAmount"] for goal in goals), 2)
    total_saved = round(sum(goal["totalSaved"] for goal in goals), 2)
    average_progress = round(
        sum(goal["progressPercentage"] for goal in goals) / goal_count, 2
    ) if goal_count else 0.0

    return {
        "goalCount": goal_count,
        "totalTarget": total_target,
        "totalSaved": total_saved,
        "averageProgress": average_progress,
    }


def _calculate_metrics(goal, contributions, recurring_plan):
    total_saved = round(sum(item["amount"] for item in contributions), 2)
    remaining_amount = round(max(goal["targetAmount"] - total_saved, 0), 2)
    progress = round((total_saved / goal["targetAmount"]) * 100, 2)
    visual_progress = min(progress, 100.0)

    recurring_monthly = 0.0
    if recurring_plan and recurring_plan["isActive"]:
        recurring_monthly = _to_monthly_amount(
            recurring_plan["amount"], recurring_plan["frequency"]
        )

    recent_contributions = _recent_contributions(contributions)
    recent_manual_contributions = [
        item for item in recent_contributions if item["type"] == "manual"
    ]
    recent_manual_monthly = round(
        sum(item["amount"] for item in recent_manual_contributions) / 3, 2
    ) if recent_manual_contributions else 0.0
    recent_all_monthly = round(
        sum(item["amount"] for item in recent_contributions) / 3, 2
    ) if recent_contributions else 0.0

    if recurring_monthly > 0:
        monthly_saving_rate = round(recurring_monthly + recent_manual_monthly, 2)
        pace_source = "combined" if recent_manual_monthly else "recurring-plan"
    elif len(recent_manual_contributions) >= 2:
        monthly_saving_rate = recent_all_monthly
        pace_source = "recent-contributions"
    else:
        monthly_saving_rate = 0.0
        pace_source = "none"

    estimate = _estimate_completion(
        goal,
        remaining_amount,
        monthly_saving_rate,
        pace_source,
    )
    recommendation = _build_recommendation(
        goal,
        remaining_amount,
        progress,
        recurring_monthly,
        monthly_saving_rate,
        estimate["monthsToGoal"],
    )

    return {
        "totalSaved": total_saved,
        "remainingAmount": remaining_amount,
        "progressPercentage": progress,
        "visualProgressPercentage": visual_progress,
        "recurringContributionAmount": round(recurring_monthly, 2),
        "recentManualMonthlyAverage": recent_manual_monthly,
        "monthlySavingRate": monthly_saving_rate,
        "paceSource": pace_source,
        "estimateText": estimate["estimateText"],
        "estimatedCompletionDate": estimate["estimatedCompletionDate"],
        "monthsToGoal": estimate["monthsToGoal"],
        "recommendation": recommendation,
        "contributionCount": len(contributions),
    }


def _sync_recurring_contributions(connection, goal_id):
    plan_row = _get_recurring_plan_row(connection, goal_id)
    existing_rows = connection.execute(
        """
        SELECT * FROM contributions
        WHERE goal_id = ? AND type = 'recurring'
        ORDER BY date ASC
        """,
        (goal_id,),
    ).fetchall()

    if plan_row is None:
        if existing_rows:
            connection.execute(
                "DELETE FROM contributions WHERE goal_id = ? AND type = 'recurring'",
                (goal_id,),
            )
            connection.commit()
        return

    plan = _serialize_recurring_plan(plan_row)
    start_date = _parse_iso_date(plan["startDate"])
    if (not plan["isActive"]) or start_date is None or start_date > date.today():
        if existing_rows:
            connection.execute(
                "DELETE FROM contributions WHERE goal_id = ? AND type = 'recurring'",
                (goal_id,),
            )
            connection.commit()
        return

    expected_dates = {
        occurrence.isoformat()
        for occurrence in _generate_occurrence_dates(
            start_date,
            date.today(),
            plan["frequency"],
        )
    }
    existing_by_date = {row["date"]: row for row in existing_rows}
    auto_note = "Auto-generated from recurring plan"
    has_changes = False

    for row in existing_rows:
        if row["date"] not in expected_dates:
            connection.execute("DELETE FROM contributions WHERE id = ?", (row["id"],))
            has_changes = True

    for occurrence_date in expected_dates:
        existing = existing_by_date.get(occurrence_date)
        if existing is None:
            connection.execute(
                """
                INSERT INTO contributions (goal_id, amount, date, note, type)
                VALUES (?, ?, ?, ?, 'recurring')
                """,
                (goal_id, plan["amount"], occurrence_date, auto_note),
            )
            has_changes = True
            continue

        if (
            round(float(existing["amount"]), 2) != plan["amount"]
            or (existing["note"] or "") != auto_note
        ):
            connection.execute(
                """
                UPDATE contributions
                SET amount = ?, note = ?
                WHERE id = ?
                """,
                (plan["amount"], auto_note, existing["id"]),
            )
            has_changes = True

    if has_changes:
        connection.commit()


def _estimate_completion(goal, remaining_amount, monthly_saving_rate, pace_source):
    if remaining_amount <= 0:
        return {
            "estimateText": "Goal reached.",
            "estimatedCompletionDate": date.today().isoformat(),
            "monthsToGoal": 0,
        }

    if monthly_saving_rate <= 0 or pace_source == "none":
        return {
            "estimateText": "Not enough data to estimate completion time.",
            "estimatedCompletionDate": None,
            "monthsToGoal": None,
        }

    months_to_goal = round(remaining_amount / monthly_saving_rate, 2)
    completion_date = date.today() + timedelta(days=math.ceil(months_to_goal * DAYS_PER_MONTH))
    duration_text = _format_duration(months_to_goal)
    estimate_text = (
        f"At your current pace, you may reach this goal in {duration_text}. "
        f"Estimated completion: {completion_date.strftime('%B %Y')}."
    )

    return {
        "estimateText": estimate_text,
        "estimatedCompletionDate": completion_date.isoformat(),
        "monthsToGoal": months_to_goal,
    }


def _build_recommendation(
    goal,
    remaining_amount,
    progress,
    recurring_monthly,
    monthly_saving_rate,
    months_to_goal,
):
    if remaining_amount <= 0:
        return "You reached this goal. Consider creating a new savings target."

    target_date = _parse_iso_date(goal["targetDate"])
    if target_date:
        days_left = (target_date - date.today()).days
        if days_left <= 0:
            return "The target date has passed. Extend the date or increase contributions."

        months_left = max(days_left / DAYS_PER_MONTH, 0.1)
        required_monthly = remaining_amount / months_left

        if monthly_saving_rate <= 0:
            return (
                "Your current savings pace may not be enough to reach the target date. "
                f"Try saving about EUR {required_monthly:.2f} per month."
            )

        if monthly_saving_rate < required_monthly:
            increase_needed = required_monthly - monthly_saving_rate
            return (
                "Your current savings pace may not be enough to reach the target date. "
                f"Increase your monthly savings by about EUR {increase_needed:.2f}."
            )

        if monthly_saving_rate >= required_monthly * 1.15:
            return "You are ahead of schedule."

    if remaining_amount <= goal["targetAmount"] * 0.1:
        return "You are almost there."

    if progress < 25 and recurring_monthly < goal["targetAmount"] * 0.05:
        return "Consider increasing your regular contribution to reach your goal faster."

    if recurring_monthly > 0 and months_to_goal is not None:
        return "You are on a steady path toward your goal."

    if monthly_saving_rate > 0:
        return "Your manual deposits are helping. A recurring plan would make progress more predictable."

    return "Add a contribution or create a recurring plan to start building momentum."


def _recent_contributions(contributions):
    cutoff = date.today() - timedelta(days=RECENT_WINDOW_DAYS)
    recent = []
    for contribution in contributions:
        contribution_date = _parse_iso_date(contribution["date"])
        if contribution_date and contribution_date >= cutoff:
            recent.append(contribution)
    return recent


def _format_duration(months):
    if months < 1:
        weeks = max(1, math.ceil(months * 4.345))
        return f"{weeks} week{'s' if weeks != 1 else ''}"

    rounded_months = max(1, math.ceil(months))
    return f"{rounded_months} month{'s' if rounded_months != 1 else ''}"


def _to_monthly_amount(amount, frequency):
    if frequency == "weekly":
        return round(amount * (52 / 12), 2)
    return round(amount, 2)


def _generate_occurrence_dates(start_date, end_date, frequency):
    occurrences = []
    current = start_date

    while current <= end_date:
        occurrences.append(current)
        if frequency == "weekly":
            current += timedelta(days=7)
        else:
            current = _add_one_month(current)

    return occurrences


def _add_one_month(current_date):
    next_month = current_date.month + 1
    next_year = current_date.year
    if next_month > 12:
        next_month = 1
        next_year += 1

    last_day = calendar.monthrange(next_year, next_month)[1]
    return current_date.replace(
        year=next_year,
        month=next_month,
        day=min(current_date.day, last_day),
    )


def _serialize_goal(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "targetAmount": round(float(row["target_amount"]), 2),
        "description": row["description"] or "",
        "targetDate": row["target_date"],
        "createdAt": row["created_at"],
    }


def _serialize_contribution(row):
    return {
        "id": row["id"],
        "goalId": row["goal_id"],
        "amount": round(float(row["amount"]), 2),
        "date": row["date"],
        "note": row["note"] or "",
        "type": row["type"],
        "createdAt": row["created_at"],
    }


def _serialize_recurring_plan(row):
    return {
        "id": row["id"],
        "goalId": row["goal_id"],
        "amount": round(float(row["amount"]), 2),
        "frequency": row["frequency"],
        "startDate": row["start_date"],
        "isActive": bool(row["is_active"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _get_goal_row(connection, goal_id):
    row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Goal {goal_id} was not found.")
    return row


def _get_contribution_rows(connection, goal_id):
    return connection.execute(
        """
        SELECT * FROM contributions
        WHERE goal_id = ?
        ORDER BY date DESC, id DESC
        """,
        (goal_id,),
    ).fetchall()


def _get_contribution_row(connection, contribution_id):
    row = connection.execute(
        "SELECT * FROM contributions WHERE id = ?",
        (contribution_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Contribution {contribution_id} was not found.")
    return row


def _get_recurring_plan_row(connection, goal_id):
    return connection.execute(
        "SELECT * FROM recurring_plans WHERE goal_id = ?",
        (goal_id,),
    ).fetchone()


def _require_text(value, field_name):
    text = _optional_text(value)
    if not text:
        raise ValidationError(f"{field_name} is required.")
    return text


def _optional_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _require_positive_amount(value, field_name):
    if value is None or value == "":
        raise ValidationError(f"{field_name} is required.")

    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field_name} must be a valid number.") from error

    if amount <= 0:
        raise ValidationError(f"{field_name} must be greater than 0.")
    return amount


def _optional_date(value, field_name):
    if value in (None, ""):
        return None

    parsed = _parse_iso_date(value)
    if parsed is None:
        raise ValidationError(f"{field_name} must use YYYY-MM-DD format.")
    return parsed.isoformat()


def _parse_iso_date(value):
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _normalize_frequency(value):
    frequency = _optional_text(value).lower()
    if frequency not in {"weekly", "monthly"}:
        raise ValidationError("frequency must be either weekly or monthly.")
    return frequency


def _normalize_contribution_type(value):
    contribution_type = _optional_text(value).lower() or "manual"
    if contribution_type not in {"manual", "recurring"}:
        raise ValidationError("type must be either manual or recurring.")
    return contribution_type


def _normalize_bool(value):
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError("isActive must be true or false.")
