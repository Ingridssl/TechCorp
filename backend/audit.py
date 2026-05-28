from database import SessionLocal
from models import AuditLog


def log(username: str, action: str, entity: str = None,
        entity_id: int = None, detail: str = None, ip: str = None):
    """Registra uma ação no audit log."""
    db = SessionLocal()
    try:
        db.add(AuditLog(
            username=username,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
            ip=ip,
        ))
        db.commit()
    except Exception as e:
        print(f"[AUDIT] Erro ao registrar: {e}")
        db.rollback()
    finally:
        db.close()
