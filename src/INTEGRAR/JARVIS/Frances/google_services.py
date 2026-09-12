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

# Globaux persistants pour le doc en cours
dernier_doc_id    = None
dernier_doc_titre = None


# SCOPES pour Google API (inclut modify pour envoyer, répondre et supprimer des emails)
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.readonly'
]

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")

def get_google_creds():
    if not _google_apis_ok:
        print("[GOOGLE] google-auth-oauthlib non installé — fonctions Google désactivées.")
        return None
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, "rb") as f:
                creds = pickle.load(f)
        except Exception:
            creds = None

    # Si le token ne possède pas les nouveaux scopes, on force la réautorisation
    if creds and hasattr(creds, 'has_scopes') and not creds.has_scopes(SCOPES):
        print("[GOOGLE] Nouvelles permissions Gmail requises (envoi/suppression), réautorisation...")
        creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as _e:
                print(f"[GOOGLE] Token expiré ou invalide ({_e}), nouvelle connexion requise...")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(CREDS_PATH):
                print(f"[GOOGLE] Pas de credentials.json trouvé à : {CREDS_PATH}")
                return None
            try:
                flow  = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
                print("[GOOGLE] 🌐 Ouverture du navigateur pour autoriser l'accès à Gmail/Google...")
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[GOOGLE] Erreur lors de l'authentification OAuth : {e}")
                return None

        if creds:
            try:
                with open(TOKEN_PATH, "wb") as f:
                    pickle.dump(creds, f)
            except Exception as e:
                print(f"[GOOGLE] Erreur sauvegarde token : {e}")

    return creds

def get_docs_service():
    creds = get_google_creds()
    return build("docs", "v1", credentials=creds) if creds else None

def get_drive_service():
    creds = get_google_creds()
    return build("drive", "v3", credentials=creds) if creds else None

def get_gmail_service():
    creds = get_google_creds()
    return build("gmail", "v1", credentials=creds) if creds else None

def get_sheets_service():
    creds = get_google_creds()
    return build("sheets", "v4", credentials=creds) if creds else None

def get_calendar_service():
    creds = get_google_creds()
    return build("calendar", "v3", credentials=creds) if creds else None

def creer_google_doc(titre="Nouveau Document", contenu=""):
    global dernier_doc_id, dernier_doc_titre
    try:
        service = get_docs_service()
        if not service:
            return "Google Docs non disponible."
        doc    = service.documents().create(body={"title": titre}).execute()
        doc_id = doc["documentId"]
        dernier_doc_id    = doc_id
        dernier_doc_titre = titre
        if contenu:
            requests_body = [{"insertText": {"location": {"index": 1}, "text": contenu}}]
            service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{doc_id}/edit")
        return f"Document {titre} cree et ouvert, Mickael."
    except Exception as e:
        return f"Erreur Google Docs : {e}"

