from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import SolicitacaoVaga, Job
from security import decode_token
from audit import log as audit_log
from email_service import send_email
import secrets
from datetime import datetime, timezone

bp = Blueprint("solicitacoes", __name__, url_prefix="/api/solicitacoes")


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
def criar_solicitacao():
    """Cria uma solicitação de abertura de vaga (qualquer usuário autenticado)."""
    payload, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    required = ["position", "location", "num_vagas", "justificativa",
                "solicitante_nome", "solicitante_email"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"message": f"Campos obrigatórios: {', '.join(missing)}"}), 400

    db  = SessionLocal()
    sol = SolicitacaoVaga(
        position          = data["position"],
        location          = data["location"],
        tipo              = data.get("tipo"),
        num_vagas         = data["num_vagas"],
        finalidade        = data.get("finalidade"),
        justificativa     = data["justificativa"],
        solicitante_nome  = data["solicitante_nome"],
        solicitante_email = data["solicitante_email"],
        solicitante_user  = payload["sub"],
        status            = "PENDENTE",
        approval_token    = secrets.token_hex(32),
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)

    # Notifica RH/Admin por e-mail com link de aprovação
    link = f"{request.host_url}revisar-solicitacao?token={sol.approval_token}"
    send_email(
        data["solicitante_email"],
        f"[NewRH] Solicitação de vaga: {data['position']}",
        f"<p>Solicitação recebida. Aguardando aprovação.</p><p><a href='{link}'>Revisar</a></p>"
    )

    audit_log(payload["sub"], "CRIAR_SOLICITACAO", "solicitacao", sol.id)
    db.close()
    return jsonify({"id": sol.id, "message": "Solicitação criada e enviada para aprovação."}), 201


@bp.route("/revisar/<token>", methods=["GET"])
def revisar_solicitacao(token):
    """Retorna os dados de uma solicitação pelo token de aprovação."""
    db  = SessionLocal()
    sol = db.query(SolicitacaoVaga).filter(SolicitacaoVaga.approval_token == token).first()
    db.close()
    if not sol:
        return jsonify({"message": "Token inválido ou expirado."}), 404
    return jsonify({
        "id":            sol.id,
        "position":      sol.position,
        "location":      sol.location,
        "num_vagas":     sol.num_vagas,
        "justificativa": sol.justificativa,
        "solicitante":   sol.solicitante_nome,
        "status":        sol.status,
    })


@bp.route("/decidir/<token>", methods=["POST"])
def decidir_solicitacao(token):
    """Aprova ou rejeita uma solicitação via token (sem login)."""
    data   = request.get_json() or {}
    decisao = data.get("decisao")  # APROVADA | REJEITADA
    if decisao not in ("APROVADA", "REJEITADA"):
        return jsonify({"message": "Decisão inválida."}), 400

    db  = SessionLocal()
    sol = db.query(SolicitacaoVaga).filter(SolicitacaoVaga.approval_token == token).first()
    if not sol or sol.status != "PENDENTE":
        db.close()
        return jsonify({"message": "Solicitação não encontrada ou já decidida."}), 404

    sol.status          = decisao
    sol.aprovado_por    = data.get("aprovado_por", "via-link")
    sol.motivo_rejeicao = data.get("motivo") if decisao == "REJEITADA" else None
    sol.decidido_em     = datetime.now(timezone.utc)

    # Se aprovada, cria a vaga automaticamente
    if decisao == "APROVADA":
        job = Job(
            position   = sol.position,
            location   = sol.location,
            tipo       = sol.tipo,
            num_vagas  = sol.num_vagas,
            finalidade = sol.finalidade,
            status     = "OPEN",
        )
        db.add(job)
        db.flush()
        sol.job_id = job.id

    db.commit()
    db.close()
    return jsonify({"message": f"Solicitação {decisao.lower()} com sucesso."})
