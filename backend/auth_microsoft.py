"""
SSO via Microsoft Azure AD (MSAL).
Permite que usuários internos façam login com conta corporativa (@suaempresa.com).

Configuração necessária no Azure AD:
1. Registrar aplicação
2. Adicionar redirect URI: https://seudominio.com/api/auth/microsoft/callback
3. Conceder permissão: User.Read (Microsoft Graph)
"""
from flask import Blueprint, request, jsonify, redirect
from msal import ConfidentialClientApplication
from database import SessionLocal
from models import User
from security import create_token
from audit import log as audit_log
import os

bp_ms = Blueprint("auth_microsoft", __name__)

TENANT_ID     = os.getenv("MS_TENANT_ID")
CLIENT_ID     = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("MS_REDIRECT_URI", "http://localhost:8080/api/auth/microsoft/callback")
ALLOWED_DOMAIN = os.getenv("MS_ALLOWED_DOMAIN", "suaempresa.com")

SCOPES = ["User.Read"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"


def _get_msal_app():
    return ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )


@bp_ms.route("/login")
def ms_login():
    """Redireciona para a tela de login Microsoft."""
    msal_app = _get_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return redirect(auth_url)


@bp_ms.route("/callback")
def ms_callback():
    """Recebe o código de autorização e troca por token."""
    code = request.args.get("code")
    if not code:
        return jsonify({"message": "Código de autorização ausente."}), 400

    msal_app = _get_msal_app()
    result   = msal_app.acquire_token_by_authorization_code(
        code, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )

    if "error" in result:
        return jsonify({"message": result.get("error_description", "Falha no login.")}), 401

    ms_email    = result.get("id_token_claims", {}).get("preferred_username", "")
    ms_name     = result.get("id_token_claims", {}).get("name", "")

    # Verifica domínio permitido
    if not ms_email.endswith(f"@{ALLOWED_DOMAIN}"):
        return jsonify({"message": f"Apenas contas @{ALLOWED_DOMAIN} são permitidas."}), 403

    # Busca ou cria o usuário
    db   = SessionLocal()
    user = db.query(User).filter(User.email == ms_email).first()
    if not user:
        username = ms_email.split("@")[0]
        user = User(
            username  = username,
            email     = ms_email,
            role      = "ROLE_RH",
            is_active = True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_token({"sub": user.username, "role": user.role})
    audit_log(user.username, "LOGIN_MS", ip=request.remote_addr)
    db.close()

    # Redireciona para o frontend com o token
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
    return redirect(f"{frontend_url}/?token={token}")
