import os
import pickle
import webbrowser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import datetime

try:
    import google.oauth2.credentials
    _google_apis_ok = True
except ImportError:
    _google_apis_ok = False

# Globales persistentes para el documento actual
ultimo_id_doc    = None
ultimo_titulo_doc = None


# SCOPES para Google API (debe coincidir con lo que estaba en main2.py)
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def obtener_credenciales_google():
    if not _google_apis_ok:
        print("[GOOGLE] google-auth-oauthlib no instalado — funciones Google desactivadas.")
        return None
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("[GOOGLE] No hay credentials.json - funciones Google desactivadas.")
                return None
            flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
    return creds

def obtener_servicio_docs():
    creds = obtener_credenciales_google()
    return build("docs", "v1", credentials=creds) if creds else None

def obtener_servicio_drive():
    creds = obtener_credenciales_google()
    return build("drive", "v3", credentials=creds) if creds else None

def obtener_servicio_gmail():
    creds = obtener_credenciales_google()
    return build("gmail", "v1", credentials=creds) if creds else None

def obtener_servicio_sheets():
    creds = obtener_credenciales_google()
    return build("sheets", "v4", credentials=creds) if creds else None

def obtener_servicio_calendar():
    creds = obtener_credenciales_google()
    return build("calendar", "v3", credentials=creds) if creds else None

def crear_documento_google(titulo="Nuevo Documento", contenido=""):
    global ultimo_id_doc, ultimo_titulo_doc
    try:
        service = obtener_servicio_docs()
        if not service:
            return "Google Docs no disponible."
        doc    = service.documents().create(body={"title": titulo}).execute()
        doc_id = doc["documentId"]
        ultimo_id_doc    = doc_id
        ultimo_titulo_doc = titulo
        if contenido:
            cuerpo_peticion = [{"insertText": {"location": {"index": 1}, "text": contenido}}]
            service.documents().batchUpdate(documentId=doc_id, body={"requests": cuerpo_peticion}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{doc_id}/edit")
        return f"Documento {titulo} creado y abierto, Christopher."
    except Exception as e:
        return f"Error en Google Docs: {e}"

def modificar_documento_google(contenido, doc_id=None):
    global ultimo_id_doc
    try:
        service   = obtener_servicio_docs()
        if not service:
            return "Google Docs no disponible."
        id_objetivo = doc_id or ultimo_id_doc
        if not id_objetivo:
            return "No hay ningún documento abierto en memoria."
        doc       = service.documents().get(documentId=id_objetivo).execute()
        indice_final = doc["body"]["content"][-1]["endIndex"] - 1
        cuerpo_peticion = [{"insertText": {"location": {"index": indice_final}, "text": "\n" + contenido}}]
        service.documents().batchUpdate(documentId=id_objetivo, body={"requests": cuerpo_peticion}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{id_objetivo}/edit")
        return f"Texto añadido en el documento {ultimo_titulo_doc}."
    except Exception as e:
        return f"Error al modificar documento: {e}"

def leer_correos(max_resultados=3):
    try:
        service  = obtener_servicio_gmail()
        if not service:
            return "Gmail no disponible."
        results  = service.users().messages().list(userId="me", maxResults=max_resultados, labelIds=["INBOX"]).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No se encontraron correos."
        respuesta = ""
        for msg in messages:
            m       = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            respuesta += f"De: {headers.get('From','?')} | Asunto: {headers.get('Subject','?')}\n"
        return respuesta.strip()
    except Exception as e:
        return f"Error en Gmail: {e}"

def listar_eventos_calendario():
    try:
        service = obtener_servicio_calendar()
        if not service:
            return "Google Calendar no disponible."
        from datetime import datetime, timezone
        ahora    = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=ahora, maxResults=5, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        if not items:
            return "No hay eventos próximos."
        respuesta = ""
        for e in items:
            inicio    = e["start"].get("dateTime", e["start"].get("date"))
            respuesta += f"{inicio} : {e['summary']}\n"
        return respuesta.strip()
    except Exception as e:
        return f"Error en Calendar: {e}"

def crear_hoja_calculo_google(titulo="Nueva Hoja"):
    try:
        service  = obtener_servicio_sheets()
        if not service:
            return "Google Sheets no disponible."
        hoja    = service.spreadsheets().create(body={"properties": {"title": titulo}}).execute()
        hoja_id = hoja["spreadsheetId"]
        webbrowser.open(f"https://docs.google.com/spreadsheets/d/{hoja_id}/edit")
        return f"Hoja {titulo} creada y abierta."
    except Exception as e:
        return f"Error en Google Sheets: {e}"