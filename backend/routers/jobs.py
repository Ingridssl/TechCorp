from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import Job, Candidatura
from security import decode_token
from audit import log as audit_log
from datetime import datetime, timezone

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _require_auth(roles=None):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"message": "Não autorizado."}), 401)
    try:
        payload = decode_token(auth.split(" ", 1)[1])
        if roles and payload.get("role") not in roles:
            return None, (jsonify({"message": "Sem permissão."}), 403)
        return payload, None
    except Exception:
        return None, (jsonify({"message": "Token inválido."}), 401)


@bp.route("", methods=["GET"])
def list_jobs():
    """Lista vagas abertas (público — usado no formulário de candidatura)."""
    db   = SessionLocal()
    jobs = db.query(Job).filter(Job.status == "OPEN").order_by(Job.created_at.desc()).all()
    db.close()
    return jsonify([{
        "id":        j.id,
        "position":  j.position,
        "location":  j.location,
        "tipo":      j.tipo,
        "num_vagas": j.num_vagas,
        "finalidade":j.finalidade,
    } for j in jobs])


@bp.route("/all", methods=["GET"])
def list_all_jobs():
    """Lista todas as vagas (requer autenticação)."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH", "ROLE_GESTOR"])
    if err:
        return err

    db   = SessionLocal()
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    db.close()
    return jsonify([{
        "id":         j.id,
        "position":   j.position,
        "location":   j.location,
        "tipo":       j.tipo,
        "num_vagas":  j.num_vagas,
        "status":     j.status,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "expires_at": j.expires_at.isoformat() if j.expires_at else None,
    } for j in jobs])


@bp.route("", methods=["POST"])
def create_job():
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH"])
    if err:
        return err

    data = request.get_json() or {}
    if not data.get("position") or not data.get("location"):
        return jsonify({"message": "Cargo e localidade são obrigatórios."}), 400

    db  = SessionLocal()
    job = Job(
        position    = data["position"],
        location    = data["location"],
        tipo        = data.get("tipo"),
        num_vagas   = data.get("num_vagas", 1),
        finalidade  = data.get("finalidade"),
        responsavel = data.get("responsavel"),
        email_resp  = data.get("email_resp"),
        status      = "OPEN",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    audit_log(payload["sub"], "CREATE_JOB", "job", job.id, f"Vaga: {job.position}")
    db.close()
    return jsonify({"id": job.id, "message": "Vaga criada com sucesso."}), 201


@bp.route("/<int:job_id>", methods=["PATCH"])
def update_job(job_id):
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH"])
    if err:
        return err

    db  = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return jsonify({"message": "Vaga não encontrada."}), 404

    data = request.get_json() or {}
    for field in ("position", "location", "tipo", "num_vagas", "finalidade", "status"):
        if field in data:
            setattr(job, field, data[field])

    db.commit()
    audit_log(payload["sub"], "UPDATE_JOB", "job", job_id)
    db.close()
    return jsonify({"message": "Vaga atualizada."})


@bp.route("/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    payload, err = _require_auth(["ROLE_ADMIN"])
    if err:
        return err

    db  = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return jsonify({"message": "Vaga não encontrada."}), 404

    db.delete(job)
    db.commit()
    audit_log(payload["sub"], "DELETE_JOB", "job", job_id)
    db.close()
    return jsonify({"message": "Vaga removida."})
