# src/actions/gdrive_integration.py
"""
Integración con Google Drive usando OAuth 2.0.
Soporte: autenticación, subida, descarga, listado, búsqueda, eliminación,
creación de carpetas, compartición y subida de carpetas completas.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io


class GDriveIntegration:
    """
    Integración con Google Drive usando OAuth 2.0.
    """

    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def __init__(self):
        self.config_dir = Path(__file__).resolve().parent.parent / "config"
        self.creds_path = self.config_dir / "credentials.json"
        self.token_path = self.config_dir / "token.pickle"
        self.service = None
        self.enabled = True
        self._authenticate()

    def _authenticate(self):
        """
        Autentica con Google Drive usando credenciales OAuth.
        Maneja archivos credentials.json vacíos o corruptos de forma silenciosa.
        """
        creds = None
        self.enabled = True

        # --- Validar o crear credentials.json ---
        if self.creds_path.exists():
            try:
                with open(self.creds_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, dict) or 'installed' not in data:
                    print("[GDrive] ⚠️ credentials.json no tiene formato válido (falta 'installed').")
                    print("   Descarga el archivo correcto desde Google Cloud Console.")
                    self.enabled = False
                    self.service = None
                    return
            except json.JSONDecodeError:
                print("[GDrive] ⚠️ credentials.json está vacío o tiene JSON inválido.")
                print("   Descarga el archivo correcto desde Google Cloud Console.")
                self.enabled = False
                self.service = None
                return
        else:
            # Crear archivo de ejemplo
            print("[GDrive] ⚠️ No se encuentra credentials.json. Creando archivo de ejemplo...")
            example_creds = {
                "installed": {
                    "client_id": "TU_CLIENT_ID.apps.googleusercontent.com",
                    "project_id": "tu-proyecto",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": "TU_CLIENT_SECRET",
                    "redirect_uris": ["http://localhost"]
                }
            }
            try:
                self.creds_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.creds_path, 'w', encoding='utf-8') as f:
                    json.dump(example_creds, f, indent=2)
                print("[GDrive] ✅ Archivo credentials.json de ejemplo creado.")
                print("   Reemplázalo con tus credenciales reales desde Google Cloud Console.")
            except Exception as e:
                print(f"[GDrive] ⚠️ No se pudo crear credentials.json: {e}")
            self.enabled = False
            self.service = None
            return

        # --- Cargar token si existe ---
        if self.token_path.exists():
            try:
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception:
                pass

        # --- Si no hay credenciales válidas, pedir login ---
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.creds_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"[GDrive] Error en autenticación: {e}")
                    self.enabled = False
                    self.service = None
                    return

            # Guardar token para futuras ejecuciones
            try:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception:
                pass

        # --- Construir servicio ---
        try:
            self.service = build('drive', 'v3', credentials=creds)
            self.enabled = True
            print("[GDriveIntegration] ✅ Autenticado correctamente.")
        except Exception as e:
            print(f"[GDrive] Error al construir servicio: {e}")
            self.enabled = False
            self.service = None

    def _check_auth(self) -> bool:
        """Verifica que el servicio esté autenticado y habilitado."""
        if not self.enabled or self.service is None:
            print("[GDrive] ⚠️ Servicio no autenticado. Revisa credentials.json")
            return False
        return True

    # ============================================================
    # FUNCIONES PRINCIPALES
    # ============================================================

    def upload_file(self, file_path: str, folder_id: Optional[str] = None) -> str:
        """
        Sube un archivo a Google Drive.

        Args:
            file_path: Ruta local del archivo.
            folder_id: ID de la carpeta en Drive (opcional).

        Returns:
            Mensaje de resultado.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        if not os.path.exists(file_path):
            return f"❌ Archivo no encontrado: {file_path}"

        try:
            file_metadata = {
                'name': os.path.basename(file_path)
            }
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()

            file_name = file.get('name', os.path.basename(file_path))
            file_id = file.get('id', '')
            web_link = file.get('webViewLink', '')

            return f"✅ Archivo subido a Drive: {file_name} (ID: {file_id})\n🔗 {web_link}"

        except Exception as e:
            return f"❌ Error al subir archivo: {str(e)}"

    def download_file(self, file_id: str, output_path: Optional[str] = None) -> str:
        """
        Descarga un archivo de Google Drive.

        Args:
            file_id: ID del archivo en Drive.
            output_path: Ruta donde guardar (opcional, usa el nombre original).

        Returns:
            Mensaje de resultado.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            file_meta = self.service.files().get(fileId=file_id, fields='name').execute()
            file_name = file_meta.get('name', f'drive_file_{file_id}')

            if output_path is None:
                output_path = os.path.join(os.getcwd(), file_name)
            elif os.path.isdir(output_path):
                output_path = os.path.join(output_path, file_name)

            request = self.service.files().get_media(fileId=file_id)
            with open(output_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

            return f"✅ Archivo descargado: {output_path}"

        except Exception as e:
            return f"❌ Error al descargar archivo: {str(e)}"

    def delete_file(self, file_id: str) -> str:
        """
        Elimina un archivo de Google Drive (mueve a la papelera).

        Args:
            file_id: ID del archivo en Drive.

        Returns:
            Mensaje de resultado.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            self.service.files().delete(fileId=file_id).execute()
            return f"✅ Archivo {file_id} eliminado (papelera)."
        except Exception as e:
            return f"❌ Error al eliminar archivo: {str(e)}"

    def list_files(self, max_results: int = 10, query: str = "") -> str:
        """
        Lista los archivos en Google Drive, opcionalmente con filtro.

        Args:
            max_results: Número máximo de resultados.
            query: Consulta de búsqueda (ej: "name contains 'informe'").

        Returns:
            Lista formateada de archivos.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            q = query if query else ""
            results = self.service.files().list(
                pageSize=max_results,
                q=q,
                fields="files(id, name, mimeType, size, webViewLink, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()

            files = results.get('files', [])
            if not files:
                return "📭 No se encontraron archivos en Drive."

            output = ["📂 Archivos en Drive:"]
            for f in files:
                name = f.get('name', 'Sin nombre')
                mime = f.get('mimeType', '')
                size = f.get('size', '0')
                modified = f.get('modifiedTime', '')[:10]
                is_folder = 'folder' in mime
                icon = "📁" if is_folder else "📄"
                size_str = f"({int(size)//1024} KB)" if not is_folder else ""
                output.append(f"{icon} {name} {size_str}  [{modified}]")
            return "\n".join(output)

        except Exception as e:
            return f"❌ Error al listar archivos: {str(e)}"

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """
        Crea una carpeta en Google Drive.

        Args:
            folder_name: Nombre de la carpeta.
            parent_id: ID de la carpeta padre (opcional).

        Returns:
            Mensaje con el ID de la carpeta creada.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            folder_id = folder.get('id')
            return f"✅ Carpeta '{folder_name}' creada con ID: {folder_id}"

        except Exception as e:
            return f"❌ Error al crear carpeta: {str(e)}"

    def search_files(self, query: str, max_results: int = 10) -> str:
        """
        Busca archivos por nombre o contenido.

        Args:
            query: Texto a buscar.
            max_results: Número máximo de resultados.

        Returns:
            Lista formateada de archivos encontrados.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        q = f"name contains '{query}' or fullText contains '{query}'"
        return self.list_files(max_results, q)

    def get_file_info(self, file_id: str) -> str:
        """
        Obtiene información detallada de un archivo.

        Args:
            file_id: ID del archivo en Drive.

        Returns:
            Información formateada.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents, owners"
            ).execute()

            info = [
                f"📄 {file.get('name', 'Sin nombre')}",
                f"  ID: {file.get('id', 'N/A')}",
                f"  Tipo: {file.get('mimeType', 'N/A')}",
                f"  Tamaño: {int(file.get('size', 0)) // 1024} KB" if file.get('size') else "  Tamaño: N/A",
                f"  Creado: {file.get('createdTime', 'N/A')[:10]}",
                f"  Modificado: {file.get('modifiedTime', 'N/A')[:10]}",
                f"  Enlace: {file.get('webViewLink', 'N/A')}"
            ]
            return "\n".join(info)

        except Exception as e:
            return f"❌ Error al obtener información: {str(e)}"

    def share_file(self, file_id: str, email: str, role: str = 'reader') -> str:
        """
        Comparte un archivo con un usuario.

        Args:
            file_id: ID del archivo.
            email: Correo del usuario.
            role: 'reader' | 'writer' | 'commenter'

        Returns:
            Mensaje de resultado.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            return f"✅ Archivo compartido con {email} como {role}."

        except Exception as e:
            return f"❌ Error al compartir archivo: {str(e)}"

    def get_folder_contents(self, folder_id: str = 'root', max_results: int = 20) -> str:
        """
        Lista el contenido de una carpeta específica.

        Args:
            folder_id: ID de la carpeta ('root' para raíz).
            max_results: Número máximo de resultados.

        Returns:
            Lista formateada.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        try:
            q = f"'{folder_id}' in parents and trashed=false"
            return self.list_files(max_results, q)

        except Exception as e:
            return f"❌ Error al listar contenido: {str(e)}"

    def upload_folder(self, folder_path: str, parent_id: Optional[str] = None) -> str:
        """
        Sube una carpeta completa y su contenido recursivamente.

        Args:
            folder_path: Ruta local de la carpeta.
            parent_id: ID de la carpeta padre en Drive (opcional).

        Returns:
            Mensaje de resultado.
        """
        if not self._check_auth():
            return "❌ Servicio de Google Drive no autenticado."

        if not os.path.isdir(folder_path):
            return f"❌ No es una carpeta válida: {folder_path}"

        folder_name = os.path.basename(folder_path)
        result = self.create_folder(folder_name, parent_id)
        # Extraer ID de la carpeta creada
        folder_id = None
        for part in result.split(' '):
            if part.startswith('ID:'):
                folder_id = part.replace('ID:', '')
                break

        if not folder_id:
            return f"❌ No se pudo obtener el ID de la carpeta creada."

        uploaded = 0
        failed = 0
        current_parent = folder_id

        for root, dirs, files in os.walk(folder_path):
            relative_root = os.path.relpath(root, folder_path)
            if relative_root == '.':
                current_parent = folder_id
            else:
                subfolder_name = os.path.basename(root)
                create_result = self.create_folder(subfolder_name, current_parent)
                # Extraer ID (simplificado)
                for part in create_result.split(' '):
                    if part.startswith('ID:'):
                        current_parent = part.replace('ID:', '')
                        break
                if not current_parent:
                    failed += 1
                    continue

            for file in files:
                file_path = os.path.join(root, file)
                result_upload = self.upload_file(file_path, current_parent)
                if '✅' in result_upload:
                    uploaded += 1
                else:
                    failed += 1

        return f"✅ Carpeta subida: {uploaded} archivos, {failed} fallos."

    # ============================================================
    # ALIAS PARA COMPATIBILIDAD
    # ============================================================

    def upload(self, file_path: str, folder_id: Optional[str] = None) -> str:
        return self.upload_file(file_path, folder_id)

    def download(self, file_id: str, output_path: Optional[str] = None) -> str:
        return self.download_file(file_id, output_path)

    def delete(self, file_id: str) -> str:
        return self.delete_file(file_id)

    def list(self, max_results: int = 10) -> str:
        return self.list_files(max_results)


# ===== PRUEBA RÁPIDA =====
if __name__ == "__main__":
    print("🧪 Probando GDriveIntegration...")
    gdrive = GDriveIntegration()

    if gdrive.enabled:
        print("\n📂 Listando archivos:")
        print(gdrive.list_files(5))

        print("\n📁 Creando carpeta de prueba:")
        print(gdrive.create_folder("AP0L0_Test"))

        print("\n🔍 Buscando 'informe':")
        print(gdrive.search_files("informe", 3))
    else:
        print("⚠️ GDrive no disponible. Verifica credentials.json")