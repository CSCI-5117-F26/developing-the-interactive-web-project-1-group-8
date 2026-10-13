# Majority of the Auth0 code is based on the new Auth0 docs:
# https://auth0.com/docs/quickstart/webapp/python

from flask import session
import os
from auth0_server_python.auth_server.server_client import ServerClient
from dotenv import load_dotenv

load_dotenv()


class MemoryStateStore:
    def __init__(self):
        self._data = {}

    async def get(self, key, options=None):
        return self._data.get((session.get("auth0_browser_id"), key))

    async def set(self, key, value, options=None):
        self._data[(session["auth0_browser_id"], key)] = value

    async def delete(self, key, options=None):
        self._data.pop((session.get("auth0_browser_id"), key), None)

    async def delete_by_logout_token(self, claims, options=None):
        pass


class MemoryTransactionStore:
    def __init__(self):
        self._data = {}

    async def get(self, key, options=None):
        return self._data.get((session.get("auth0_browser_id"), key))

    async def set(self, key, value, options=None):
        self._data[(session["auth0_browser_id"], key)] = value

    async def delete(self, key, options=None):
        self._data.pop((session.get("auth0_browser_id"), key), None)


state_store = MemoryStateStore()
transaction_store = MemoryTransactionStore()


def create_auth0():
    # Create per request so HTTP connections don't reuse a closed event loop.
    return ServerClient(
        domain=os.environ["AUTH0_DOMAIN"],
        client_id=os.environ["AUTH0_CLIENT_ID"],
        client_secret=os.environ["AUTH0_CLIENT_SECRET"],
        secret=os.environ["AUTH0_SECRET"],
        redirect_uri=os.environ["AUTH0_REDIRECT_URI"],
        state_store=state_store,
        transaction_store=transaction_store,
        authorization_params={"scope": "openid profile email"},
    )
