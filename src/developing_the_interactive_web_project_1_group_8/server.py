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
    request,
    jsonify,
)
import validators
import os
from urllib.parse import urlencode, urlsplit
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth
from io import BytesIO
import warnings
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, UnidentifiedImageError
from psycopg.errors import UniqueViolation
from itsdangerous import BadSignature, URLSafeSerializer

from developing_the_interactive_web_project_1_group_8 import db
from developing_the_interactive_web_project_1_group_8.api import (
    api,
    is_safe_avatar_url,
    get_user_photo,
)
from developing_the_interactive_web_project_1_group_8.decorators import (
    requires_auth,
    requires_setup,
)
import developing_the_interactive_web_project_1_group_8.db as db
from developing_the_interactive_web_project_1_group_8.avatars import (
    MAX_AVATAR_BYTES,
    prepare_avatar,
    upload_avatar,
)

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

# https://itsdangerous.palletsprojects.com/en/stable/url_safe/
# https://itsdangerous.palletsprojects.com/en/stable/concepts/
friend_link_signer = URLSafeSerializer(app.secret_key, salt="friend-invite")

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


@app.before_request
def limit_avatar_request():
    if request.endpoint == "settings" and request.method == "POST":
        request.max_content_length = MAX_AVATAR_BYTES + 64 * 1024


@app.errorhandler(413)
def upload_too_large(e):
    return render_template(
        "error.html",
        message="Upload is too large. Choose an avatar of 5 MiB or smaller.",
    ), 413


# https://flask-wtf.readthedocs.io/en/1.2.x/csrf/
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

    friend_invite = session.get("friend_invite")
    session.clear()
    if friend_invite:
        session["friend_invite"] = friend_invite
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "username": user["username"],
        "setup_complete": user["setup_complete"],
        "profile_pic": user["profile_pic"] or None,
    }
    if user_exists and user["setup_complete"]:
        if friend_invite:
            return redirect(url_for("friend_invite", token=friend_invite))
        return redirect(url_for("user", username=user["username"]))
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

    return redirect(url_for("settings"))


