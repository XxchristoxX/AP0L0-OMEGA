import sys
import subprocess
import os
import imaplib
import email
from email.header import decode_header
from pathlib import Path
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
def run(params):
    try:
        install_and_import("plyer")
        from plyer import notification
        imap_server = params.get("imap_server", "imap.gmail.com")
        email_user = params.get("email_user", "")
        email_pass = params.get("email_pass", "")
        if not email_user or not email_pass:
            return "Faltan credenciales de correo (email_user y email_pass) en los parámetros."
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        mail.select("inbox")
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            return "No se pudieron buscar nuevos mensajes."
        task_count = 0
        tasks_found = []
        for num in messages[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                    if "tarea" in subject.lower() or "pendiente" in subject.lower() or "todo" in subject.lower():
                        tasks_found.append(subject)
                        task_count += 1
        mail.logout()
        if task_count > 0:
            task_list_str = "\n".join([f"- {t}" for t in tasks_found[:5]])
            notification.notify(
                title=f"Gestión Contextual: {task_count} nuevas tareas",
                message=f"Extraídas de correos:\n{task_list_str}",
                app_name="Asistente Autónomo",
                timeout=10
            )
            return f"Se procesaron {task_count} tareas automáticamente desde los correos no leídos y se notificó en el escritorio."
        else:
            return "No se encontraron nuevas tareas pendientes en los correos recientes."
    except Exception as e:
        return f"Error en la ejecución de la habilidad tengas_ingresarlas_manualmente: {str(e)}"