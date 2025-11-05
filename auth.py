# auth.py
import os
import functools
import requests
from flask import request, g, jsonify

NETLIFY_ISSUER = os.getenv("NETLIFY_ISSUER", "").rstrip("/")

def _bearer_token(auth_header: str) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def _fetch_netlify_user(token: str) -> dict:
    """Ask Netlify Identity to validate the token and return the user JSON."""
    url = f"{NETLIFY_ISSUER}/user"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if resp.status_code != 200:
        raise ValueError(f"Identity /user status {resp.status_code}")
    data = resp.json()  # contains email, app_metadata.roles, etc.
    roles = (data.get("app_metadata") or {}).get("roles") or []
    return {
        "id": data.get("id"),
        "email": data.get("email"),
        "roles": roles,
        "raw": data,
    }

def require_professor(view_fn):
    """Decorator that requires a valid Netlify Identity token with role 'professor' or 'admin'."""
    @functools.wraps(view_fn)
    def wrapper(*args, **kwargs):
        token = _bearer_token(request.headers.get("Authorization"))
        if not token:
            return jsonify({"error": "missing bearer token"}), 401
        try:
            user = _fetch_netlify_user(token)
        except Exception as e:
            return jsonify({"error": "invalid token", "detail": str(e)}), 401

        roles = set(r.lower() for r in user["roles"])
        if "professor" not in roles and "admin" not in roles:
            return jsonify({"error": "forbidden: professor role required"}), 403

        # Stash on flask.g for downstream use
        g.user = user
        g.email = user["email"]
        return view_fn(*args, **kwargs)
    return wrapper