@app.route("/account/friend-requests", methods=["GET", "POST"])
@requires_auth
@requires_setup
def friend_requests():
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    current_user_id = current_user["id"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "send":
            username = request.form.get("username", "").strip()
            recipient = db.get_public_user(username)
            if recipient is None:
                flash("No user with that username was found.")
            elif recipient["id"] == current_user_id:
                flash("You cannot send a friend request to yourself.")
            elif db.is_blocked(current_user_id, recipient["id"]) or db.is_blocked(
                recipient["id"], current_user_id
            ):
                flash("Friend requests are unavailable for this user.")
            elif db.are_friends(current_user_id, recipient["id"]):
                flash("You are already friends with this user.")
            else:
                sent_request = db.send_friend_request(current_user_id, recipient["id"])
                if sent_request:
                    flash("Friend request sent. You are following this user.")
                else:
                    flash(
                        "A friend request is already pending between you and this user."
                    )
        elif action == "accept":
            requester_id = request.form.get("user_id", type=int)
            accepted = db.accept_friend_request(requester_id, current_user_id)
            if accepted:
                flash(
                    "Friend request accepted. You are now friends. You also follow each other."
                )
            else:
                flash("That request is no longer available to accept.")
        elif action == "cancel":
            recipient_id = request.form.get("user_id", type=int)
            removed = db.cancel_friend_request(current_user_id, recipient_id)
            if removed:
                flash("Friend request cancelled.")
            else:
                flash("That sent request is no longer pending.")
        elif action == "decline":
            requester_id = request.form.get("user_id", type=int)
            removed = db.cancel_friend_request(requester_id, current_user_id)
            if removed:
                flash("Friend request declined.")
            else:
                flash("That received request is no longer pending.")
        else:
            flash("Choose a friend request action.")
        return redirect(url_for("friend_requests"))

    return render_template(
        "friend_requests.html",
        current_user=current_user,
        received_requests=db.get_received_friend_requests(current_user_id),
        sent_requests=db.get_sent_friend_requests(current_user_id),
    )


@app.route("/username")
@requires_auth
def username():
    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    elif current_user["setup_complete"]:
        return redirect(url_for("user", username=current_user["username"]))
    else:
        return render_template("username.html")


@app.route("/set-username", methods=["POST"])
@requires_auth
def set_username():
    username = request.form.get("username", "")
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    errors = []
    if not 3 <= len(username) <= 30:
        errors.append("Username must be between 3 and 30 characters.")
    if not username.isascii() or not username.isalnum():
        errors.append(
            "Username may contain only alphanumeric characters with no spaces."
        )

    existing_user_id = db.get_id_for_username(username)
    if existing_user_id is not None and existing_user_id != current_user["id"]:
        errors.append("Username is already in use; choose something unique.")

    if not errors:
        display_name = current_user["display_name"]
        if not current_user["setup_complete"]:
            display_name = username

        # TODO: enforce 24 hr limit for username changes
        try:
            updated_user = db.update_username(
                current_user["id"], username, display_name
            )
        except UniqueViolation:
            errors.append("Username is already in use; choose something unique.")

    if not errors:
        if updated_user is None:
            session.clear()
            return redirect(url_for("index"))

        session["profile"] = {
            "id": updated_user["id"],
            "sub": updated_user["auth0_sub"],
            "display_name": updated_user["display_name"],
            "profile_pic": updated_user["profile_pic"],
            "username": updated_user["username"],
            "setup_complete": updated_user["setup_complete"],
        }
        flash("Username updated.")
        if current_user["setup_complete"]:
            return redirect(url_for("settings"))
        friend_invite = session.get("friend_invite")
        if friend_invite:
            return redirect(url_for("friend_invite", token=friend_invite))
        return redirect(url_for("user", username=updated_user["username"]))

    if current_user["setup_complete"]:
        values = {
            "username": username,
            "display_name": current_user["display_name"] or "",
            "bio": current_user["bio"] or "",
            "profile_pic": current_user["profile_pic"] or "",
        }
        return render_template(
            "settings.html",
            user=current_user,
            values=values,
            errors=errors,
        )

    return render_template(
        "username.html",
        username=username,
        errors=errors,
    )


@app.route("/friend-invite/<string:token>", methods=["GET", "POST"])
def friend_invite(token):
    try:
        owner_id = friend_link_signer.loads(token)
    except BadSignature:
        abort(404, "This friend link is invalid.")

    owner = db.get_user_from_id(owner_id)
    if owner is None or not owner["setup_complete"]:
        abort(404, "This friend link is no longer available.")

    current_user = None
    if "profile" in session:
        current_user = db.get_user_from_id(session["profile"]["id"])
        if current_user is None:
            session.clear()
    if current_user is None:
        session["friend_invite"] = token
        return render_template("friend_invite.html", owner=owner, needs_login=True)
    if not current_user["setup_complete"]:
        session["friend_invite"] = token
        return redirect(url_for("username"))

    session.pop("friend_invite", None)
    current_user_id = current_user["id"]
    own_link = owner_id == current_user_id
    unavailable = db.is_blocked(owner_id, current_user_id) or db.is_blocked(
        current_user_id, owner_id
    )
    already_friends = db.are_friends(owner_id, current_user_id)
    if request.method == "POST":
        if own_link:
            flash("This is your own friend link. Share it with someone else.")
        elif unavailable:
            flash("This friend invitation is unavailable.")
        elif already_friends:
            flash("You are already friends with this user.")
        elif db.accept_friend_invite(owner_id, current_user_id):
            flash(
                "Friend invitation accepted. You are now friends and follow each other."
            )
        else:
            flash("This invitation was already accepted or is no longer available.")
        return redirect(url_for("friend_invite", token=token))

    return render_template(
        "friend_invite.html",
        owner=owner,
        current_user=current_user,
        needs_login=False,
        own_link=own_link,
        unavailable=unavailable,
        already_friends=already_friends,
    )


@app.post("/user/<int:user_id>/remove-friend")
@requires_auth
@requires_setup
def remove_friend(user_id):
    other_user = db.get_user_from_id(user_id)
    if other_user is None:
        abort(404, "This user does not appear to exist.")
    removed = db.remove_friend(session["profile"]["id"], user_id)
    if removed:
        flash("Friend removed. Your follow settings are unchanged.")
    else:
        flash("You are no longer friends with this user.")
    return redirect(url_for("user", username=other_user["username"]))


@app.route("/user/<string:username>")
def user(username):
    profile = db.get_public_user(username)

    if profile is None:
        abort(404, "This user does not appear to exist.")

    profile_id = profile["id"]
    profile["followers"] = db.get_follower_count(profile_id)
    profile["is_following"] = False
    profile["is_blocked"] = False
    profile["is_friend"] = False

    if "profile" in session and db.is_blocked(profile_id, session["profile"]["id"]):
        # this is deception, we don't want to tell the user that they are blocked, we just want to make it look like the user doesn't exist
        abort(403, "This user does not appear to exist.")

    events = db.get_user_events(profile_id)
    going_events = db.get_user_events_attending(profile_id)
    friends = db.get_friends(profile_id)
    friend_ids = {friend["id"] for friend in friends}
    following = []
    for followed_user in db.get_following(profile_id):
        if followed_user["id"] not in friend_ids:
            following.append(followed_user)
    friend_link = None
    sections = [("Hosted Events", events), ("Events Going To", going_events)]

    if "profile" in session:
        current_user_id = session["profile"]["id"]
        profile["is_following"] = db.is_following(current_user_id, profile_id)
        profile["is_blocked"] = db.is_blocked(current_user_id, profile_id)
        profile["is_friend"] = db.are_friends(current_user_id, profile_id)
        if current_user_id == profile_id and profile["setup_complete"]:
            token = friend_link_signer.dumps(profile_id)
            friend_link = os.environ["APP_BASE_URL"].rstrip("/") + url_for(
                "friend_invite", token=token
            )

    return render_template(
        "user.html",
        sections=sections,
        following=following,
        friends=friends,
        friend_link=friend_link,
        user=profile,
    )


# https://flask.palletsprojects.com/en/stable/patterns/fileuploads/
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

    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete_avatar":
            values["profile_pic"] = ""
        else:
            values["display_name"] = request.form.get("display_name", "").strip()
            values["bio"] = request.form.get("bio", "")
            if not 1 <= len(values["display_name"]) <= 80:
                errors.append("Display name must be between 1 and 80 characters.")
            if len(values["bio"]) > 200:
                errors.append("Biography must be 200 characters or fewer.")
            if not errors:
                avatar_file = request.files.get("avatar")
                if avatar_file is not None and avatar_file.filename:
                    image_data = avatar_file.stream.read(MAX_AVATAR_BYTES + 1)
                    if len(image_data) > MAX_AVATAR_BYTES:
                        errors.append("Avatar must be 5 MB or smaller.")

                    if not errors:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter(
                                    "error", Image.DecompressionBombWarning
                                )
                                with Image.open(BytesIO(image_data)) as image:
                                    if image.format not in {"JPEG", "PNG", "WEBP"}:
                                        errors.append(
                                            "Choose a JPEG, PNG, or WebP image."
                                        )
                                    if getattr(image, "is_animated", False):
                                        errors.append(
                                            "Choose a still image rather than an animation."
                                        )
                                    if not errors:
                                        prepared_image = prepare_avatar(image)
                        except (
                            UnidentifiedImageError,
                            OSError,
                            ValueError,
                            Image.DecompressionBombWarning,
                            Image.DecompressionBombError,
                        ):
                            errors.append("Choose a valid JPEG, PNG, or WebP image.")

                    if not errors:
                        try:
                            avatar_key = upload_avatar(
                                prepared_image, current_user["id"]
                            )
                            values["profile_pic"] = avatar_key
                        except KeyError:
                            errors.append(
                                "Avatar storage is not configured yet. Your current avatar is unchanged."
                            )
                        except BotoCoreError, ClientError:
                            errors.append(
                                "Avatar upload failed. Your current avatar is unchanged."
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
                "username": updated_user["username"],
                "display_name": updated_user["display_name"],
                "profile_pic": updated_user["profile_pic"],
                "setup_complete": updated_user["setup_complete"],
            }
            if action == "delete_avatar":
                flash("Avatar deleted. The default avatar is now in use.")
            else:
                flash("Profile saved.")
            return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        user=current_user,
        values=values,
        errors=errors,
    )


