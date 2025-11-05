# auth.py
import os, requests
from functools import wraps
from flask import request, jsonify, g
from jose import jwk, jwt
from jose.utils import base64url_decode

# Your Netlify site Identity endpoints
NETLIFY_ISSUER = os.getenv(
    "NETLIFY_ISSUER",
    "https://virtualteacher.netlify.app/.netlify/identity"
)
NETLIFY_JWKS = os.getenv(
    "NETLIFY_JWKS",
    "https://virtualteacher.netlify.app/.netlify/identity/.well-known/jwks.json"
)

# Cache the JWKS keys on import
_JWKS = requests.get(NETLIFY_JWKS, timeout=10).json().get("keys", [])

def _verify_netlify_jwt(token: str):
    # Verify signature using JWKS
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key_data = next((k for k in _JWKS if k.get("kid") == kid), None)
    if not key_data:
        raise Exception("Unknown key id")

    key = jwk.construct(key_data)
    signing_input, crypto_segment = token.rsplit(".", 1)
    decoded_sig = base64url_decode(crypto_segment.encode())
    if not key.verify(signing_input.encode(), decoded_sig):
        raise Exception("Invalid signature")

    claims = jwt.get_unverified_claims(token)
    if claims.get("iss") != NETLIFY_ISSUER:
        raise Exception("Invalid issuer")
    return claims

def require_professor(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing token"}), 401
        token = auth.split()[1]
        try:
            claims = _verify_netlify_jwt(token)
            roles = (claims.get("app_metadata") or {}).get("roles") or []
            if "professor" not in roles:
                return jsonify({"error": "forbidden"}), 403
            # expose identity for handlers
            g.user_id = claims.get("sub")
            g.email = claims.get("email")
        except Exception as e:
            return jsonify({"error": "invalid token", "detail": str(e)}), 401
        return f(*args, **kwargs)
    return wrapper
