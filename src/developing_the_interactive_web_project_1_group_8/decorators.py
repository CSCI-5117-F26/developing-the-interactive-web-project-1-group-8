from functools import wraps
from flask import redirect, session, current_app, request, url_for


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "profile" not in session:
            if request.endpoint == "rsvp":
                return redirect(url_for("login", event=kwargs["public_id"]))
            return redirect(url_for("login"))
        return current_app.ensure_sync(f)(*args, **kwargs)

    return decorated


def requires_setup(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "profile" in session and not session["profile"].get("setup_complete", False):
            return redirect("/username")
        return current_app.ensure_sync(f)(*args, **kwargs)

    return decorated
