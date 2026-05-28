from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import Candidatura, Job, StatusHistory
from security import decode_token
from audit import log as audit_log
from email_service import send_status_update
from datetime import datetime, timezone
import json

bp = Blueprint("candidaturas", __name__, url_prefix="/api/candidaturas")

FUNNEL_ORDER = [
    "PENDING", "TRIAGEM", "TRIAGEM_OK",
    "ENTREVISTA", "ENTREVISTA_OK",
    "APROVACAO_FINAL", "APPROVED", "REJECTED",
]


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


@bp.route("", methods=["POST"])
def apply():
    """Submete uma candidatura (rota pública)."""
    data = request.get_json() or {}

    required = ["job_id", "full_name", "cpf", "rg", "phone", "email"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"message": f"Campos obrigatórios: {', '.join(missing)}"}), 400

    db  = SessionLocal()
    job = db.query(Job).filter(Job.id == data["job_id"], Job.status == "OPEN").first()
    if not job:
        db.close()
        return jsonify({"message": "Vaga não encontrada ou encerrada."}), 404

    c = Candidatura(
        job_id       = data["job_id"],
        full_name    = data["full_name"],
        cpf          = data["cpf"],
        rg           = data["rg"],
        phone        = data["phone"],
        email        = data["email"],
        data_nascimento       = data.get("data_nascimento"),
        cidade_atual          = data.get("cidade_atual"),
        education             = data.get("education"),
        experience            = data.get("experience"),
        disponibilidade_viagem= data.get("disponibilidade_viagem"),
        motivation            = data.get("motivation"),
        linkedin              = data.get("linkedin"),
        nrs                   = json.dumps(data.get("nrs", [])),
        status                = "PENDING",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    db.close()
    return jsonify({"id": c.id, "message": "Candidatura enviada com sucesso!"}), 201


@bp.route("", methods=["GET"])
def list_candidaturas():
    """Lista candidaturas com filtros opcionais."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH", "ROLE_GESTOR"])
    if err:
        return err

    db   = SessionLocal()
    q    = db.query(Candidatura)

    job_id = request.args.get("job_id")
    status = request.args.get("status")
    if job_id:
        q = q.filter(Candidatura.job_id == int(job_id))
    if status:
        q = q.filter(Candidatura.status == status)

    items = q.order_by(Candidatura.applied_at.desc()).all()
    db.close()

    return jsonify([{
        "id":         c.id,
        "full_name":  c.full_name,
        "email":      c.email,
        "job_id":     c.job_id,
        "status":     c.status,
        "funnel_stage": c.funnel_stage,
        "applied_at": c.applied_at.isoformat() if c.applied_at else None,
    } for c in items])


@bp.route("/<int:cid>/status", methods=["PATCH"])
def update_status(cid):
    """Atualiza o status/funil de uma candidatura."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH"])
    if err:
        return err

    data       = request.get_json() or {}
    new_status = data.get("status")
    if new_status not in FUNNEL_ORDER:
        return jsonify({"message": "Status inválido."}), 400

    db = SessionLocal()
    c  = db.query(Candidatura).filter(Candidatura.id == cid).first()
    if not c:
        db.close()
        return jsonify({"message": "Candidatura não encontrada."}), 404

    old_status = c.status
    c.status   = new_status
    if new_status not in ("APPROVED", "REJECTED"):
        c.funnel_stage = new_status

    db.add(StatusHistory(
        candidatura_id = cid,
        old_status     = old_status,
        new_status     = new_status,
        changed_by     = payload["sub"],
        note           = data.get("note"),
    ))
    db.commit()

    # Notifica o candidato por e-mail
    send_status_update(c.email, c.full_name, new_status)

    audit_log(payload["sub"], "UPDATE_STATUS", "candidatura", cid,
              f"{old_status} → {new_status}")
    db.close()
    return jsonify({"message": "Status atualizado."})
