"""
Scheduler de alertas automáticos.
Verifica candidaturas sem movimentação e notifica os responsáveis.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from models import Candidatura, AuditLog
from datetime import datetime, timedelta, timezone
import os

DIAS_SEM_MOVIMENTACAO = int(os.getenv("ALERTA_DIAS", "7"))


def verificar_candidatos_parados():
    """Identifica candidaturas sem atualização há X dias."""
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=DIAS_SEM_MOVIMENTACAO)
        paradas = db.query(Candidatura).filter(
            Candidatura.status.notin_(["APPROVED", "REJECTED"]),
            Candidatura.applied_at < limite,
        ).all()

        for c in paradas:
            print(f"[ALERTA] Candidatura parada: {c.full_name} ({c.status}) — {c.applied_at}")
            # Aqui você pode adicionar envio de e-mail para o RH
    finally:
        db.close()


def iniciar_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Manaus")
    scheduler.add_job(verificar_candidatos_parados, "cron", hour=8, minute=0)
    scheduler.start()
    print("[SCHEDULER] Iniciado — alertas diários às 08:00")
