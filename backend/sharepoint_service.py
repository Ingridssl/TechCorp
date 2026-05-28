"""
Integração com SharePoint via Microsoft Graph API.
Cria pastas automaticamente e faz upload de documentos.

Configuração via variáveis de ambiente:
    MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET
    SHAREPOINT_SITE  (ex: suaempresa.sharepoint.com)
    SHAREPOINT_DRIVE (ex: Documentos Compartilhados)
    SHAREPOINT_BASE_PATH (ex: RH/CANDIDATURAS)
"""
import os
import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.getenv("MS_TENANT_ID")
CLIENT_ID     = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
SITE_HOST     = os.getenv("SHAREPOINT_SITE",       "suaempresa.sharepoint.com")
DRIVE_NAME    = os.getenv("SHAREPOINT_DRIVE",      "Documentos Compartilhados")
BASE_PATH     = os.getenv("SHAREPOINT_BASE_PATH",  "RH/CANDIDATURAS")

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
        raise Exception(f"Falha ao obter token: {result.get('error_description')}")
    return result["access_token"]


def _headers(json_content: bool = True) -> dict:
    h = {"Authorization": f"Bearer {_get_token()}"}
    if json_content:
        h["Content-Type"] = "application/json"
    return h


def _get_site_id() -> str:
    url = f"{GRAPH_BASE}/sites/{SITE_HOST}:/sites/Intranet"
    r   = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["id"]


def _get_drive_id(site_id: str) -> str:
    url    = f"{GRAPH_BASE}/sites/{site_id}/drives"
    r      = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    drives = r.json().get("value", [])
    for d in drives:
        if d.get("name") == DRIVE_NAME:
            return d["id"]
    raise Exception(f"Drive '{DRIVE_NAME}' não encontrado no site.")


def _ensure_folder(drive_id: str, path: str) -> str:
    """Cria a pasta no SharePoint se não existir. Retorna o ID da pasta."""
    url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{path}"
    r   = requests.get(url, headers=_headers(), timeout=15)
    if r.status_code == 200:
        return r.json()["id"]

    # Cria pasta recursivamente
    parts  = path.rsplit("/", 1)
    parent = parts[0] if len(parts) > 1 else ""
    name   = parts[-1]

    if parent:
        parent_id = _ensure_folder(drive_id, parent)
        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{parent_id}/children"
    else:
        url = f"{GRAPH_BASE}/drives/{drive_id}/root/children"

    payload = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
    r = requests.post(url, headers=_headers(), json=payload, timeout=15)
    if r.status_code in (200, 201):
        return r.json()["id"]
    if r.status_code == 409:  # já existe
        r2 = requests.get(f"{GRAPH_BASE}/drives/{drive_id}/root:/{path}", headers=_headers(), timeout=15)
        r2.raise_for_status()
        return r2.json()["id"]
    r.raise_for_status()


def criar_pasta_candidato(nome: str, cargo: str) -> str:
    """
    Cria a pasta do candidato no SharePoint.
    Padrão: BASE_PATH / CARGO / NOME
    Retorna a URL da pasta criada.
    """
    site_id  = _get_site_id()
    drive_id = _get_drive_id(site_id)
    path     = f"{BASE_PATH}/{cargo.upper()}/{nome.upper()}"
    folder_id = _ensure_folder(drive_id, path)

    # Retorna a URL de compartilhamento
    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_id}"
    r   = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("webUrl", "")


def upload_arquivo(local_path: str, nome_destino: str, pasta_sharepoint_url: str) -> str:
    """
    Faz upload de um arquivo local para o SharePoint.
    Retorna a URL do arquivo no SharePoint.
    """
    site_id  = _get_site_id()
    drive_id = _get_drive_id(site_id)

    # Deriva o path relativo a partir da URL da pasta
    path_pasta = pasta_sharepoint_url.split("/Documentos%20Compartilhados/")[-1]
    path_pasta = path_pasta.replace("%20", " ")
    path_arquivo = f"{path_pasta}/{nome_destino}"

    upload_url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{path_arquivo}:/content"

    with open(local_path, "rb") as f:
        r = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/octet-stream"},
            data=f,
            timeout=60,
        )
    r.raise_for_status()
    return r.json().get("webUrl", "")
