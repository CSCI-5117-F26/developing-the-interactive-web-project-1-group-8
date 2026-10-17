from developing_the_interactive_web_project_1_group_8.decorators import requires_auth
import validators
from urllib.parse import urlencode, urlsplit
from developing_the_interactive_web_project_1_group_8 import db
from developing_the_interactive_web_project_1_group_8.db import get_public_user, get_user
import psycopg
import faker
from flask import Flask, jsonify, Blueprint, request, render_template, abort, url_for, session, redirect

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


# get user account photo
@api.route("/api/user/<int:user_id>/photo", methods=["GET"])
def get_user_photo(user_id):
    """
    Get the account photo for a user.

    Parameters:
      user_id (int): The ID of the user.
    """
    profile = get_public_user(user_id)

    if profile is None:
        abort(404)

    avatar_url = profile["profile_pic"]

    if not is_safe_avatar_url(avatar_url):
        avatar_url = url_for("static", filename="default-avatar.svg")

    return avatar_url


# ---------- Follow ----------
@api.route("/api/user/<int:user_id>/follow", methods=["POST"])
@requires_auth
def follow_user(user_id):
    """
    Follow a user.

    Parameters:
      user_id (int): The ID of the user to follow.
    """

    current_user = get_user(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    
    current_user_id = current_user["id"]

    if current_user_id == user_id:
        return jsonify({"error": "You cannot follow yourself"}), 400
    if db.is_following(current_user_id, user_id):
        return jsonify({"error": "You are already following this user"}), 400

    try:
        db.follow_user(current_user_id, user_id)
        return jsonify({"message": "User followed successfully"}), 200
    except psycopg.errors.UniqueViolation:
        return jsonify({"error": "You are already following this user"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@api.route("/api/user/<int:user_id>/unfollow", methods=["POST"])
@requires_auth
def unfollow_user(user_id):
    """
    Unfollow a user.

    Parameters:
      user_id (int): The ID of the user to unfollow.
    """

    current_user = get_user(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    
    current_user_id = current_user["id"]

    if current_user_id == user_id:
        return jsonify({"error": "You cannot unfollow yourself"}), 400

    try:
        db.unfollow_user(current_user_id, user_id)
        return jsonify({"message": "User unfollowed successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- Block ----------

@api.route("/api/user/<int:user_id>/block", methods=["POST"])
@requires_auth
def block_user(user_id):
    """
    Block a user.

    Parameters:
      user_id (int): The ID of the user to block.
    """

    current_user = get_user(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    
    current_user_id = current_user["id"]

    if current_user_id == user_id:
        return jsonify({"error": "You cannot block yourself"}), 400

    try:
        db.block_user(current_user_id, user_id)
        if db.is_following(current_user_id, user_id):
            db.unfollow_user(current_user_id, user_id)
        if db.is_following(user_id, current_user_id):
            db.unfollow_user(user_id, current_user_id)
        return jsonify({"message": "User blocked successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    

@api.route("/api/user/<int:user_id>/unblock", methods=["POST"])
@requires_auth
def unblock_user(user_id):
    """
    Unblock a user.

    Parameters:
      user_id (int): The ID of the user to unblock.
    """

    current_user = get_user(session["profile"]["id"])

    if current_user is None:
        session.clear()
        return redirect(url_for("index"))
    
    current_user_id = current_user["id"]

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
    query = request.args.get("q", type=str)

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    # search users, events, games ( ? )
    r = db.search_events(query)
    print(r)

    return jsonify(r), 200
