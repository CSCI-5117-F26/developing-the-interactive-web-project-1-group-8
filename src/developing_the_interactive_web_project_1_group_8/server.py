from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
)
import os
from urllib.parse import urlencode
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

from developing_the_interactive_web_project_1_group_8.api import api
from developing_the_interactive_web_project_1_group_8.decorators import requires_auth
from developing_the_interactive_web_project_1_group_8.db import get_or_create_user, get_user

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

    return render_template("account.html", user=session["profile"])


@app.route("/search")
def search():
    """Search page, where users can search for events"""
    return render_template("search.html")


@app.route("/event/<int:event_id>")
def event(event_id):
    """Event page, where users can view details about a specific event"""
    return render_template("event.html", event_id=event_id)


@app.route("/user/<string:username>")
def user(username):
    """User page, where users can view details about a specific user"""
    return render_template("user.html", username=username)
