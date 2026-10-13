from flask import (
    Flask,
    render_template,
    redirect,
    request,
    url_for,
    session,
)
import os
import secrets
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from auth0_server_python.auth_types import LogoutOptions

from developing_the_interactive_web_project_1_group_8.api import api
from developing_the_interactive_web_project_1_group_8.decorators import requires_auth
from developing_the_interactive_web_project_1_group_8.auth import create_auth0

load_dotenv()
app = Flask(__name__)

# Majority of the Auth0 code is based on the new Auth0 docs:
# https://auth0.com/docs/quickstart/webapp/python
app.config.update(
    SECRET_KEY=os.environ["AUTH0_SECRET"],
    SESSION_COOKIE_SECURE=os.environ["APP_BASE_URL"].startswith("https://"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
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
    session.setdefault("auth0_browser_id", secrets.token_urlsafe(32))
    auth0 = create_auth0()
    return redirect(await auth0.start_interactive_login())


@app.route("/callback")
async def callback():
    auth0 = create_auth0()
    try:
        result = await auth0.complete_interactive_login(request.url)
        user_info = result["state_data"]["user"]
    except Exception as e:
        session.clear()
        return f"Authentication error: {str(e)}", 400

    # Clear any old session data but keep auth0_browser_id
    temp_browser_id = session["auth0_browser_id"]
    session.clear()
    session["auth0_browser_id"] = temp_browser_id

    session["profile"] = {
        "sub": user_info["sub"],
        "display_name": user_info["name"],
    }

    return redirect(url_for("account"))


@app.route("/logout", methods=["POST"])
@requires_auth
async def logout():
    """Logout and redirect to Auth0 logout"""
    auth0 = create_auth0()
    logout_url = await auth0.logout(LogoutOptions(return_to=url_for("index", _external=True)))
    session.clear()
    return redirect(logout_url)


@app.route("/account")
@requires_auth
async def account():
    auth0 = create_auth0()
    if await auth0.get_user() is None:
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
