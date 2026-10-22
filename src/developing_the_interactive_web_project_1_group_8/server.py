from wtforms.validators import DataRequired, Length
from wtforms import StringField
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
import validators
import os
from urllib.parse import urlencode, urlsplit
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

from developing_the_interactive_web_project_1_group_8 import db
from developing_the_interactive_web_project_1_group_8.api import api, is_safe_avatar_url, get_user_photo
from developing_the_interactive_web_project_1_group_8.decorators import requires_auth, requires_setup
import developing_the_interactive_web_project_1_group_8.db as db

db.setup()

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
    events = db.get_all_event_info()
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
    user_exists = db.get_sub(user_info["sub"])
    user = db.get_or_create_user(user_info)

    session.clear()
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "username": user["username"],
        "setup_complete": user["setup_complete"],
        "profile_pic": user["profile_pic"] or None,
    }
    if user_exists and user["setup_complete"]:
        return redirect(url_for("account"))
    else:
        return redirect(url_for("username"))


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
@requires_setup
def account():
    user = db.get_user_from_id(session["profile"]["id"])
    if user is None:
        session.clear()
        return redirect(url_for("index"))

    # Ensure session profile is up to date with database
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "username": user["username"],
        "setup_complete": user["setup_complete"],
        "profile_pic": user["profile_pic"] or None,
    }

    return render_template("account.html", user=user)

@app.route("/username")
@requires_auth
def username():
    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    elif current_user["setup_complete"]:
        return redirect(url_for("account"))
    else: 
        return render_template("username.html")

@app.route("/set-username", methods=["POST"])
@requires_auth
def set_username():
    username = request.form.get("username").strip()
    current_user = session["profile"]["id"]

    errors = []

    if not 3 <= len(username) <= 30:
        errors.append("Username must be between 1 and 30 characters.")
    check_exists = db.get_public_user(username)
    if check_exists:
        errors.append("Username is already in use. Choose a unique display name.")
    if not errors:
        updated_user = db.update_username(
            current_user,
            username
        )
        
        if updated_user is None:
            session.clear()
            return redirect(url_for("index"))
                
        session["profile"] = {
            "id": updated_user["id"],
            "sub": updated_user["auth0_sub"],
            "display_name": updated_user["display_name"],
            "profile_pic": updated_user["profile_pic"],
            "username": updated_user["username"],
            "setup_complete": updated_user["setup_complete"]
        }
        flash("Username updated.")
        return redirect(url_for("account"))
    
    return render_template(
        "username.html",
        username=username,
        errors=errors,
    )



@app.route("/user/<string:username>")
def user(username):
    profile = db.get_public_user(username)

    if profile is None:
        abort(404, "This user does not appear to exist.")
        
    profile_id = profile["id"]
    profile["followers"] =  db.get_follower_count(profile_id)
    profile["is_following"] = False
    profile["is_blocked"] = False

    if db.is_blocked(profile_id, session["profile"]["id"]):
        # this is deception, we don't want to tell the user that they are blocked, we just want to make it look like the user doesn't exist
        abort(403, "This user does not appear to exist.")

    events = db.get_user_events(username)
    going_events = db.get_user_events_attending(username)
    followers = db.get_following(profile_id)
    sections = [
        ("Hosted Events", events),
        ("Events Going To", going_events)
    ]

    if "profile" in session:
        current_user_id = session["profile"]["id"]
        profile["is_following"] = db.is_following(current_user_id, profile_id)
        profile["is_blocked"] = db.is_blocked(current_user_id, profile_id)

    return render_template("user.html", sections=sections, following=followers, user=profile)


@app.route("/account/settings", methods=["GET", "POST"])
@requires_auth
@requires_setup
def settings():
    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    else:
        values = {
            "username": current_user["username"],
            "display_name": current_user["display_name"] or "",
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
            check_exists = db.get_public_user(values["display_name"])
            if check_exists and check_exists["id"] != current_user["id"]:
                errors.append("Display name is already in use. Choose a unique display name.")
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
            updated_user = db.update_profile(
                current_user["id"],
                values["display_name"],
                values["bio"],
                values["profile_pic"] or None,
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
@requires_setup
def my_events():
    """Page with many events"""
    events = db.get_all_event_info()
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

    event = db.get_event_info(event_id)
    # print(event)
    if event is None:
        abort(404,"This event does appear to exist.")
    # print(db.get_event(event_id))
    return render_template("event.html", event=event)

@app.route("/create-event")
@requires_auth
def create_event():
    """Event form, where users can insert info about their event"""
    # print(database.get_event(event_id))
    return render_template("event_info.html", event=None)

@app.post("/add-event")
@requires_auth
def add_event():
    print(request.form)
    print(session["profile"]["id"])
    result = db.create_event(request.form.get("name"), request.form.get("gameid"),
                    session["profile"]["id"], request.form.get("address"),
                    request.form.get("time"), request.form.get("expected_duration"), 
                    request.form.get("max_attendees"), request.form.get("description"),
                    "scheduled")

    db.attend_event(result["id"], session["profile"]["id"], True)
    
    return redirect("/")

@app.route("/rsvp/<int:event_id>")
@requires_auth
def rsvp(event_id):

    db.attend_event(event_id, session["profile"]["id"], False)
    
    return redirect("/")

@app.route("/event/<int:event_id>/edit")
@requires_auth
def edit_event(event_id):
    """Event form, where users can edit info about their event"""
    edited_event = db.get_event(event_id)
    # TODO There should be a check as to whether edited_event.hostid == the
    # userID of the session holder, 403 otherwise
    print(session["profile"])
    print(edited_event)
    if (session["profile"]["id"] == edited_event["hostid"]):
        return render_template("event_info.html", event=edited_event)
    else:
        # print(session["profile"]["user"])
        return redirect("/event/" + str(event_id))

@app.post("/update-event/<int:event_id>")
@requires_auth
def update_event(event_id):
    check_event = db.get_event_info(event_id)

    if check_event["hostid"] != session["profile"]["id"]:
        abort(404,"This event does not belong to you.")

    if check_event["count"] > int(request.form.get("max_attendees")):
        abort(404,
        "Cannot adjust an event's max attendees lower than the number of participants.")
    
    db.update_event(event_id, request.form.get("name"), request.form.get("gameid"),
                    request.form.get("address"), request.form.get("time"), 
                    request.form.get("expected_duration"), request.form.get("max_attendees"),
                    request.form.get("description"), "scheduled")
    
    return redirect("/")

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

