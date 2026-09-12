# src/actions/google_services.py
"""
Servicios de Google para AP0L0
Docs, Sheets, Gmail, Calendar
"""

import os
import pickle
import webbrowser
import datetime

# Google es una integración opcional. No debe impedir que AP0L0 arranque si el
# usuario todavía no instaló OAuth o no configuró credentials.json.
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    _GOOGLE_AVAILABLE = True
    _GOOGLE_IMPORT_ERROR = ""
except ImportError as exc:
    Credentials = None
    InstalledAppFlow = None
    Request = None
    build = None
    _GOOGLE_AVAILABLE = False
    _GOOGLE_IMPORT_ERROR = str(exc)

_SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.readonly'
]

_dernier_doc_id = None
_dernier_doc_titre = None


def _get_credentials():
    if not _GOOGLE_AVAILABLE:
        return None
    creds = None
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "token.pickle")
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "credentials.json")
            if not os.path.exists(creds_file):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return creds


def _get_service(service_name, version):
    if not _GOOGLE_AVAILABLE:
        return None
    creds = _get_credentials()
    if not creds:
        return None
    return build(service_name, version, credentials=creds)


def creer_google_doc(titre="Nouveau Document", contenu=""):
    global _dernier_doc_id, _dernier_doc_titre
    service = _get_service("docs", "v1")
    if not service:
        return "Google Docs no disponible."
    try:
        doc = service.documents().create(body={"title": titre}).execute()
        doc_id = doc["documentId"]
        _dernier_doc_id = doc_id
        _dernier_doc_titre = titre
        if contenu:
            requests_body = [{"insertText": {"location": {"index": 1}, "text": contenu}}]
            service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{doc_id}/edit")
        return f"Documento '{titre}' creado y abierto."
    except Exception as e:
        return f"Error en Google Docs: {e}"


def modifier_google_doc(contenu, doc_id=None):
    global _dernier_doc_id
    service = _get_service("docs", "v1")
    if not service:
        return "Google Docs no disponible."
    target_id = doc_id or _dernier_doc_id
    if not target_id:
        return "No hay documento abierto en memoria."
    try:
        doc = service.documents().get(documentId=target_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        requests_body = [{"insertText": {"location": {"index": end_index}, "text": "\n" + contenu}}]
        service.documents().batchUpdate(documentId=target_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{target_id}/edit")
        return f"Texto añadido al documento {_dernier_doc_titre}."
    except Exception as e:
        return f"Error modificando doc: {e}"


def lire_emails(max_results=5):
    service = _get_service("gmail", "v1")
    if not service:
        return "Gmail no disponible."
    try:
        results = service.users().messages().list(userId="me", maxResults=max_results, labelIds=["INBOX"]).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No hay emails recientes."
        reponse = ""
        for msg in messages[:max_results]:
            m = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            reponse += f"De: {headers.get('From','?')} | Asunto: {headers.get('Subject','?')}\n"
        return reponse.strip()
    except Exception as e:
        return f"Error en Gmail: {e}"


def lister_evenements_calendar(max_results=5):
    service = _get_service("calendar", "v3")
    if not service:
        return "Google Calendar no disponible."
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=max_results, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        if not items:
            return "No hay próximos eventos."
        reponse = ""
        for e in items:
            start = e["start"].get("dateTime", e["start"].get("date"))
            reponse += f"{start}: {e['summary']}\n"
        return reponse.strip()
    except Exception as e:
        return f"Error en Calendar: {e}"


def creer_google_sheet(titre="Nueva Hoja"):
    service = _get_service("sheets", "v4")
    if not service:
        return "Google Sheets no disponible."
    try:
        sheet = service.spreadsheets().create(body={"properties": {"title": titre}}).execute()
        sheet_id = sheet["spreadsheetId"]
        webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        return f"Hoja '{titre}' creada."
    except Exception as e:
        return f"Error en Sheets: {e}"


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def google_services(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "").lower()
    if action == "create_doc":
        title = params.get("title", "Nuevo Documento")
        content = params.get("content", "")
        result = creer_google_doc(title, content)
    elif action == "edit_doc":
        content = params.get("content", "")
        result = modifier_google_doc(content)
    elif action == "create_sheet":
        title = params.get("title", "Nueva Hoja")
        result = creer_google_sheet(title)
    elif action == "read_emails":
        max_res = params.get("max_results", 5)
        result = lire_emails(max_res)
    elif action == "read_calendar":
        max_res = params.get("max_results", 5)
        result = lister_evenements_calendar(max_res)
    else:
        result = f"Acción '{action}' no soportada."
    if speak:
        speak(result)
    if player:
        player.write_log(f"[Google] {result}")
    return result
