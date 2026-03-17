import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for

from database import DEFAULT_DATABASE, get_db, init_app as init_database_app, init_db
from services import (
    AuthenticationError,
    ValidationError,
    add_quick_amount,
    authenticate_user,
    get_dashboard_data,
    get_user_by_id,
    register_user,
    save_profile,
)


def _format_currency(value):
    amount = float(value or 0)
    return f"EUR {amount:,.2f}"


def _login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return redirect(url_for("login"))

        user = get_user_by_id(get_db(), user_id)
        if user is None:
            session.clear()
            flash("Your session expired. Please log in again.", "error")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "development-secret-key"),
        DATABASE=str(DEFAULT_DATABASE),
    )

    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    init_database_app(app)
    _register_template_helpers(app)
    _register_routes(app)
    return app


def _register_template_helpers(app):
    @app.template_filter("currency")
    def currency_filter(value):
        return _format_currency(value)

    @app.template_filter("date_label")
    def date_label_filter(value):
        if not value:
            return "No target date"
        year, month, day = value.split("-")
        return f"{day}.{month}.{year}"

    @app.context_processor
    def inject_globals():
        user = None
        user_id = session.get("user_id")
        if user_id is not None:
            user = get_user_by_id(get_db(), user_id)
        return {"current_user": user}


def _register_routes(app):
    @app.get("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            try:
                user = register_user(get_db(), request.form)
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login", username=user["username"]))
            except ValidationError as error:
                flash(str(error), "error")

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            try:
                user = authenticate_user(get_db(), request.form)
                session.clear()
                session["user_id"] = user["id"]
                flash("Welcome back.", "success")
                return redirect(url_for("dashboard"))
            except AuthenticationError as error:
                flash(str(error), "error")

        return render_template("login.html", suggested_username=request.args.get("username", ""))

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard", methods=["GET", "POST"])
    @_login_required
    def dashboard():
        if request.method == "POST":
            try:
                save_profile(get_db(), session["user_id"], request.form)
                flash("Your savings plan was updated.", "success")
                return redirect(url_for("dashboard"))
            except ValidationError as error:
                flash(str(error), "error")

        dashboard_data = get_dashboard_data(get_db(), session["user_id"])
        return render_template("dashboard.html", dashboard=dashboard_data)

    @app.post("/dashboard/quick-add")
    @_login_required
    def quick_add():
        try:
            add_quick_amount(get_db(), session["user_id"], request.form)
            flash("Current balance updated.", "success")
        except ValidationError as error:
            flash(str(error), "error")
        return redirect(url_for("dashboard"))

    @app.get("/health")
    def health():
        return {"status": "ok"}


app = create_app()


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000/ in your browser. Do not open files inside templates/ directly.")
    app.run(debug=True)
