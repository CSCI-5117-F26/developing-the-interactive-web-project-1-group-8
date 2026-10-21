from functools import wraps
from flask import redirect, session, url_for, current_app


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "profile" not in session:
            # TODO: should probably pass user's original request in to route them along after logging in
            return redirect("/")
        return current_app.ensure_sync(f)(*args, **kwargs)

    return decorated

def requires_setup(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print(session['profile'])
        if "profile" in session and not session['profile'].get('setup_complete', False):
            return redirect("/username")
        return current_app.ensure_sync(f)(*args, **kwargs)

    return decorated
