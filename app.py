import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

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


def _redirect_with_notice(endpoint, message, level="success", **values):
    values["notice"] = message
    values["notice_level"] = level
    return redirect(url_for(endpoint, **values))


def _login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return redirect(url_for("login"))

        user = get_user_by_id(get_db(), user_id)
        if user is None:
            session.clear()
            return _redirect_with_notice("login", "Sesija beidzās. Ieej vēlreiz.", "error")

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
    _register_routes(app)
    return app

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
                return _redirect_with_notice(
                    "login",
                    "Konts izveidots. Tagad vari ieiet.",
                    "success",
                    username=user["username"],
                )
            except ValidationError as error:
                return _redirect_with_notice("register", str(error), "error")

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
                return _redirect_with_notice("dashboard", "Prieks redzēt atkal.", "success")
            except AuthenticationError as error:
                username = (request.form.get("username") or "").strip()
                return _redirect_with_notice("login", str(error), "error", username=username)

        return render_template("login.html")

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        return _redirect_with_notice("login", "Tu esi izrakstījies.", "success")

    @app.route("/dashboard", methods=["GET", "POST"])
    @_login_required
    def dashboard():
        if request.method == "POST":
            try:
                save_profile(get_db(), session["user_id"], request.form)
                return _redirect_with_notice("dashboard", "Tavs krājuma plāns ir atjaunināts.", "success")
            except ValidationError as error:
                return _redirect_with_notice("dashboard", str(error), "error")

        return render_template("dashboard.html")

    @app.post("/dashboard/quick-add")
    @_login_required
    def quick_add():
        try:
            add_quick_amount(get_db(), session["user_id"], request.form)
            return _redirect_with_notice("dashboard", "Pašreizējais atlikums atjaunināts.", "success")
        except ValidationError as error:
            return _redirect_with_notice("dashboard", str(error), "error")

    @app.get("/api/dashboard-data")
    @_login_required
    def api_dashboard_data():
        user = get_user_by_id(get_db(), session["user_id"])
        dashboard_data = get_dashboard_data(get_db(), session["user_id"])
        return jsonify(
            {
                **dashboard_data,
                "username": user["username"],
            }
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}


app = create_app()


if __name__ == "__main__":
    print("Atver http://127.0.0.1:5000/ pārlūkā. Neatver templates mapes failus pa tiešo.")
    app.run(debug=True)
