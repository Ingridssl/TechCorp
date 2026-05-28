"""
Envio de e-mails via Microsoft Graph API (sem SMTP).
Requer aplicação registrada no Azure AD com permissão Mail.Send.
"""
import os
import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.getenv("MS_TENANT_ID")
CLIENT_ID     = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
SENDER_EMAIL  = os.getenv("SENDER_EMAIL", "noreply@suaempresa.com")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"

TOKEN_URL  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES     = ["https://graph.microsoft.com/.default"]


def _get_token() -> str:
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_silent(SCOPES, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" not in result:
        raise Exception(f"Token falhou: {result.get('error_description')}")
    return result["access_token"]


def send_email(to: str, subject: str, body_html: str) -> bool:
    """
    Envia um e-mail via Microsoft Graph.
    Retorna True se enviado com sucesso, False caso contrário.
    """
    if not EMAIL_ENABLED:
        print(f"[EMAIL] Desabilitado. Seria enviado para {to}: {subject}")
        return False

    url     = f"{GRAPH_BASE}/users/{SENDER_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": "false",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    return r.status_code == 202


def send_status_update(candidate_email: str, candidate_name: str, new_status: str):
    """Notifica o candidato sobre mudança de status na candidatura."""
    status_labels = {
        "TRIAGEM":          "em triagem",
        "ENTREVISTA":       "convocado para entrevista",
        "APROVACAO_FINAL":  "na aprovação final",
        "APPROVED":         "aprovado",
        "REJECTED":         "não selecionado neste processo",
    }
    label = status_labels.get(new_status, new_status)
    subject = "Atualização da sua candidatura"
    body = f"""
    <p>Olá, <strong>{candidate_name}</strong>!</p>
    <p>Sua candidatura foi atualizada para: <strong>{label}</strong>.</p>
    <p>Acompanhe sua candidatura pelo portal do candidato.</p>
    """
    return send_email(candidate_email, subject, body)
