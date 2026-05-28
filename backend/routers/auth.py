from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import User
from security import verify_password, create_token, hash_password, hash_token
from audit import log as audit_log
from extensions import limiter
from datetime import datetime, timedelta, timezone

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _get_user_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


@bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data     = request.get_json() or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    db   = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if not user or not user.password or not verify_password(password, user.password):
        return jsonify({"message": "Usuário ou senha inválidos."}), 401

    if not user.is_active:
        return jsonify({"message": "Conta inativa. Verifique seu e-mail de convite."}), 403

    token = create_token({"sub": user.username, "role": user.role})
    audit_log(username, "LOGIN", ip=_get_user_ip())

    return jsonify({
        "token":    token,
        "username": user.username,
        "role":     user.role,
    })


@bp.route("/logout", methods=["POST"])
def logout():
    # JWT é stateless — o logout é feito no frontend descartando o token
    return jsonify({"message": "Logout realizado."})


@bp.route("/me", methods=["GET"])
def me():
    """Retorna dados do usuário autenticado."""
    from functools import wraps
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"message": "Token ausente."}), 401

    token = auth_header.split(" ", 1)[1]
    try:
        from security import decode_token
        payload = decode_token(token)
    except Exception:
        return jsonify({"message": "Token inválido ou expirado."}), 401

    db   = SessionLocal()
    user = db.query(User).filter(User.username == payload["sub"]).first()
    db.close()

    if not user:
        return jsonify({"message": "Usuário não encontrado."}), 404

    return jsonify({
        "username": user.username,
        "email":    user.email,
        "role":     user.role,
    })