def modifier_google_doc(contenu, doc_id=None):
    global dernier_doc_id
    try:
        service   = get_docs_service()
        if not service:
            return "Google Docs non disponible."
        target_id = doc_id or dernier_doc_id
        if not target_id:
            return "Aucun document ouvert en memoire."
        doc       = service.documents().get(documentId=target_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        requests_body = [{"insertText": {"location": {"index": end_index}, "text": "\n" + contenu}}]
        service.documents().batchUpdate(documentId=target_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{target_id}/edit")
        return f"Texte ajoute dans le document {dernier_doc_titre}."
    except Exception as e:
        return f"Erreur modification doc : {e}"

def recuperer_emails_structures(max_results=4, non_lus_seulement=False):
    """Récupère les emails récents au format structuré pour l'affichage HUD et la synthèse vocale."""
    try:
        service = get_gmail_service()
        if not service:
            return {
                "success": False,
                "emails": [],
                "vocal": "Je n'ai pas pu accéder à votre boîte Gmail. Veuillez vérifier l'autorisation Google."
            }

        query_labels = ["INBOX"]
        if non_lus_seulement:
            query_labels.append("UNREAD")

        results = service.users().messages().list(userId="me", maxResults=max_results, labelIds=query_labels).execute()
        messages = results.get("messages", [])

        if not messages:
            return {
                "success": True,
                "emails": [],
                "vocal": "Vous n'avez aucun nouveau message dans votre boîte de réception principale."
            }

        import re
        emails_list = []
        for msg in messages:
            try:
                m = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}

                expediteur_brut = headers.get("from", "Inconnu")
                nom_match = re.match(r'^(.*?)\s*<.*?>$', expediteur_brut)
                if nom_match and nom_match.group(1).strip():
                    nom_expediteur = nom_match.group(1).strip().replace('"', '')
                else:
                    nom_expediteur = expediteur_brut.split("@")[0].capitalize()

                sujet = headers.get("subject", "Sans objet")
                date_brute = headers.get("date", "")
                snippet = m.get("snippet", "")
                is_unread = "UNREAD" in m.get("labelIds", [])

                emails_list.append({
                    "id": msg["id"],
                    "sender": nom_expediteur,
                    "sender_full": expediteur_brut,
                    "subject": sujet,
                    "snippet": snippet,
                    "date": date_brute,
                    "unread": is_unread
                })
            except Exception as _e:
                print(f"[GMAIL] Erreur lecture message {msg.get('id')}: {_e}")
                continue

        global DERNIERS_EMAILS_MEMOIRE
        DERNIERS_EMAILS_MEMOIRE = emails_list

        # Synthèse vocale naturelle et invitation interactive
        nb = len(emails_list)
        if nb == 0:
            vocal = "Vous n'avez aucun nouvel email dans votre boîte de réception."
        elif nb == 1:
            em = emails_list[0]
            vocal = f"Vous avez un email de {em['sender']}, avec pour objet : {em['subject']}. Souhaitez-vous que je vous lise le contenu ?"
        else:
            noms = ", ".join([f"le premier de {emails_list[0]['sender']}", f"le deuxième de {emails_list[1]['sender']}"])
            if nb > 2:
                noms += f", et {nb - 2} autres"
            vocal = f"Vous avez {nb} emails récents : {noms}. Lequel souhaitez-vous que je vous ouvre ?"

        return {
            "success": True,
            "emails": emails_list,
            "vocal": vocal
        }

    except Exception as e:
        print(f"[GMAIL] Erreur : {e}")
        return {
            "success": False,
            "emails": [],
            "vocal": f"Erreur lors de la lecture des emails : {e}"
        }

# Cache global des derniers emails récupérés pour sélection par index
DERNIERS_EMAILS_MEMOIRE = []

def recuperer_email_detail(email_id_ou_index):
    """Récupère le corps complet et les détails d'un email spécifique."""
    global DERNIERS_EMAILS_MEMOIRE
    try:
        service = get_gmail_service()
        if not service:
            return {"success": False, "error": "Gmail non disponible", "vocal": "Gmail non connecté."}

        email_id = None
        if isinstance(email_id_ou_index, int) and 0 <= email_id_ou_index < len(DERNIERS_EMAILS_MEMOIRE):
            email_id = DERNIERS_EMAILS_MEMOIRE[email_id_ou_index].get("id")
        elif isinstance(email_id_ou_index, str):
            if email_id_ou_index.isdigit() and int(email_id_ou_index) < len(DERNIERS_EMAILS_MEMOIRE):
                email_id = DERNIERS_EMAILS_MEMOIRE[int(email_id_ou_index)].get("id")
            else:
                email_id = email_id_ou_index

        if not email_id:
            return {"success": False, "error": "Email introuvable", "vocal": "Désolé, je n'ai pas trouvé cet email."}

        m = service.users().messages().get(userId="me", id=email_id, format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}

        import re, base64
        expediteur_brut = headers.get("from", "Inconnu")
        nom_match = re.match(r'^(.*?)\s*<.*?>$', expediteur_brut)
        nom_expediteur = nom_match.group(1).strip().replace('"', '') if nom_match and nom_match.group(1).strip() else expediteur_brut.split("@")[0].capitalize()

        sujet = headers.get("subject", "Sans objet")
        date_brute = headers.get("date", "")
        snippet = m.get("snippet", "")

        # Extraction du corps de texte
        payload = m.get("payload", {})
        def _extraire_texte(part):
            if not part: return ""
            mime = part.get("mimeType", "")
            if mime == "text/plain" and "data" in part.get("body", {}):
                try:
                    data = part["body"]["data"]
                    return base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8", errors="ignore")
                except Exception:
                    pass
            for sub in part.get("parts", []):
                t = _extraire_texte(sub)
                if t: return t
            return ""

        body_text = _extraire_texte(payload)
        if not body_text:
            body_text = snippet

        # Nettoyage pour la synthèse vocale (sans liens http bruts)
        clean_text_for_speech = re.sub(r'https?://\S+', '', body_text)
        clean_text_for_speech = re.sub(r'\s+', ' ', clean_text_for_speech).strip()
        vocal_summary = clean_text_for_speech[:350]
        if len(clean_text_for_speech) > 350:
            vocal_summary += "..."

        vocal = f"Voici le message de {nom_expediteur}. Objet : {sujet}. Contenu : {vocal_summary}"

        return {
            "success": True,
            "id": email_id,
            "sender": nom_expediteur,
            "sender_full": expediteur_brut,
            "subject": sujet,
            "date": date_brute,
            "body": body_text[:2500],
            "snippet": snippet,
            "vocal": vocal
        }
    except Exception as e:
        print(f"[GMAIL DETAIL] Erreur : {e}")
        return {"success": False, "error": str(e), "vocal": f"Impossible d'ouvrir ce message : {e}"}

def lire_emails(max_results=4):
    """Fonction wrapper pour compatibilité."""
    res = recuperer_emails_structures(max_results=max_results)
    return res.get("vocal", "Aucun email.")

def lister_evenements_calendar():
    try:
        service = get_calendar_service()
        if not service:
            return "Google Calendar non disponible."
        from datetime import datetime, timezone
        now    = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=5, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        if not items:
            return "Aucun evenement a venir."
        reponse = ""
        for e in items:
            start    = e["start"].get("dateTime", e["start"].get("date"))
            reponse += f"{start} : {e['summary']}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur Calendar : {e}"

def creer_google_sheet(titre="Nouvelle Feuille"):
    try:
        service  = get_sheets_service()
        if not service:
            return "Google Sheets non disponible."
        sheet    = service.spreadsheets().create(body={"properties": {"title": titre}}).execute()
        sheet_id = sheet["spreadsheetId"]
        webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        return f"Feuille {titre} creee et ouverte."
    except Exception as e:
        return f"Erreur Google Sheets : {e}"

def supprimer_email(email_id_ou_index):
    """Déplace un email vers la corbeille Gmail."""
    global DERNIERS_EMAILS_MEMOIRE
    try:
        service = get_gmail_service()
        if not service:
            return {"success": False, "error": "Gmail non disponible", "vocal": "Gmail n'est pas connecté."}

        email_id = None
        if isinstance(email_id_ou_index, int) and 0 <= email_id_ou_index < len(DERNIERS_EMAILS_MEMOIRE):
            email_id = DERNIERS_EMAILS_MEMOIRE[email_id_ou_index].get("id")
        elif isinstance(email_id_ou_index, str):
            if email_id_ou_index.isdigit() and int(email_id_ou_index) < len(DERNIERS_EMAILS_MEMOIRE):
                email_id = DERNIERS_EMAILS_MEMOIRE[int(email_id_ou_index)].get("id")
            else:
                email_id = email_id_ou_index

        if not email_id:
            return {"success": False, "error": "Email introuvable", "vocal": "Désolé, je n'ai pas trouvé cet email à supprimer."}

        service.users().messages().trash(userId="me", id=email_id).execute()
        DERNIERS_EMAILS_MEMOIRE = [e for e in DERNIERS_EMAILS_MEMOIRE if e.get("id") != email_id]

        return {
            "success": True,
            "id": email_id,
            "vocal": "L'email a été déplacé vers la corbeille avec succès."
        }
    except Exception as e:
        print(f"[GMAIL TRASH] Erreur : {e}")
        return {"success": False, "error": str(e), "vocal": f"Impossible de supprimer l'email : {e}"}

def envoyer_email(destinataire, sujet, corps_texte, thread_id=None, in_reply_to=None):
    """Crée et envoie un email via Gmail API."""
    import base64
    from email.mime.text import MIMEText
    try:
        service = get_gmail_service()
        if not service:
            return {"success": False, "error": "Gmail non disponible", "vocal": "Gmail n'est pas connecté."}

        message = MIMEText(corps_texte, "plain", "utf-8")
        message["to"] = destinataire
        message["subject"] = sujet
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body_send = {"raw": raw_message}
        if thread_id:
            body_send["threadId"] = thread_id

        sent_msg = service.users().messages().send(userId="me", body=body_send).execute()
        return {
            "success": True,
            "id": sent_msg.get("id"),
            "vocal": f"Votre email a bien été envoyé à {destinataire}."
        }
    except Exception as e:
        print(f"[GMAIL SEND] Erreur : {e}")
        return {"success": False, "error": str(e), "vocal": f"Erreur lors de l'envoi de l'email : {e}"}

def repondre_email(email_id_ou_index, corps_reponse):
    """Répond à un email existant."""
    global DERNIERS_EMAILS_MEMOIRE
    try:
        service = get_gmail_service()
        if not service:
            return {"success": False, "error": "Gmail non disponible", "vocal": "Gmail n'est pas connecté."}

        email_id = None
        if isinstance(email_id_ou_index, int) and 0 <= email_id_ou_index < len(DERNIERS_EMAILS_MEMOIRE):
            email_id = DERNIERS_EMAILS_MEMOIRE[email_id_ou_index].get("id")
        elif isinstance(email_id_ou_index, str):
            if email_id_ou_index.isdigit() and int(email_id_ou_index) < len(DERNIERS_EMAILS_MEMOIRE):
                email_id = DERNIERS_EMAILS_MEMOIRE[int(email_id_ou_index)].get("id")
            else:
                email_id = email_id_ou_index

        if not email_id:
            return {"success": False, "error": "Email introuvable", "vocal": "Impossible de trouver l'email auquel répondre."}

        m = service.users().messages().get(userId="me", id=email_id, format="metadata", metadataHeaders=["From", "Subject", "Message-ID"]).execute()
        headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}

        destinataire = headers.get("from", "")
        sujet_orig = headers.get("subject", "Sans objet")
        msg_id_header = headers.get("message-id", "")
        thread_id = m.get("threadId")

        sujet_reponse = sujet_orig if sujet_orig.lower().startswith("re:") else f"Re: {sujet_orig}"

        return envoyer_email(
            destinataire=destinataire,
            sujet=sujet_reponse,
            corps_texte=corps_reponse,
            thread_id=thread_id,
            in_reply_to=msg_id_header
        )
    except Exception as e:
        print(f"[GMAIL REPLY] Erreur : {e}")
        return {"success": False, "error": str(e), "vocal": f"Erreur lors de la réponse : {e}"}

