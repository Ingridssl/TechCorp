"""
Autenticação do Portal do Candidato (e-mail + senha).
Separado do login interno para evitar conflitos de roles.
"""
from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import CandidatoConta, Candidatura, CandidatoDocumento
from security import verify_password, hash_password
from email_service import send_email
from extensions import limiter
import jwt, os, secrets
from datetime import datetime, timedelta, timezone

bp_cand = Blueprint("candidato_auth", __name__)

SECRET = os.getenv("CANDIDATO_JWT_SECRET", os.getenv("SECRET_KEY", "fallback-secret"))


def _create_token(email: str) -> str:
    payload = {
        "sub":  email,
        "role": "CANDIDATO",
        "exp":  datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])


@bp_cand.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def candidato_login():
    data  = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "")

    db    = SessionLocal()
    conta = db.query(CandidatoConta).filter(CandidatoConta.email == email).first()
    db.close()

    if not conta or not conta.senha_hash or not verify_password(senha, conta.senha_hash):
        return jsonify({"message": "E-mail ou senha inválidos."}), 401

    return jsonify({"token": _create_token(email)})


@bp_cand.route("/minhas-candidaturas", methods=["GET"])
def minhas_candidaturas():
    """Retorna as candidaturas do candidato autenticado."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"message": "Não autorizado."}), 401
    try:
        payload = _decode_token(auth.split(" ", 1)[1])
    except Exception:
        return jsonify({"message": "Token inválido."}), 401

    email = payload["sub"]
    db    = SessionLocal()
    cands = db.query(Candidatura).filter(Candidatura.email == email).all()
    db.close()

    return jsonify([{
        "id":         c.id,
        "job_id":     c.job_id,
        "status":     c.status,
        "applied_at": c.applied_at.isoformat() if c.applied_at else None,
    } for c in cands])


@bp_cand.route("/solicitar-reset", methods=["POST"])
@limiter.limit("5 per hour")
def solicitar_reset():
    """Envia e-mail de redefinição de senha ao candidato."""
    data  = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    db    = SessionLocal()
    conta = db.query(CandidatoConta).filter(CandidatoConta.email == email).first()
    if conta:
        token          = secrets.token_hex(32)
        conta.reset_token  = token
        conta.reset_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
        db.commit()
        link = f"{request.host_url}candidato/definir-senha?token={token}"
        send_email(email, "Redefinir senha — Portal do Candidato",
                   f"<p><a href='{link}'>Clique aqui</a> para redefinir sua senha (válido 2h).</p>")
    db.close()
    # Sempre retorna 200 para não expor se e-mail existe
    return jsonify({"message": "Se o e-mail estiver cadastrado, você receberá um link."})