@app.route("/myevents")
@requires_auth
@requires_setup
def my_events():
    """Page with many events"""
    user_id = session["profile"]["id"]
    events = db.get_user_events(user_id)
    hosted_ids = {event["id"] for event in events}
    events += [
        event
        for event in db.get_user_events_attending(user_id)
        if event["id"] not in hosted_ids
    ]
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
        abort(404, "This event does not appear to exist.")
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
    result = db.create_event(
        request.form.get("name"),
        request.form.get("gameid"),
        session["profile"]["id"],
        request.form.get("address"),
        request.form.get("time") or None,
        request.form.get("expected_duration"),
        request.form.get("max_attendees"),
        request.form.get("description"),
        "scheduled",
    )

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
    if edited_event is None:
        abort(404, "This event does not appear to exist.")
    # TODO There should be a check as to whether edited_event.hostid == the
    # userID of the session holder, 403 otherwise
    print(session["profile"])
    print(edited_event)
    if session["profile"]["id"] == edited_event["hostid"]:
        return render_template("event_info.html", event=edited_event)
    else:
        # print(session["profile"]["user"])
        return redirect("/event/" + str(event_id))


@app.post("/update-event/<int:event_id>")
@requires_auth
def update_event(event_id):
    check_event = db.get_event_info(event_id)
    if check_event is None:
        abort(404, "This event does not appear to exist.")

    if check_event["hostid"] != session["profile"]["id"]:
        abort(404, "This event does not belong to you.")

    if check_event["count"] > int(request.form.get("max_attendees")):
        abort(
            404,
            "Cannot adjust an event's max attendees lower than the number of participants.",
        )

    db.update_event(
        event_id,
        request.form.get("name"),
        request.form.get("gameid"),
        request.form.get("address"),
        request.form.get("time") or None,
        request.form.get("expected_duration"),
        request.form.get("max_attendees"),
        request.form.get("description"),
        "scheduled",
    )

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
