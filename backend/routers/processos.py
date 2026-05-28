from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import ProcessoAdmissao, EtapaProcesso, DocumentoEtapa, Candidatura, ADMISSION_STEPS
from security import decode_token
from audit import log as audit_log
from datetime import datetime, timezone

bp = Blueprint("processos", __name__, url_prefix="/api/processos")


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
def iniciar_processo():
    """Inicia o processo de admissão para uma candidatura aprovada."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH"])
    if err:
        return err

    data          = request.get_json() or {}
    candidatura_id = data.get("candidatura_id")
    tipo_admissao  = data.get("tipo_admissao", "ADMISSAO_NOVA")

    db = SessionLocal()
    c  = db.query(Candidatura).filter(Candidatura.id == candidatura_id).first()
    if not c:
        db.close()
        return jsonify({"message": "Candidatura não encontrada."}), 404

    # Verifica se já existe processo para essa candidatura
    existing = db.query(ProcessoAdmissao).filter(
        ProcessoAdmissao.candidatura_id == candidatura_id
    ).first()
    if existing:
        db.close()
        return jsonify({"message": "Processo já iniciado para esta candidatura.", "id": existing.id}), 409

    processo = ProcessoAdmissao(
        candidatura_id = candidatura_id,
        tipo_admissao  = tipo_admissao,
        status         = "EM_ANDAMENTO",
        etapa_atual    = ADMISSION_STEPS[0]["key"],
    )
    db.add(processo)
    db.flush()

    # Cria todas as etapas predefinidas
    for i, step in enumerate(ADMISSION_STEPS):
        db.add(EtapaProcesso(
            processo_id  = processo.id,
            ordem        = i,
            codigo       = step["key"],
            nome         = step["label"],
            departamento = step["dept"],
            tipo         = step["type"].upper(),
            status       = "PENDENTE",
        ))

    db.commit()
    audit_log(payload["sub"], "INICIAR_PROCESSO", "processo", processo.id,
              f"Candidatura #{candidatura_id}")
    db.close()
    return jsonify({"id": processo.id, "message": "Processo de admissão iniciado."}), 201


@bp.route("/<int:pid>", methods=["GET"])
def get_processo(pid):
    """Retorna o processo de admissão com todas as etapas."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH", "ROLE_GESTOR"])
    if err:
        return err

    db       = SessionLocal()
    processo = db.query(ProcessoAdmissao).filter(ProcessoAdmissao.id == pid).first()
    if not processo:
        db.close()
        return jsonify({"message": "Processo não encontrado."}), 404

    etapas = [{
        "id":          e.id,
        "ordem":       e.ordem,
        "codigo":      e.codigo,
        "nome":        e.nome,
        "departamento":e.departamento,
        "tipo":        e.tipo,
        "status":      e.status,
        "responsavel": e.responsavel,
        "concluido_em":e.concluido_em.isoformat() if e.concluido_em else None,
        "nota_externa":e.nota_externa,
    } for e in processo.etapas]

    db.close()
    return jsonify({
        "id":            processo.id,
        "candidatura_id":processo.candidatura_id,
        "status":        processo.status,
        "tipo_admissao": processo.tipo_admissao,
        "etapa_atual":   processo.etapa_atual,
        "sharepoint_url":processo.sharepoint_url,
        "etapas":        etapas,
    })


@bp.route("/etapa/<int:eid>", methods=["PATCH"])
def atualizar_etapa(eid):
    """Atualiza o status de uma etapa do processo."""
    payload, err = _require_auth(["ROLE_ADMIN", "ROLE_RH", "ROLE_GESTOR"])
    if err:
        return err

    data   = request.get_json() or {}
    status = data.get("status")

    db    = SessionLocal()
    etapa = db.query(EtapaProcesso).filter(EtapaProcesso.id == eid).first()
    if not etapa:
        db.close()
        return jsonify({"message": "Etapa não encontrada."}), 404

    etapa.status      = status
    etapa.responsavel = payload["sub"]
    if status in ("APROVADO", "REPROVADO"):
        etapa.concluido_em = datetime.now(timezone.utc)

    if data.get("nota"):
        etapa.nota = data["nota"]
    if data.get("nota_externa"):
        etapa.nota_externa = data["nota_externa"]

    db.commit()
    audit_log(payload["sub"], "ATUALIZAR_ETAPA", "etapa", eid, f"Status: {status}")
    db.close()
    return jsonify({"message": "Etapa atualizada."})
