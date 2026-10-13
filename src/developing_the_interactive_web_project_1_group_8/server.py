from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    abort,
    flash,
    request,
)
import validators
import os
from urllib.parse import urlencode, urlsplit
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

from developing_the_interactive_web_project_1_group_8.api import api
from developing_the_interactive_web_project_1_group_8.decorators import requires_auth
from developing_the_interactive_web_project_1_group_8.db import (
    get_or_create_user,
    get_user,
    get_public_user,
    update_profile,
)

load_dotenv()
app = Flask(__name__)

# Auth0 code based on https://docs.authlib.org/en/stable/oauth2/client/web/flask.html
app.config.update(
    SECRET_KEY=os.environ["AUTH0_SECRET"],
    SESSION_COOKIE_SECURE=os.environ["APP_BASE_URL"].startswith("https://"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

oauth = OAuth(app)
auth0 = oauth.register(
    name="auth0",
    client_id=os.environ["AUTH0_CLIENT_ID"],
    client_secret=os.environ["AUTH0_CLIENT_SECRET"],
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=(
        f"https://{os.environ['AUTH0_DOMAIN']}/.well-known/openid-configuration"
    ),
)

# https://flask-wtf.readthedocs.io/en/0.15.x/csrf/
CSRFProtect(app)

app.register_blueprint(api)


# https://nandgator.github.io/pyvalidators/stable/api/url/
def is_safe_avatar_url(url):
    if not url or validators.url(url) is not True:
        return False

    # https://docs.python.org/3/library/urllib.parse.html
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https" and parsed.username is None and parsed.password is None
    )


@app.route("/")
def index():
    """Dashboard page, where users can explore for new events"""
    return render_template("index.html")


@app.route("/login")
async def login():
    """Login page, where users can log in to their account"""
    return auth0.authorize_redirect(os.environ["AUTH0_REDIRECT_URI"])


@app.route("/callback")
async def callback():
    token = auth0.authorize_access_token()
    user_info = token["userinfo"]
    user = get_or_create_user(user_info)

    session.clear()
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "display_name": user["display_name"],
    }
    return redirect(url_for("account"))


@app.route("/logout", methods=["POST"])
@requires_auth
def logout():
    session.clear()
    # https://auth0.com/docs/authenticate/login/logout/redirect-users-after-logout
    # https://docs.python.org/3/library/urllib.parse.html
    parameters = urlencode(
        {
            "client_id": os.environ["AUTH0_CLIENT_ID"],
            "returnTo": url_for("index", _external=True),
        }
    )
    return redirect(f"https://{os.environ['AUTH0_DOMAIN']}/v2/logout?{parameters}")


@app.route("/account")
@requires_auth
def account():
    user = get_user(session["profile"]["id"])
    if user is None:
        session.clear()
        return redirect(url_for("index"))

    # Ensure session profile is up to date with database
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "display_name": user["display_name"],
    }

    return render_template("account.html", user=user)


@app.route("/user/<int:user_id>")
def user(user_id):
    profile = get_public_user(user_id)

    if profile is None:
        abort(404)

    avatar_url = profile["profile_pic"]

    if not is_safe_avatar_url(avatar_url):
        avatar_url = url_for("static", filename="default-avatar.svg")

    return render_template("user.html", user=profile, avatar_url=avatar_url)


@app.route("/account/settings", methods=["GET", "POST"])
@requires_auth
def settings():
    current_user = get_user(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    values = {
        "display_name": current_user["display_name"],
        "bio": current_user["bio"] or "",
    }
    errors = []

    if request.method == "POST":
        values = {
            "display_name": request.form.get("display_name", "").strip(),
            "bio": request.form.get("bio", ""),
        }
        if not 1 <= len(values["display_name"]) <= 80:
            errors.append("Display name must be between 1 and 80 characters.")
        if len(values["bio"]) > 4000:
            errors.append("Biography must be 4,000 characters or fewer.")

        if not errors:
            updated_user = update_profile(
                current_user["id"],
                values["display_name"],
                values["bio"],
            )
            if updated_user is None:
                session.clear()
                return redirect(url_for("index"))
            session["profile"] = {
                "id": updated_user["id"],
                "sub": updated_user["auth0_sub"],
                "display_name": updated_user["display_name"],
            }
            flash("Profile saved.")
            return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        user=current_user,
        values=values,
        errors=errors,
    )


@app.route("/search")
def search():
    """Search page, where users can search for events"""
    return render_template("search.html")


@app.route("/event/<int:event_id>")
def event(event_id):
    """Event page, where users can view details about a specific event"""
    return render_template("event.html", event_id=event_id)
