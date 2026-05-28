from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import User
from security import decode_token, hash_password, hash_token
from audit import log as audit_log
from email_service import send_email
import secrets
from datetime import datetime, timedelta, timezone

bp_colab = Blueprint("colaboradores", __name__, url_prefix="/api/colaboradores")


def _require_admin():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"message": "Não autorizado."}), 401)
    try:
        payload = decode_token(auth.split(" ", 1)[1])
        if payload.get("role") != "ROLE_ADMIN":
            return None, (jsonify({"message": "Apenas admins."}), 403)
        return payload, None
    except Exception:
        return None, (jsonify({"message": "Token inválido."}), 401)


@bp_colab.route("", methods=["GET"])
def listar():
    payload, err = _require_admin()
    if err:
        return err

    db    = SessionLocal()
    users = db.query(User).order_by(User.created_at.desc()).all()
    db.close()
    return jsonify([{
        "id":        u.id,
        "username":  u.username,
        "email":     u.email,
        "role":      u.role,
        "is_active": u.is_active,
    } for u in users])


@bp_colab.route("/convidar", methods=["POST"])
def convidar():
    """Envia convite por e-mail para novo usuário interno."""
    payload, err = _require_admin()
    if err:
        return err

    data = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    username = data.get("username", "").strip().lower()
    role     = data.get("role", "ROLE_RH")

    if not email or not username:
        return jsonify({"message": "Email e username são obrigatórios."}), 400

    db = SessionLocal()
    if db.query(User).filter((User.email == email) | (User.username == username)).first():
        db.close()
        return jsonify({"message": "Usuário já existe."}), 409

    token   = secrets.token_hex(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=48)

    user = User(
        username=username, email=email, role=role,
        is_active=False, invite_token=token, invite_expires=expires,
    )
    db.add(user)
    db.commit()

    link = f"{request.host_url}definir-senha?token={token}"
    send_email(email, "Convite para o NewRH",
               f"<p>Você foi convidado. <a href='{link}'>Defina sua senha</a> (válido 48h).</p>")

    audit_log(payload["sub"], "INVITE_USER", "user", user.id, f"Convidado: {email}")
    db.close()
    return jsonify({"message": "Convite enviado."}), 201