# ── SURVEILLANCE AUTOMATIQUE EN ARRIÈRE-PLAN ─────────────────────────────────
DERNIERS_EMAILS_CONNUS_IDS = set()
PREMIER_CHECK_EFFECTUE = False

def gmail_est_configure():
    """Vérifie si credentials.json et token.pickle existent."""
    return os.path.exists(CREDS_PATH) and os.path.exists(TOKEN_PATH)

def verifier_nouveaux_emails():
    """
    Vérifie les nouveaux emails en arrière-plan.
    Retourne la liste des nouveaux emails arrivés depuis la dernière vérification.
    """
    global DERNIERS_EMAILS_CONNUS_IDS, PREMIER_CHECK_EFFECTUE, DERNIERS_EMAILS_MEMOIRE
    if not gmail_est_configure():
        return {"configured": False, "new_emails": [], "unread_count": 0}

    try:
        data = recuperer_emails_structures(max_results=5)
        if not data.get("success"):
            return {"configured": True, "new_emails": [], "unread_count": 0}

        emails = data.get("emails", [])
        unread_count = sum(1 for e in emails if e.get("unread"))
        current_ids = {e["id"] for e in emails}

        # Premier appel lors du démarrage : on synchronise sans alerte
        if not PREMIER_CHECK_EFFECTUE:
            DERNIERS_EMAILS_CONNUS_IDS = current_ids
            PREMIER_CHECK_EFFECTUE = True
            return {
                "configured": True,
                "first_run": True,
                "new_emails": [],
                "unread_count": unread_count,
                "emails": emails
            }

        # Détecter les nouveaux emails arrivés
        nouveaux = [e for e in emails if e["id"] not in DERNIERS_EMAILS_CONNUS_IDS]
        DERNIERS_EMAILS_CONNUS_IDS = current_ids

        return {
            "configured": True,
            "first_run": False,
            "new_emails": nouveaux,
            "unread_count": unread_count,
            "emails": emails
        }
    except Exception as e:
        print(f"[GMAIL MONITOR] Erreur : {e}")
        return {"configured": True, "new_emails": [], "unread_count": 0}


