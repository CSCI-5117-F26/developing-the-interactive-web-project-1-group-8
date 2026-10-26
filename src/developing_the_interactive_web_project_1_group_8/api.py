from io import BytesIO
from botocore.exceptions import BotoCoreError, ClientError
import psycopg
from flask import jsonify, Blueprint, request
from developing_the_interactive_web_project_1_group_8.decorators import requires_auth
import validators
from urllib.parse import urlsplit
from developing_the_interactive_web_project_1_group_8 import db
from flask import (
    abort,
    url_for,
    session,
    redirect,
)

from flask import send_file
from developing_the_interactive_web_project_1_group_8.avatars import (
    download_avatar,
)
# this module holds all of the api endpoints


api = Blueprint("api", __name__, template_folder="templates")


# ---------- Events ----------


@api.route("/api/event/create", methods=["POST"])
def disp():
    """
    Create a new event.

    Parameters:
      name (str): The name of the new event.
      description (str): The description of the new event.
      date (str): The date of the new event.

    Returns:
      A JSON response indicating success or failure of event creation.
    """
    name = request.args.get("name", type=str)
    description = request.args.get("description", type=str)
    date = request.args.get("date", type=str)

    return jsonify({"data": name})


# ---------- Users ----------


@api.route("/api/user/create", methods=["GET", "POST"])
def userCreate():
    """
    Create an user.

    Parameters:
      username (str): The username for the new user.
      password (str): The password for the new user.

    Returns:
      A JSON response indicating success or failure of user creation.
    """
    username = request.args.get("username", type=str)
    password = request.args.get("password", type=str)

    # sanity checks for username and password
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400
    if len(username) < 5:
        return jsonify({"error": "Username must be at least 5 characters long"}), 400
    if len(username) > 32:
        return jsonify({"error": "Username must be at most 32 characters long"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400

    # TODO: Add logic to create the user in the database

    return jsonify({"message": "User created successfully"}), 201


# https://nandgator.github.io/pyvalidators/stable/api/url/
def is_safe_avatar_url(url):
    if not url or validators.url(url) is not True:
        return False

    # https://docs.python.org/3/library/urllib.parse.html
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https" and parsed.username is None and parsed.password is None
    )


@api.app_template_global()
def avatar_url(profile):
    picture = profile["profile_pic"]
    if picture and picture.startswith("avatars/"):
        return url_for("api.avatar_image", user_id=profile["id"])

    if is_safe_avatar_url(picture):
        return picture

    return url_for("static", filename="images/avatar-default.svg")


@api.get("/api/user/<int:user_id>/avatar")
def avatar_image(user_id):
    profile = db.get_user_from_id(user_id)
    if profile is None:
        abort(404)
    if "profile" in session and session["profile"]["id"] != profile["id"]:
        viewer_id = session["profile"]["id"]
        if db.is_blocked(viewer_id, profile["id"]) or db.is_blocked(
            profile["id"], viewer_id
        ):
            return redirect(url_for("static", filename="images/avatar-default.svg"))

    avatar_key = profile["profile_pic"]
    if not avatar_key or not avatar_key.startswith("avatars/"):
        return redirect(avatar_url(profile))

    try:
        image_data = download_avatar(avatar_key)
    except KeyError, BotoCoreError, ClientError:
        return redirect(url_for("static", filename="images/avatar-default.svg"))

    # https://tedboy.github.io/flask/generated/flask.send_file.html
    return send_file(BytesIO(image_data), mimetype="image/jpeg", etag=avatar_key)


# get user account photo
@api.route("/api/user/<string:username>/photo", methods=["GET"])
def get_user_photo(username):
    """
    Get the account photo for a user.

    Parameters:
      username (str): The username of the user.
    """
    profile = db.get_public_user(username)

    if profile is None:
        abort(404)
    if "profile" in session and session["profile"]["id"] != profile["id"]:
        viewer_id = session["profile"]["id"]
        if db.is_blocked(viewer_id, profile["id"]) or db.is_blocked(
            profile["id"], viewer_id
        ):
            return url_for("static", filename="images/avatar-default.svg")

    return avatar_url(profile)


# ---------- Follow ----------
@api.route("/api/user/<string:username>/follow", methods=["POST"])
@requires_auth
def follow_user(username):
    """
    Follow a user.

    Parameters:
      username (str): The username of the user to follow.
    """

    current_user = db.get_user_from_id(session["profile"]["id"])
    user_id = db.get_id_for_username(username)
    if user_id is None:
        abort(404, "This user does not appear to exist.")

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    current_user_id = session["profile"]["id"]

    if current_user_id == user_id:
        return jsonify({"error": "You cannot follow yourself"}), 400
    if db.is_blocked(current_user_id, user_id) or db.is_blocked(
        user_id, current_user_id
    ):
        return jsonify({"error": "Following is unavailable for this user"}), 400
    if db.is_following(current_user_id, user_id):
        return jsonify({"error": "You are already following this user"}), 400

    try:
        db.follow_user(current_user_id, user_id)
        return jsonify({"message": "User followed successfully"}), 200
    except psycopg.errors.UniqueViolation:
        return jsonify({"error": "You are already following this user"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/api/user/<string:username>/unfollow", methods=["POST"])
@requires_auth
def unfollow_user(username):
    """
    Unfollow a user.

    Parameters:
      usernamt (str): The username of the user to unfollow.
    """

    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    current_user_id = session["profile"]["id"]
    user_id = db.get_id_for_username(username)
    if user_id is None:
        abort(404, "This user does not appear to exist.")

    if current_user_id == user_id:
        return jsonify({"error": "You cannot unfollow yourself"}), 400

    try:
        db.unfollow_user(current_user_id, user_id)
        return jsonify({"message": "User unfollowed successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Block ----------


@api.route("/api/user/<string:username>/block", methods=["POST"])
@requires_auth
def block_user(username):
    """
    Block a user.

    Parameters:
      username (str): The username of the user to block.
    """

    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    current_user_id = session["profile"]["id"]
    user_id = db.get_id_for_username(username)
    if user_id is None:
        abort(404, "This user does not appear to exist.")

    if current_user_id == user_id:
        return jsonify({"error": "You cannot block yourself"}), 400

    try:
        db.block_user(current_user_id, user_id)
        return jsonify({"message": "User blocked successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/api/user/<string:username>/unblock", methods=["POST"])
@requires_auth
def unblock_user(username):
    """
    Unblock a user.

    Parameters:
      user_id (int): The ID of the user to unblock.
    """

    current_user = db.get_user_from_id(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))

    current_user_id = session["profile"]["id"]
    user_id = db.get_id_for_username(username)
    if user_id is None:
        abort(404, "This user does not appear to exist.")

    if current_user_id == user_id:
        return jsonify({"error": "You cannot unblock yourself"}), 400

    try:
        db.unblock_user(current_user_id, user_id)
        return jsonify({"message": "User unblocked successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Search ----------


@api.route("/api/search", methods=["GET"])
def search():
    """
    Search for users or events.

    Parameters:
      query (str): The search query.
    """
    q = request.args.get("q", type=str)
    game = request.args.get("game", "", type=str)
    category = request.args.get("category", "", type=str)
    category_name = request.args.get("category-name", "", type=str)
    min_players = request.args.get("min", None, type=int)
    max_players = request.args.get("max", None, type=int)
    duration = request.args.get("duration", None, type=int)
    recency = request.args.get('recency', "", type=str)
    full = request.args.get("full", False, type=bool)
    pending = request.args.get("pending", False, type=bool)
    played = request.args.get("played", False, type=bool)
    user_id = session['profile']['id'] if session.get("profile") else None;

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
        played
    )

    if not q:
        return jsonify({"error": "Search query is required"}), 400

    # search users, events, games ( ? )
    r = results
    #print(r)

    return jsonify(r), 200


@api.route("/api/search-games", methods=["GET"])
def searchGames():
    """
    Search for events from our bgg instance

    Parameters:
      query (str): The game query
    """
    query = request.args.get("q", type=str)

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    # search users, events, games ( ? )
    r = db.bgg.search(query)
    # filter so we only use game
    r = [game for game in r if game.type == "boardgame"]

    # sort so that the best match is first
    r.sort(key=lambda game: game.name.lower().find(query.lower()))
    r = [{"id": game.id, "name": game.name} for game in r]
    r = r[:10]  # limit to 10 results
    return jsonify(r), 200
