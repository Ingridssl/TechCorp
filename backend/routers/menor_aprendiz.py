from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import MenorAprendiz
from security import decode_token
from audit import log as audit_log

bp = Blueprint("menor_aprendiz", __name__, url_prefix="/api/menor-aprendiz")


@bp.route("", methods=["POST"])
def inscrever():
    """Inscrição pública de menor aprendiz."""
    data = request.get_json() or {}
    required = ["full_name", "cpf", "phone", "email"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"message": f"Campos obrigatórios: {', '.join(missing)}"}), 400

    db = SessionLocal()
    m  = MenorAprendiz(
        full_name        = data["full_name"],
        cpf              = data["cpf"],
        phone            = data["phone"],
        email            = data["email"],
        data_nascimento  = data.get("data_nascimento"),
        nome_responsavel = data.get("nome_responsavel"),
        cidade_atual     = data.get("cidade_atual"),
        escola_atual     = data.get("escola_atual"),
        periodo_escolar  = data.get("periodo_escolar"),
        turno_escolar    = data.get("turno_escolar"),
        area_interesse   = data.get("area_interesse"),
        motivation       = data.get("motivation"),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    db.close()
    return jsonify({"id": m.id, "message": "Inscrição realizada com sucesso!"}), 201


@bp.route("", methods=["GET"])
def listar():
    """Lista inscrições (requer autenticação)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"message": "Não autorizado."}), 401
    try:
        decode_token(auth.split(" ", 1)[1])
    except Exception:
        return jsonify({"message": "Token inválido."}), 401

    db    = SessionLocal()
    items = db.query(MenorAprendiz).order_by(MenorAprendiz.created_at.desc()).all()
    db.close()
    return jsonify([{
        "id":          m.id,
        "full_name":   m.full_name,
        "email":       m.email,
        "cidade_atual":m.cidade_atual,
        "status":      m.status,
        "created_at":  m.created_at.isoformat() if m.created_at else None,
    } for m in items])
