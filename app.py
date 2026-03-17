from datetime import date
import os

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from database import DEFAULT_DATABASE, get_db, init_app as init_database_app, init_db
from services import (
    NotFoundError,
    ValidationError,
    add_contribution,
    create_goal,
    delete_contribution,
    delete_goal,
    get_goal_detail,
    get_recurring_plan,
    list_contributions,
    list_goal_summaries,
    update_contribution,
    update_goal,
    upsert_recurring_plan,
)


def _format_currency(value):
    amount = float(value or 0)
    whole, fraction = f"{amount:,.2f}".split(".")
    return f"{whole.replace(',', ' ')},{fraction} €"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "development-secret-key"),
        DATABASE=str(DEFAULT_DATABASE),
    )

    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    init_database_app(app)
    _register_template_helpers(app)
    _register_web_routes(app)
    _register_api_routes(app)
    return app


def _register_template_helpers(app):
    @app.template_filter("currency")
    def currency_filter(value):
        return _format_currency(value)

    @app.context_processor
    def inject_defaults():
        return {"today_iso": date.today().isoformat()}


def _register_web_routes(app):
    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/presentation-dashboard")
    def presentation_dashboard():
        return render_template("dashboard.html")

    @app.get("/goals/<int:goal_id>")
    def goal_detail(goal_id):
        try:
            goal = get_goal_detail(get_db(), goal_id)
        except NotFoundError as error:
            flash(str(error), "error")
            return redirect(url_for("dashboard"))

        return render_template("goal_detail.html", goal=goal)

    @app.post("/goals")
    def create_goal_route():
        try:
            create_goal(get_db(), request.form)
            flash("Uzkrājumu mērķis izveidots.", "success")
        except ValidationError as error:
            flash(str(error), "error")
        return redirect(url_for("dashboard"))

    @app.post("/goals/<int:goal_id>/edit")
    def update_goal_route(goal_id):
        try:
            update_goal(get_db(), goal_id, request.form)
            flash("Mērķis atjaunināts.", "success")
        except (ValidationError, NotFoundError) as error:
            flash(str(error), "error")
        return redirect(url_for("goal_detail", goal_id=goal_id))

    @app.post("/goals/<int:goal_id>/delete")
    def delete_goal_route(goal_id):
        try:
            delete_goal(get_db(), goal_id)
            flash("Mērķis dzēsts.", "success")
        except NotFoundError as error:
            flash(str(error), "error")
        return redirect(url_for("dashboard"))

    @app.post("/goals/<int:goal_id>/contributions")
    def add_contribution_route(goal_id):
        try:
            add_contribution(get_db(), goal_id, request.form)
            flash("Iemaksa pievienota.", "success")
        except (ValidationError, NotFoundError) as error:
            flash(str(error), "error")
        return redirect(url_for("goal_detail", goal_id=goal_id))

    @app.post("/contributions/<int:contribution_id>/delete")
    def delete_contribution_route(contribution_id):
        goal_id = request.form.get("goal_id")
        redirect_goal_id = goal_id or ""
        try:
            delete_contribution(get_db(), contribution_id)
            flash("Iemaksa dzēsta.", "success")
        except NotFoundError as error:
            flash(str(error), "error")

        if redirect_goal_id:
            return redirect(url_for("goal_detail", goal_id=redirect_goal_id))
        return redirect(url_for("dashboard"))

    @app.post("/contributions/<int:contribution_id>/edit")
    def update_contribution_route(contribution_id):
        goal_id = request.form.get("goal_id")
        redirect_goal_id = goal_id or ""
        try:
            contribution = update_contribution(get_db(), contribution_id, request.form)
            redirect_goal_id = redirect_goal_id or str(contribution["goalId"])
            flash("Iemaksa atjaunināta.", "success")
        except (ValidationError, NotFoundError) as error:
            flash(str(error), "error")

        if redirect_goal_id:
            return redirect(url_for("goal_detail", goal_id=redirect_goal_id))
        return redirect(url_for("dashboard"))

    @app.post("/goals/<int:goal_id>/recurring-plan")
    def recurring_plan_route(goal_id):
        try:
            upsert_recurring_plan(get_db(), goal_id, request.form)
            flash("Regulārais plāns saglabāts.", "success")
        except (ValidationError, NotFoundError) as error:
            flash(str(error), "error")
        return redirect(url_for("goal_detail", goal_id=goal_id))


def _register_api_routes(app):
    @app.get("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.get("/api/goals")
    def api_list_goals():
        goals = list_goal_summaries(get_db())
        return jsonify({"items": goals, "count": len(goals)})

    @app.post("/api/goals")
    def api_create_goal():
        try:
            goal = create_goal(get_db(), _require_json_body())
            return jsonify(goal), 201
        except ValidationError as error:
            return _json_error(str(error), 400)

    @app.get("/api/goals/<int:goal_id>")
    def api_get_goal(goal_id):
        try:
            goal = get_goal_detail(get_db(), goal_id)
            return jsonify(goal)
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.put("/api/goals/<int:goal_id>")
    def api_update_goal(goal_id):
        try:
            goal = update_goal(get_db(), goal_id, _require_json_body())
            return jsonify(goal)
        except ValidationError as error:
            return _json_error(str(error), 400)
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.delete("/api/goals/<int:goal_id>")
    def api_delete_goal(goal_id):
        try:
            delete_goal(get_db(), goal_id)
            return "", 204
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.get("/api/goals/<int:goal_id>/contributions")
    def api_list_contributions(goal_id):
        try:
            items = list_contributions(get_db(), goal_id)
            return jsonify({"items": items, "count": len(items)})
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.post("/api/goals/<int:goal_id>/contributions")
    def api_add_contribution(goal_id):
        try:
            contribution = add_contribution(get_db(), goal_id, _require_json_body())
            goal = get_goal_detail(get_db(), goal_id)
            return jsonify({"contribution": contribution, "goal": goal}), 201
        except ValidationError as error:
            return _json_error(str(error), 400)
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.put("/api/contributions/<int:contribution_id>")
    def api_update_contribution(contribution_id):
        try:
            contribution = update_contribution(get_db(), contribution_id, _require_json_body())
            return jsonify(contribution)
        except ValidationError as error:
            return _json_error(str(error), 400)
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.delete("/api/contributions/<int:contribution_id>")
    def api_delete_contribution(contribution_id):
        try:
            delete_contribution(get_db(), contribution_id)
            return "", 204
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.get("/api/goals/<int:goal_id>/recurring-plan")
    def api_get_recurring_plan(goal_id):
        try:
            plan = get_recurring_plan(get_db(), goal_id)
            if plan is None:
                return jsonify({"item": None}), 200
            return jsonify(plan)
        except NotFoundError as error:
            return _json_error(str(error), 404)

    @app.route("/api/goals/<int:goal_id>/recurring-plan", methods=["POST", "PUT"])
    def api_upsert_recurring_plan(goal_id):
        try:
            plan = upsert_recurring_plan(get_db(), goal_id, _require_json_body())
            goal = get_goal_detail(get_db(), goal_id)
            return jsonify({"recurringPlan": plan, "goal": goal})
        except ValidationError as error:
            return _json_error(str(error), 400)
        except NotFoundError as error:
            return _json_error(str(error), 404)


def _require_json_body():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Pieprasījuma saturam jābūt derīgam JSON.")
    return payload


def _json_error(message, status_code):
    return jsonify({"error": message}), status_code


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
