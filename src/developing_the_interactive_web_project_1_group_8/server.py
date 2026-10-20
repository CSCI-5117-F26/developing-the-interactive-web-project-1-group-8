from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    abort,
    flash,
    request, jsonify,
)
import os
from urllib.parse import urlencode, urlsplit
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

from developing_the_interactive_web_project_1_group_8 import db
from developing_the_interactive_web_project_1_group_8.api import api, is_safe_avatar_url, get_user_photo
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

@app.route("/")
def index():
    """Dashboard page, where users can explore for new events"""
    events = db.get_all_events()
    sections = [
        ("Events from Popular Games", events),
        ("Events from Games You've Played", events),
        ("Events in the Next Week", events),
        ("Friend Events!", events),
    ]
    return render_template("index.html", sections=sections)


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
        "profile_pic": user["profile_pic"] or None,
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
        "profile_pic": user["profile_pic"] or None,
    }

    return render_template("account.html", user=user)


@app.route("/user/<int:user_id>")
def user(user_id):
    profile = get_public_user(user_id)
    if profile is None:
        abort(404, "This user does not appear to exist.")
    profile["followers"] =  db.get_follower_count(user_id)
    profile["is_following"] = False
    profile["is_blocked"] = False

    if db.is_blocked(user_id, session["profile"]["id"]):
        # this is deception, we don't want to tell the user that they are blocked, we just want to make it look like the user doesn't exist
        abort(403, "This user does not appear to exist.")

    events = db.get_user_events(user_id)
    going_events = db.get_user_events_attending(user_id)
    followers = db.get_following(user_id)
    sections = [
        ("Hosted Events", events),
        ("Events Going To", going_events)
    ]

    if "profile" in session:
        current_user_id = session["profile"]["id"]
        profile["is_following"] = db.is_following(current_user_id, user_id)
        profile["is_blocked"] = db.is_blocked(current_user_id, user_id)

    return render_template("user.html", sections=sections, following=followers, user=profile)


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
        "profile_pic": current_user["profile_pic"] or "",
    }
    errors = []
    can_restore_avatar = is_safe_avatar_url(current_user["auth0_avatar_url"])

    if request.method == "POST":
        if request.form.get("action") == "restore_avatar":
            values["profile_pic"] = current_user["auth0_avatar_url"] or ""
            if not can_restore_avatar:
                errors.append("No valid Auth0 avatar is available to restore.")
        else:
            values = {
                "display_name": request.form.get("display_name", "").strip(),
                "bio": request.form.get("bio", ""),
                "profile_pic": request.form.get("profile_pic", "").strip(),
            }
            if not 1 <= len(values["display_name"]) <= 80:
                errors.append("Display name must be between 1 and 80 characters.")
            if len(values["bio"]) > 200:
                errors.append("Biography must be 200 characters or fewer.")
            if values["profile_pic"] and (
                len(values["profile_pic"]) > 2048
                or not is_safe_avatar_url(values["profile_pic"])
            ):
                errors.append(
                    "Avatar must be an HTTPS URL of 2,048 characters or fewer, without a username or password."
                )

        if not errors:
            updated_user = update_profile(
                current_user["id"],
                values["display_name"],
                values["bio"],
                values["profile_pic"],
            )
            if updated_user is None:
                session.clear()
                return redirect(url_for("index"))
            
            session["profile"] = {
                "id": updated_user["id"],
                "sub": updated_user["auth0_sub"],
                "display_name": updated_user["display_name"],
                "profile_pic": updated_user["profile_pic"],
            }
            flash("Profile saved.")
            return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        user=current_user,
        values=values,
        errors=errors,
        can_restore_avatar=can_restore_avatar,
    )


@app.route("/myevents")
def my_events():
    """Page with many events"""
    events = db.get_all_events()
    # print(events)
    return render_template("my_events.html", events=events)


@app.route("/search")
def search():
    """Search page, where users can search for events"""
    q = request.args.get("q", type=str)

    return render_template("search.html", query=q, results=db.search_events(q))


@app.route("/event/<int:event_id>")
def event(event_id):
    """
    Event page, where users can view details about a specific event
    
    """

    event = db.get_event(event_id)
    if event is None:
        abort(404,"This event does appear to exist.")
    # print(db.get_event(event_id))
    return render_template("event.html", event=event)


# @app.route("/user/<string:username>")
# def user(username):
#     """ User page, where users can view details about a specific user """
#     if not username:
#         return render_template("error.html", message="Username is required"), 400
#     return render_template("user.html", username=username)




# ---------- Error Handlers ----------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", message=e.description), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", message=e.description), 404

