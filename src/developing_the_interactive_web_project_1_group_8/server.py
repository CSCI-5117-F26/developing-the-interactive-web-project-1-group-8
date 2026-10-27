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
import os
import secrets
from datetime import timezone
from urllib.parse import urlencode
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth
from io import BytesIO
import warnings
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, UnidentifiedImageError
from psycopg.errors import UniqueViolation

from developing_the_interactive_web_project_1_group_8 import db
from developing_the_interactive_web_project_1_group_8.api import (
    api,
)
from developing_the_interactive_web_project_1_group_8.decorators import (
    requires_auth,
    requires_setup,
)
from developing_the_interactive_web_project_1_group_8.avatars import (
    MAX_AVATAR_BYTES,
    prepare_avatar,
    upload_avatar,
)

from developing_the_interactive_web_project_1_group_8.event_times import (
    CENTRAL,
    parse_utc_time,
    is_event_completed,
    is_event_time_completed,
)

db.setup()

load_dotenv()
app = Flask(__name__)

PROFILE_PRIVACY_FIELDS = (
    ("hosted_events_visibility", "Hosted events"),
    ("attending_events_visibility", "Attending events"),
    ("friends_visibility", "Friends list and friend count"),
    ("followers_visibility", "Follower count"),
)

# Auth0 code based on https://docs.authlib.org/en/stable/oauth2/client/web/flask.html
app.config.update(
    SECRET_KEY=os.environ["AUTH0_SECRET"],
    SESSION_COOKIE_SECURE=os.environ["APP_BASE_URL"].startswith("https://"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

FRIEND_LINK_DURATIONS = (
    (1, "1 hour"),
    (24, "1 day"),
    (168, "7 days"),
    (720, "30 days"),
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


@app.before_request
def require_account_setup():
    profile = session.get("profile")
    if profile is None:
        return
    if profile.get("setup_complete") and profile.get("username"):
        return
    if request.endpoint in {
        "static",
        "login",
        "callback",
        "logout",
        "username",
        "set_username",
    }:
        return
    if (
        request.endpoint == "api.avatar_image"
        and request.view_args["user_id"] == profile["id"]
    ):
        return

    if request.endpoint == "friend_invite":
        session["friend_invite"] = request.view_args["token"]
    if request.blueprint == "api":
        return jsonify(
            error="Choose a username before using the app.",
            setup_url=url_for("username"),
        ), 403
    return redirect(url_for("username"))


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


# https://flask.palletsprojects.com/en/stable/templating/#context-processors
@app.context_processor
def notification_summary():
    profile = session.get("profile")
    if profile and profile.get("setup_complete") and profile.get("username"):
        return {
            "unread_notification_count": db.get_unread_notification_count(profile["id"])
        }
    return {"unread_notification_count": 0}


@app.route("/account/notifications", methods=["GET", "POST"])
@requires_auth
@requires_setup
def notifications():
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    user_id = current_user["id"]
    page = max(request.args.get("page", 1, type=int), 1)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "mark_read":
            notification_id = request.form.get("notification_id", type=int)
            if db.mark_notification_read(notification_id, user_id):
                flash("Notification marked as read.")
            else:
                flash("That notification is already read or unavailable.")
        elif action == "mark_all_read":
            db.mark_all_notifications_read(user_id)
            flash("All notifications are marked as read.")
        else:
            flash("Choose a notification action.")
        return redirect(url_for("notifications", page=page))

    entries = db.get_notifications(user_id, limit=21, offset=(page - 1) * 20)
    has_older = len(entries) > 20
    entries = entries[:20]
    for entry in entries:
        entry["created_at"] = entry["created_at"].astimezone(timezone.utc)
        entry["url"] = None
        if entry["kind"] == "friend_request":
            entry["url"] = url_for("friend_requests")
        elif entry["kind"] == "friend_accepted":
            if entry["user_username"] is not None:
                entry["url"] = url_for("user", username=entry["user_username"])
        elif entry["event_public_id"] is not None:
            entry["url"] = url_for("event", public_id=entry["event_public_id"])
    return render_template(
        "account/notifications.html",
        notifications=entries,
        page=page,
        has_older=has_older,
        current_user=current_user,
    )


def format_time(dt):
    if dt is None:
        return "N/A"

    dt = dt.astimezone(CENTRAL)
    return f"{dt.hour % 12 or 12}:{dt.strftime('%M %p, %a %b')} {dt.day} {dt.year} {dt.tzname()}"


@app.template_filter()
def format_tile_time(dt):
    return format_time(dt)


@app.template_filter()
def format_page_time(dt):
    return format_time(dt)


@app.template_filter()
def format_event_input(dt):
    return dt.astimezone(CENTRAL).strftime("%Y-%m-%dT%H:%M") if dt else ""


@app.template_test("past")
def is_past(time):
    return is_event_time_completed(time)


@app.route("/")
def index():
    """Dashboard page, where users can explore for new events"""
    if "profile" not in session:
        events = db.get_all_event_info()
        sections = [
            ("Events in the Next Week", db.get_events_in_week(None)),
        ]
    else:
        user_id = session["profile"]["id"]
        sections = [
            ("Hosted Events", db.get_user_events(user_id, user_id)),
            ("Events Attending", db.get_user_events_attending(user_id, user_id)),
            ("Events in the Next Week", db.get_events_in_week(user_id)),
            ("Events from Users You Follow", db.get_all_friend_events(user_id)),
            ("All Events", db.get_all_event_info(user_id)),
        ]
    return render_template("index.html", sections=sections)


@app.route("/login")
async def login():
    """Login page, where users can log in to their account"""
    session["login_event"] = request.args.get("event")
    return auth0.authorize_redirect(os.environ["AUTH0_REDIRECT_URI"])


@app.route("/callback")
async def callback():
    token = auth0.authorize_access_token()
    user_info = token["userinfo"]
    user_exists = db.get_sub(user_info["sub"])
    user = db.get_or_create_user(user_info)

    friend_invite = session.get("friend_invite")
    login_event = session.get("login_event")
    session.clear()
    if friend_invite:
        session["friend_invite"] = friend_invite
    if login_event:
        session["login_event"] = login_event
    session["profile"] = {
        "id": user["id"],
        "sub": user["auth0_sub"],
        "username": user["username"],
        "setup_complete": user["setup_complete"],
        "profile_pic": user["profile_pic"] or None,
    }
    if user_exists and user["setup_complete"] and user["username"]:
        if login_event:
            session.pop("login_event")
            return redirect(url_for("event", public_id=login_event))
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


@app.route("/account/connections", methods=["GET", "POST"])
@requires_auth
@requires_setup
def connections():
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    user_id = current_user["id"]
    if request.method == "POST":
        action = request.form.get("action")
        if action not in {"unfriend", "unfollow", "remove_follower", "unblock"}:
            flash("Choose a connection action.")
            return redirect(url_for("connections"))

        other_user_id = request.form.get("user_id", type=int)
        other_user = db.get_user_from_id(other_user_id)
        if other_user is None:
            flash("This account is no longer available.")
        elif other_user_id == user_id:
            flash("Choose another account.")
        elif action == "unfriend":
            if db.remove_friend(user_id, other_user_id):
                flash(
                    f"You unfriended @{other_user['username']}. Your follow settings are unchanged."
                )
            else:
                flash(f"You are not friends with @{other_user['username']}.")
        elif action == "remove_follower":
            if db.unfollow_user(other_user_id, user_id):
                flash(
                    f"You removed @{other_user['username']} as a follower. They can follow you again."
                )
            else:
                flash(f"@{other_user['username']} is not following you.")
        elif action == "unfollow":
            if db.unfollow_user(user_id, other_user_id):
                flash(
                    f"You no longer follow @{other_user['username']}. Your friendships are unchanged."
                )
            else:
                flash(f"You are not following @{other_user['username']}.")
        elif action == "unblock":
            if db.unblock_user(user_id, other_user_id):
                flash(
                    f"You unblocked @{other_user['username']}. Previous friendships and follows were not restored."
                )
            else:
                flash(f"You have no block on @{other_user['username']}.")
        return redirect(url_for("connections"))

    sections = [
        ("friends", "Friends", db.get_friends(user_id), "No friends yet."),
        (
            "following",
            "Following",
            db.get_following(user_id),
            "You are not following anyone yet.",
        ),
        ("followers", "Followers", db.get_followers(user_id), "No followers yet."),
        (
            "blocked",
            "Blocked",
            db.get_blocked_users(user_id),
            "You have not blocked anyone.",
        ),
    ]
    return render_template(
        "account/connections.html", current_user=current_user, sections=sections
    )


@app.after_request
def keep_invitation_pages_private(response):
    if request.endpoint in {
        "invitations",
        "friend_invite",
        "friend_requests",
        "notifications",
    }:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.route("/account/invitations", methods=["GET", "POST"], endpoint="invitations")
@app.route("/account/friend-requests", methods=["GET", "POST"])
@requires_auth
@requires_setup
def friend_requests():
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    if request.endpoint == "invitations" and request.method == "GET":
        return redirect(url_for("friend_requests", _anchor="friend-links"))

    current_user_id = current_user["id"]
    errors = []
    values = {"max_uses": "1", "duration_hours": "168"}
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            values = {
                "max_uses": request.form.get("max_uses", ""),
                "duration_hours": request.form.get("duration_hours", ""),
            }
            max_uses = request.form.get("max_uses", type=int)
            duration_hours = request.form.get("duration_hours", type=int)
            if max_uses is None or not 1 <= max_uses <= 100:
                errors.append("Choose a use limit between 1 and 100.")
            if duration_hours not in dict(FRIEND_LINK_DURATIONS):
                errors.append("Choose one of the available durations.")
            if not errors:
                token = secrets.token_urlsafe(32)
                db.create_friend_invitation(
                    current_user["id"], token, max_uses, duration_hours
                )
                flash("Friend link created. Copy it from your active links below.")
                return redirect(url_for("friend_requests"))
        elif action == "revoke":
            invitation_id = request.form.get("invitation_id", type=int)
            if db.revoke_friend_invitation(invitation_id, current_user["id"]):
                flash("Friend link revoked. Existing friendships are unchanged.")
            else:
                flash(
                    "That invitation is not an active link belonging to your account."
                )
            return redirect(url_for("friend_requests"))
        elif action == "send":
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
        if not errors:
            return redirect(url_for("friend_requests"))

    active_invitations = db.get_active_friend_invitations(current_user_id)
    for invitation in active_invitations:
        invitation["link"] = os.environ["APP_BASE_URL"].rstrip("/") + url_for(
            "friend_invite", token=invitation["token"]
        )
        invitation["expires_at"] = invitation["expires_at"].astimezone(timezone.utc)
    return render_template(
        "account/friend_requests.html",
        current_user=current_user,
        received_requests=db.get_received_friend_requests(current_user_id),
        sent_requests=db.get_sent_friend_requests(current_user_id),
        invitations=active_invitations,
        values=values,
        errors=errors,
        durations=FRIEND_LINK_DURATIONS,
    )


@app.route("/username")
@requires_auth
def username():
    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    elif current_user["setup_complete"] and current_user["username"]:
        return redirect(url_for("user", username=current_user["username"]))
    else:
        return render_template("account/username.html")


@app.route("/set-username", methods=["POST"])
@requires_auth
def set_username():
    username = request.form.get("username", "")
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    setup_complete = current_user["setup_complete"] and bool(current_user["username"])
    errors = []
    if not 3 <= len(username) <= 20:
        errors.append("Username must be between 3 and 20 characters.")
    if not username.isascii() or not username.isalnum():
        errors.append(
            "Username may contain only alphanumeric characters with no spaces."
        )

    existing_user_id = db.get_id_for_username(username)
    if existing_user_id is not None and existing_user_id != current_user["id"]:
        errors.append("Username is already in use; choose something unique.")

    if not errors:
        display_name = current_user["display_name"]
        if not setup_complete:
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
        if setup_complete:
            flash("Username updated.")
            return redirect(url_for("settings"))
        flash("Your account is ready.")
        login_event = session.pop("login_event", None)
        if login_event:
            return redirect(url_for("event", public_id=login_event))
        friend_invite = session.get("friend_invite")
        if friend_invite:
            return redirect(url_for("friend_invite", token=friend_invite))
        return redirect(url_for("settings"))

    if setup_complete:
        values = {
            "username": username,
            "display_name": current_user["display_name"] or "",
            "bio": current_user["bio"] or "",
            "profile_pic": current_user["profile_pic"] or "",
            "delete_avatar": False,
        }
        return render_template(
            "account/settings.html",
            user=current_user,
            values=values,
            errors=errors,
            privacy_fields=PROFILE_PRIVACY_FIELDS,
            privacy_values=current_user,
        )

    return render_template(
        "account/username.html",
        username=username,
        errors=errors,
    )


@app.route("/friend-invite/<string:token>", methods=["GET", "POST"])
def friend_invite(token):
    invitation = db.get_friend_invitation(token)
    if invitation is None:
        return render_template(
            "account/friend_invite.html",
            unavailable=True,
            unavailable_message="This link is invalid or no longer available. Ask for a new invitation.",
        ), 404

    owner_id = invitation["owner_id"]
    owner = db.get_user_from_id(owner_id)
    if owner is None or not owner["setup_complete"] or not owner["username"]:
        return render_template("account/friend_invite.html", unavailable=True), 404

    current_user = None
    if "profile" in session:
        current_user = db.get_user_from_id(session["profile"]["id"])
        if current_user is None:
            session.clear()
    if current_user is not None and (
        db.is_blocked(owner_id, current_user["id"])
        or db.is_blocked(current_user["id"], owner_id)
    ):
        return render_template("account/friend_invite.html", unavailable=True), 403

    if invitation["status"] != "active":
        messages = {
            "revoked": "This friend invitation has been revoked.",
            "expired": "This friend invitation has expired.",
            "exhausted": "This friend invitation has no uses remaining.",
        }
        return render_template(
            "account/friend_invite.html",
            unavailable=True,
            unavailable_message=messages[invitation["status"]],
        ), 410

    if current_user is None:
        session["friend_invite"] = token
        return render_template(
            "account/friend_invite.html", owner=owner, needs_login=True
        )
    if not current_user["setup_complete"]:
        session["friend_invite"] = token
        return redirect(url_for("username"))

    session.pop("friend_invite", None)
    current_user_id = current_user["id"]
    own_link = owner_id == current_user_id
    already_friends = db.are_friends(owner_id, current_user_id)
    if request.method == "POST":
        if own_link:
            flash("This is your own friend link. Share it with someone else.")
        elif already_friends:
            flash("You are already friends with this user.")
        elif db.accept_friend_invite(token, current_user_id):
            flash(
                "Friend invitation accepted. You are now friends and follow each other."
            )
            return redirect(url_for("user", username=owner["username"]))
        else:
            flash(
                "This invitation is no longer available or you are already friends. Check the invitation again."
            )
        return redirect(url_for("friend_invite", token=token))

    return render_template(
        "account/friend_invite.html",
        owner=owner,
        current_user=current_user,
        needs_login=False,
        own_link=own_link,
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


def can_view_profile_section(visibility, is_owner, is_friend):
    return is_owner or visibility == "public" or (visibility == "friends" and is_friend)


@app.route("/user/<string:username>")
def user(username):
    profile = db.get_public_user(username)
    if profile is None:
        abort(404, "This user does not appear to exist.")

    profile_id = profile["id"]
    viewer_id = session["profile"]["id"] if "profile" in session else None
    is_owner = viewer_id == profile_id
    profile["is_following"] = False
    profile["is_blocked"] = False
    profile["is_friend"] = False

    if viewer_id is not None and not is_owner:
        blocked_by_owner = db.is_blocked(profile_id, viewer_id)
        blocked_by_viewer = db.is_blocked(viewer_id, profile_id)
        if blocked_by_owner or blocked_by_viewer:
            return render_template(
                "account/profile_blocked.html",
                username=username,
                blocked_by_owner=blocked_by_owner,
                blocked_by_viewer=blocked_by_viewer,
            ), 403
        profile["is_following"] = db.is_following(viewer_id, profile_id)
        profile["is_friend"] = db.are_friends(viewer_id, profile_id)

    friends = None
    profile["followers"] = None
    sections = []
    if can_view_profile_section(
        profile["friends_visibility"], is_owner, profile["is_friend"]
    ):
        friends = db.get_friends(profile_id)
    if can_view_profile_section(
        profile["followers_visibility"], is_owner, profile["is_friend"]
    ):
        profile["followers"] = db.get_follower_count(profile_id)
    if can_view_profile_section(
        profile["hosted_events_visibility"], is_owner, profile["is_friend"]
    ):
        sections.append(
            (
                "Hosted Events",
                db.get_user_events(profile_id, session.get("profile", {}).get("id")),
            )
        )
    if can_view_profile_section(
        profile["attending_events_visibility"], is_owner, profile["is_friend"]
    ):
        sections.append(
            (
                "Events Attending",
                db.get_user_events_attending(
                    profile_id, session.get("profile", {}).get("id")
                ),
            )
        )

    return render_template(
        "account/user.html",
        sections=sections,
        friends=friends,
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
            "delete_avatar": False,
        }
    errors = []

    if request.method == "POST":
        values["delete_avatar"] = request.form.get("delete_avatar") == "1"
        values["display_name"] = request.form.get("display_name", "").strip()
        values["bio"] = request.form.get("bio", "")
        if not 1 <= len(values["display_name"]) <= 40:
            errors.append("Display name must be between 1 and 40 characters.")
        if len(values["bio"]) > 200:
            errors.append("Biography must be 200 characters or fewer.")
        if values["delete_avatar"]:
            values["profile_pic"] = ""
        elif not errors:
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
                                    errors.append("Choose a JPEG, PNG, or WebP image.")
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
                        avatar_key = upload_avatar(prepared_image, current_user["id"])
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
            flash("Profile saved.")
            return redirect(url_for("settings"))

    return render_template(
        "account/settings.html",
        user=current_user,
        values=values,
        errors=errors,
        privacy_fields=PROFILE_PRIVACY_FIELDS,
        privacy_values=current_user,
    )


@app.post("/account/privacy")
@requires_auth
@requires_setup
def privacy_settings():
    current_user = db.get_user_from_id(session["profile"]["id"])
    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    privacy_values = {}
    errors = []
    for name, label in PROFILE_PRIVACY_FIELDS:
        privacy_values[name] = request.form.get(name, "")
        if privacy_values[name] not in {"public", "friends", "private"}:
            errors.append("Choose who can see your " + label.lower() + ".")

    if not errors:
        updated_user = db.update_profile_privacy(
            current_user["id"],
            privacy_values["hosted_events_visibility"],
            privacy_values["attending_events_visibility"],
            privacy_values["friends_visibility"],
            privacy_values["followers_visibility"],
        )
        if updated_user is None:
            session.clear()
            return redirect(url_for("index"))
        flash("Profile privacy saved.")
        return redirect(url_for("settings"))

    values = {
        "username": current_user["username"],
        "display_name": current_user["display_name"] or "",
        "bio": current_user["bio"] or "",
        "profile_pic": current_user["profile_pic"] or "",
        "delete_avatar": False,
    }
    return render_template(
        "account/settings.html",
        user=current_user,
        values=values,
        errors=errors,
        privacy_fields=PROFILE_PRIVACY_FIELDS,
        privacy_values=privacy_values,
    )


@app.route("/myevents")
@requires_auth
@requires_setup
def my_events():
    """Page with many events"""
    user_id = session["profile"]["id"]
    events = db.get_user_events(user_id, user_id)
    hosted_ids = {event["id"] for event in events}
    events += [
        event
        for event in db.get_user_events_attending(user_id, user_id)
        if event["id"] not in hosted_ids
    ]
    # print(events)
    return render_template("events/my_events.html", events=events)


@app.route("/search")
def search():
    """Search page, where users can search for events"""
    q = request.args.get("q", type=str)
    game = request.args.get("game", "", type=str)
    game_name = request.args.get("game-name", "", type=str)
    category = request.args.get("category", "", type=str)
    category_name = request.args.get("category-name", "", type=str)
    min_players = request.args.get("min", None, type=int)
    max_players = request.args.get("max", None, type=int)
    duration = request.args.get("duration", None, type=int)
    recency = request.args.get("recency", "", type=str)
    full = request.args.get("full", False, type=bool)
    pending = request.args.get("pending", False, type=bool)
    played = request.args.get("played", False, type=bool)
    user_id = session["profile"]["id"] if session.get("profile") else None
    results = db.search_events(
        q,
        user_id,
        game,
        category,
        category_name,
        min_players,
        max_players,
        duration,
        recency,
        full,
        pending,
        played,
    )

    return render_template(
        "search.html",
        query=q,
        game=game if game_name else "",
        game_name=game_name,
        category=category,
        category_name=category_name,
        min_players=min_players,
        max_players=max_players,
        duration=duration,
        recency=recency,
        full=full,
        pending=pending,
        played=played,
        results=results,
    )


@app.route("/event/<string:public_id>")
def event(public_id):
    """
    Event page, where users can view details about a specific event

    """

    event = db.get_event_by_public_id(public_id)
    if event is None:
        abort(404, "This event does not appear to exist.")
    event = db.get_event_info(event["id"], session.get("profile", {}).get("id"))

    attendees = db.get_all_event_attendees(event["id"])

    return render_template("events/event.html", event=event, attendees=attendees)


@app.route("/create-event")
@requires_auth
def create_event():
    """Event form, where users can insert info about their event"""
    # print(database.get_event(event_id))
    return render_template("events/event_info.html", event=None)


@app.post("/add-event")
@requires_auth
def add_event():
    print(request.form)
    print(session["profile"]["id"])
    visibility = request.form.get("visibility")
    if visibility not in ("public", "friends", "private"):
        return render_template(
            "error.html",
            message="Choose Public, Friends only, or Private for event visibility.",
        ), 400
    try:
        event_time = parse_utc_time(request.form.get("time"))
    except ValueError:
        return render_template(
            "error.html", message="Choose a valid event time in Central Time (CT)."
        ), 400
    db.create_event(
        request.form.get("name"),
        request.form.get("search-value") or request.form.get("gameid"),
        session["profile"]["id"],
        request.form.get("address"),
        event_time,
        request.form.get("expected_duration"),
        request.form.get("min_attendees"),
        request.form.get("max_attendees"),
        request.form.get("description"),
        "scheduled",
        visibility,
    )

    return redirect("/")


@app.post("/rsvp/<string:public_id>")
@requires_auth
def rsvp(public_id):
    event = db.get_event_by_public_id(public_id)
    if event is None:
        abort(404, "This event does not appear to exist.")
    event_id = event["id"]
    user_id = session["profile"]["id"]
    if (
        event["status"] == "Canceled"
        or is_event_completed(event)
        or event["hostid"] == user_id
        or event["count"] >= event["max_attendees"]
    ):
        return redirect(url_for("event", public_id=public_id))
    db.attend_event(event_id, user_id, False)
    return redirect("/")


@app.post("/decommit/<string:public_id>")
@requires_auth
def decommit(public_id):
    event = db.get_event_by_public_id(public_id)
    if event is None:
        abort(404, "This event does not appear to exist.")
    event_id = event["id"]
    if is_event_completed(event):
        return redirect(url_for("event", public_id=public_id))
    user_id = session["profile"]["id"]
    db.decommit_event(event_id, user_id)
    return redirect("/")


@app.route("/event/<string:public_id>/edit")
@requires_auth
def edit_event(public_id):
    """Event form, where users can edit info about their event"""
    edited_event = db.get_event_by_public_id(public_id)
    if edited_event is None:
        abort(404, "This event does not appear to exist.")
    event_id = edited_event["id"]
    # TODO There should be a check as to whether edited_event.hostid == the
    # userID of the session holder, 403 otherwise
    print(session["profile"])
    print(edited_event)
    if session["profile"]["id"] == edited_event["hostid"]:
        db.add_game_info([edited_event])
        return render_template("events/event_info.html", event=edited_event)
    else:
        # print(session["profile"]["user"])
        return redirect(url_for("event", public_id=public_id))


@app.post("/update-event/<string:public_id>")
@requires_auth
def update_event(public_id):
    event = db.get_event_by_public_id(public_id)
    if event is None:
        abort(404, "This event does not appear to exist.")
    event_id = event["id"]
    check_event = db.get_event_info(event_id, session["profile"]["id"])
    if check_event is None:
        abort(404, "This event does not appear to exist.")

    if check_event["hostid"] != session["profile"]["id"]:
        abort(404, "This event does not belong to you.")

    if check_event["count"] > int(request.form.get("max_attendees")):
        abort(
            404,
            "Cannot adjust an event's max attendees lower than the number of participants.",
        )

    visibility = request.form.get("visibility")
    if visibility not in ("public", "friends", "private"):
        return render_template(
            "error.html",
            message="Choose Public, Friends only, or Private for event visibility.",
        ), 400
    try:
        event_time = parse_utc_time(request.form.get("time"), check_event["time"])
    except ValueError:
        return render_template(
            "error.html", message="Choose a valid event time in Central Time (CT)."
        ), 400

    db.update_event(
        event_id,
        request.form.get("name"),
        request.form.get("search-value") or request.form.get("gameid"),
        request.form.get("address"),
        event_time,
        request.form.get("expected_duration"),
        request.form.get("min_attendees"),
        request.form.get("max_attendees"),
        request.form.get("description"),
        visibility,
    )

    return redirect("/")


@app.post("/event/<string:public_id>/cancel")
@requires_auth
def cancel_event(public_id):
    choice = request.form.get("action")

    if choice != "temporary" and choice != "permanent":
        abort(404, "Bad Request.")

    check_event = db.get_event_by_public_id(public_id)
    if check_event is None:
        abort(404, "This event does not appear to exist.")
    event_id = check_event["id"]

    if check_event["hostid"] != session["profile"]["id"]:
        abort(404, "This event does not belong to you.")

    if choice == "permanent":
        db.delete_event(event_id)
    else:
        db.cancel_event(event_id)

    return redirect("/")


@app.post("/event/<string:public_id>/restore")
@requires_auth
def restore_event(public_id):
    check_event = db.get_event_by_public_id(public_id)
    if check_event is None:
        abort(404, "This event does not appear to exist.")
    event_id = check_event["id"]

    if check_event["hostid"] != session["profile"]["id"]:
        abort(404, "This event does not belong to you.")

    db.restore_event(event_id)

    return redirect("/")


# ---------- Error Handlers ----------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", message=e.description), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", message=e.description), 404
