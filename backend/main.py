from flask import Flask, jsonify, send_from_directory, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
from database import engine, SessionLocal, Base
from security import hash_password
from extensions import limiter
import models
import os
import threading

load_dotenv()


# ── Scheduler de alertas (lazy, não bloqueia startup) ─────────
def _start_scheduler():
    try:
        from alertas import iniciar_scheduler
        iniciar_scheduler()
    except Exception as e:
        print(f"[ALERTA] Falha ao iniciar scheduler: {e}")

threading.Thread(target=_start_scheduler, daemon=True).start()


# ── Inicialização lazy do DB ──────────────────────────────────
_db_initialized = False

def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            Base.metadata.create_all(bind=engine)
            create_default_user()
            _db_initialized = True
        except Exception as e:
            print(f"[DB] Erro na inicialização: {e}")


FRONTEND_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_FOLDER, static_url_path="")
CORS(app)

# Compressão automática das respostas
from flask_compress import Compress
Compress(app)
app.config["COMPRESS_MIMETYPES"] = [
    "application/json", "text/html", "text/css",
    "application/javascript", "text/javascript",
]
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500


@app.after_request
def no_cache_js_html(response):
    """Força o browser a sempre buscar JS e HTML atualizados."""
    if response.content_type and any(t in response.content_type for t in
            ['javascript', 'text/html']):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.before_request
def init_db_once():
    ensure_db_initialized()


# ── Rotas de páginas ──────────────────────────────────────────

@app.route("/health")
def health():
    return "ok", 200

@app.route("/")
def index():
    return send_from_directory(FRONTEND_FOLDER, "index.html")

@app.route("/definir-senha")
def ativar():
    return send_from_directory(FRONTEND_FOLDER, "ativar.html")

@app.route("/redefinir-senha")
def redefinir_senha():
    return send_from_directory(FRONTEND_FOLDER, "redefinir-senha.html")

@app.route("/admissao")
def admissao():
    return send_from_directory(FRONTEND_FOLDER, "admissao.html")

@app.route("/admissoes")
def admissoes():
    return send_from_directory(FRONTEND_FOLDER, "admissoes.html")

@app.route("/acompanhar")
def acompanhar():
    return send_from_directory(FRONTEND_FOLDER, "acompanhar.html")

@app.route("/candidato/definir-senha")
def candidato_definir_senha():
    return send_from_directory(FRONTEND_FOLDER, "definir-senha-candidato.html")

@app.route("/menor-aprendiz")
def menor_aprendiz_page():
    return send_from_directory(FRONTEND_FOLDER, "menor-aprendiz.html")

@app.route("/revisar-solicitacao")
def revisar_solicitacao():
    return send_from_directory(FRONTEND_FOLDER, "revisar-solicitacao.html")


# ── Rate limiting ─────────────────────────────────────────────
limiter.init_app(app)

@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify({
        "message": "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
    }), 429


# ── Blueprints ────────────────────────────────────────────────
from routers import auth, jobs, candidaturas, processos, solicitacoes, menor_aprendiz
from colaboradores_router import bp_colab
from auth_microsoft import bp_ms
from candidato_auth import bp_cand

app.register_blueprint(auth.bp)
app.register_blueprint(bp_ms,    url_prefix="/api/auth/microsoft")
app.register_blueprint(bp_cand,  url_prefix="/api/candidato")
app.register_blueprint(jobs.bp)
app.register_blueprint(candidaturas.bp)
app.register_blueprint(processos.bp)
app.register_blueprint(solicitacoes.bp)
app.register_blueprint(menor_aprendiz.bp)
app.register_blueprint(bp_colab)


# ── Usuário padrão ────────────────────────────────────────────
def create_default_user():
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add(models.User(
                username="admin",
                email="admin@example.com",
                password=hash_password("1234"),
                role="ROLE_ADMIN",
                is_active=True,
            ))
            db.commit()
            print("Usuário padrão criado → admin / 1234")
    finally:
        db.close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"Servidor rodando em http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
