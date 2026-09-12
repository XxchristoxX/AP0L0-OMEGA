import time
import threading
import os
import re
from developer_gui import JarvisDeveloperGUI
from dotenv import load_dotenv

# Carga las claves API (desde .env o del entorno)
load_dotenv()

# Intenta cargar los clientes de IA
api_gemini = os.environ.get("GEMINI_API_KEY")
api_anthropic = os.environ.get("ANTHROPIC_API_KEY")
api_grok = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
api_openai = os.environ.get("OPENAI_API_KEY")


class ProjectBuilder:
    """
    Orquestador REAL de desarrollo autónomo.
    Genera código mediante Gemini y lo escribe físicamente en la carpeta seleccionada.
    """
    def __init__(self, gui: JarvisDeveloperGUI):
        self.gui = gui
        self.project_path = None
        self.project_name = None
        self.run_id = None
        # Historial de conversación en sesión (multiturno)
        # Formato universal: [{"role": "user"|"assistant", "content": str}]
        self.conversation_history = []
        self._MAX_HISTORY = 20  # Límite a los 20 últimos intercambios para evitar saturación de tokens

    def cancel_generation(self):
        self.run_id = None
        # Hacer la UI inmediatamente disponible
        if hasattr(self.gui, 'stop_button'): self.gui.stop_button.configure(state="disabled")
        if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="normal")
        if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="normal")
        self.gui.update_status("Cancelado", color="#e74c3c", loading=False)

    def start_project(self, project_name, project_path):
        """Define la carpeta de trabajo."""
        self.project_path = project_path
        self.project_name = project_name
        self.gui.set_project_path(project_path)
        self.gui.show_dev_panel()
        self.gui.update_status(f"Carpeta lista: {project_name}", color="#f39c12")
        self.gui.log_to_terminal(f"=== Carpeta definida en {project_path} ===")
        self.gui.log_to_terminal("Esperando sus instrucciones...")

    def load_existing_project(self, folder_path):
        """Abre un proyecto existente y llena la interfaz."""
        project_name = os.path.basename(folder_path)
        self.project_path = folder_path
        self.project_name = project_name
        
        self.gui.set_project_path(folder_path)
        self.gui.show_dev_panel()
        self.gui.update_status(f"Proyecto cargado: {project_name}", color="#2ecc71")
        self.gui.log_to_terminal(f"=== Abriendo proyecto {folder_path} ===")
        
        # Escanea la carpeta para construir el árbol
        structure = self._scan_directory(folder_path)
        self.gui.update_file_tree(structure)
        
        # Intentar abrir index.html o un archivo python/js primero
        first_file = None
        for root, dirs, files in os.walk(folder_path):
            if '.git' in dirs: dirs.remove('.git')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if 'venv' in dirs: dirs.remove('venv')
            for f in files:
                if f.endswith('.html') or f.endswith('.py') or f.endswith('.js'):
                    first_file = os.path.relpath(os.path.join(root, f), folder_path).replace("\\", "/")
                    break
            if first_file: break
            
        if first_file:
            try:
                with open(os.path.join(folder_path, first_file), 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.gui.update_code_viewer(first_file, content)
            except Exception as e:
                pass

    def _scan_directory(self, path, root_path=None):
        if root_path is None:
            root_path = path
        structure = {}
        try:
            for item in os.listdir(path):
                if item in ['.git', '__pycache__', 'venv', 'node_modules', '.env']:
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    structure[item] = self._scan_directory(full_path, root_path)
                else:
                    structure[item] = "file"
        except Exception as e:
            pass
        return structure

    def handle_message(self, message, image_path=None):
        """Recibe el mensaje del usuario desde la interfaz."""
        if not self.project_path:
            self.gui.log_chat("Primero debe hacer clic en 'Crear Proyecto...' para elegir una carpeta.", sender="Sistema")
            return
            
        self.gui.log_chat("Analizando su solicitud...", sender="Jarvis")
        
        # Desactivar UI
        if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="disabled")
        if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="disabled")
        
        # Agregar el mensaje del usuario al historial de conversación
        self.conversation_history.append({"role": "user", "content": message})
        # Limitar el tamaño del historial
        if len(self.conversation_history) > self._MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(self._MAX_HISTORY * 2):]
        
        # Nuevo run_id
        import uuid
        self.run_id = uuid.uuid4().hex
        
        # Lanzar la generación en un hilo para no bloquear la UI
        threading.Thread(target=self._generate_code_loop, args=(message, image_path, self.run_id), daemon=True).start()

    def _build_context(self):
        """Recupera el contenido de los archivos existentes para dar contexto a la IA."""
        context = ""
        if not self.project_path or not os.path.exists(self.project_path):
            return context
            
        files_found = []
        file_count = 0
        for root, dirs, files in os.walk(self.project_path):
            if '.git' in dirs: dirs.remove('.git')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if 'venv' in dirs: dirs.remove('venv')
            for file in files:
                if file_count >= 15: # Límite a 15 archivos
                    break
                if file.endswith(('.html', '.css', '.js', '.py', '.json', '.txt')):
                    full_path = os.path.join(root, file)
                    # Ignorar archivos demasiado grandes (>100KB)
                    if os.path.getsize(full_path) > 100000:
                        continue
                    rel_path = os.path.relpath(full_path, self.project_path).replace("\\", "/")
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        files_found.append(f"--- Archivo existente: {rel_path} ---\n{content}\n")
                        file_count += 1
                    except:
                        pass
                        
        if files_found:
            context += "\nAquí está el estado ACTUAL de los archivos del proyecto. Usa este contexto para aplicar la solicitud del usuario. DEBES reescribir siempre los archivos completos con tus modificaciones.\n"
            context += "\n".join(files_found)
        return context

    def _build_memory_context(self):
        """Carga y devuelve el contexto de la memoria persistente (jarvis_memoire.json)."""
        try:
            from memory_manager import construir_contexto_memoria
            return construir_contexto_memoria()
        except Exception as e:
            print(f"[DEV-MEMORY] Error al cargar memoria: {e}")
            return ""

    def _save_exchange_to_memory(self, user_text, model_text):
        """Guarda el intercambio en jarvis_conversations.json Y en ObsidianVault/Journal_Discussions.md."""
        try:
            from memory_manager import _guardar_intercambio_conv
            _guardar_intercambio_conv(user_text, model_text)
        except Exception as e:
            print(f"[DEV-MEMORY] Error al guardar intercambio: {e}")

    def _generate_code_loop(self, prompt, image_path=None, my_run_id=None):
        self.gui.update_status("Generación IA...", color="#3498db", loading=True)
        selected_model_name = self.gui.model_var.get()
        selected_image_model = self.gui.image_model_var.get()
        self.gui.log_to_terminal(f"> Solicitud a la IA ({selected_model_name}): {prompt}")
        
        if self.run_id != my_run_id:
            raise Exception("Cancelado por el usuario")
            
        base64_image = None
        mime_type = "image/jpeg"
        if image_path and os.path.exists(image_path):
            import base64
            import mimetypes
            try:
                with open(image_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")
                mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
                self.gui.log_to_terminal(f"> Imagen adjunta detectada: {os.path.basename(image_path)}")
            except Exception as e:
                self.gui.log_to_terminal(f"> Error al leer la imagen: {e}")
        
        # === MEMORIA OBSIDIAN: Cargar contexto persistente ===
        mem_context = self._build_memory_context()
        mem_section = ""
        if mem_context:
            mem_section = f"\n\nMEMORIA PERSONAL (información persistente sobre el usuario):\n{mem_context}\n"
        
        system_prompt = """Eres Jarvis, un desarrollador IA experto y arquitecto de software. El usuario quiere crear un proyecto de software (web, móvil, script Python, juego, etc.).
Recuerdas TODA la conversación desde el inicio de la sesión. Usa el contexto de los mensajes anteriores para entender las modificaciones solicitadas.
Genera ÚNICAMENTE el código de los archivos necesarios en este formato exacto y estricto, sin ningún texto adicional antes o después:

---BEGIN_FILE: nombre_del_archivo.ext---
[código completo del archivo aquí]
---END_FILE---

Puedes generar tantos archivos como sea necesario (ej: main.py, app.js, index.html, pubspec.yaml).
Para un sitio web simple, prefiere un solo archivo index.html. Para una aplicación o proyecto complejo, separa correctamente los archivos según las buenas prácticas del lenguaje solicitado.
Sé profesional, genera código completo y funcional. No uses las etiquetas markdown ``` para rodear el texto de los archivos.

IMPORTANTE PARA ASSETS/IMÁGENES:
Si tu código necesita cargar imágenes dinámicas, logotipos o fotos, DEBES usar esta etiqueta especial en el lugar exacto donde se espera la ruta del archivo:
[GENERATE_IMAGE: descripción ultra detallada en inglés]
Ejemplos según el lenguaje:
HTML : <img src="[GENERATE_IMAGE: A cute cat, 4k, photorealistic]" alt="Cat">
Python (Tkinter/Pygame) : image_path = "[GENERATE_IMAGE: A futuristic city skyline]"
React : <Image source={{uri: '[GENERATE_IMAGE: App logo icon, minimalist]'}} />

Jarvis generará la imagen en segundo plano y reemplazará tu etiqueta únicamente por la ruta relativa del archivo de imagen (ej: 'assets/img_1.jpg'). No inventes URLs de internet o archivos locales que no existan.

REGLAS ABSOLUTAS PARA MODIFICACIONES DE CÓDIGO:
Si el código existente que el usuario te proporciona YA contiene rutas de imágenes locales (ej: "assets/img_retro_pixel.jpg"), DEBES CONSERVARLAS TAL CUAL. No las reemplaces NUNCA por una nueva etiqueta [GENERATE_IMAGE: ...] a menos que el usuario te pida explícitamente cambiar el diseño o las imágenes. Si corriges un simple error, deja las rutas de imágenes intactas."""

        # Inyección de la memoria persistente en el prompt del sistema
        if mem_section:
            system_prompt += mem_section
        self.gui.log_to_terminal("> Paso 1/4: Análisis de sus archivos existentes...")
        existing_context = self._build_context()
        
        # PASO 1: Mejora del prompt (Opcional)
        is_new_project = not bool(existing_context)
        
        # Verifica el estado del checkbox "Prompt Auto"
        enrich_enabled = getattr(self.gui, 'enrich_prompt_var', None)
        if enrich_enabled is not None and not enrich_enabled.get():
            self.gui.log_to_terminal("> Paso 2/4: Prompt bruto enviado (sin mejora automática).")
            if is_new_project:
                full_user_prompt = f"Solicitud del usuario:\n{prompt}"
            else:
                full_user_prompt = f"{existing_context}\n\nSolicitud del usuario (a aplicar ABSOLUTAMENTE al código):\n{prompt}"
        else:
            if is_new_project:
                self.gui.log_to_terminal("> Paso 2/4: Mejorando su prompt (Creación)...")
                enhanced_prompt = self._enhance_prompt(prompt, is_new=True, base64_image=base64_image, mime_type=mime_type, selected_model_name=selected_model_name)
                
                if enhanced_prompt and enhanced_prompt.strip():
                    full_user_prompt = f"Solicitud del usuario mejorada:\n{enhanced_prompt}"
                else:
                    self.gui.log_to_terminal("> (Advertencia) La IA devolvió un prompt vacío. Usando su solicitud original.")
                    full_user_prompt = f"Solicitud del usuario:\n{prompt}"
            else:
                self.gui.log_to_terminal("> Paso 2/4: Análisis de su solicitud de modificación...")
                # Pasamos el historial de conversación para que la IA sepa de qué proyecto se trata
                enhanced_prompt = self._enhance_prompt(prompt, is_new=False, base64_image=base64_image, mime_type=mime_type, selected_model_name=selected_model_name, conv_history=self.conversation_history)
                
                if enhanced_prompt and enhanced_prompt.strip():
                    full_user_prompt = f"{existing_context}\n\nSolicitud del usuario mejorada (a aplicar ABSOLUTAMENTE al código):\n{enhanced_prompt}"
                else:
                    self.gui.log_to_terminal("> (Advertencia) La IA devolvió un prompt vacío. Usando su solicitud original.")
                    full_user_prompt = f"{existing_context}\n\nSolicitud del usuario (a aplicar ABSOLUTAMENTE al código):\n{prompt}"
        
        if self.run_id != my_run_id: raise Exception("Cancelado por el usuario")
        self.gui.log_to_terminal("> Paso 3/4: Generando el código completo (normalmente toma entre 30 y 60 segundos)...")
        self.gui.update_status("Creando código...", color="#3498db", loading=True)
        
        # === CONSTRUCCIÓN DEL HISTORIAL MULTITURNO ===
        # Recuperamos todo el historial EXCEPTO el último mensaje del usuario (ya está en full_user_prompt)
        history_for_ai = self.conversation_history[:-1]  # Excluir el último (mensaje actual)
        
        try:
            raw_text = ""
            if "Gemini" in selected_model_name:
                import google.genai as genai
                if not api_gemini: raise Exception("Falta GEMINI_API_KEY.")
                client = genai.Client(api_key=api_gemini)
                model_id = "gemini-2.5-flash"
                if "3.5 Flash" in selected_model_name: model_id = "gemini-3.5-flash"
                elif "3.1 Pro" in selected_model_name: model_id = "gemini-3.1-pro-preview"
                elif "Pro" in selected_model_name: model_id = "gemini-2.5-pro"
                elif "1.5 Pro" in selected_model_name: model_id = "gemini-1.5-pro"
                
                # Construcción de los contenidos Gemini con historial multiturno
                contents = []
                # Inyectar system_prompt como primer mensaje usuario/modelo si el historial está vacío
                if not history_for_ai:
                    contents.append({"role": "user", "parts": [{"text": system_prompt}]})
                    contents.append({"role": "model", "parts": [{"text": "Entendido. Estoy listo para generar su proyecto."}]})
                else:
                    # Inyectar system en el primer mensaje del historial
                    first_user = history_for_ai[0]
                    contents.append({"role": "user", "parts": [{"text": system_prompt + "\n\nPrimer intercambio:\n" + first_user["content"]}]})
                    # Agregar el resto del historial
                    for h in history_for_ai[1:]:
                        gemini_role = "model" if h["role"] == "assistant" else "user"
                        contents.append({"role": gemini_role, "parts": [{"text": h["content"]}]})
                
                # Mensaje actual
                current_parts = [{"text": full_user_prompt}]
                if base64_image:
                    current_parts.append({"inlineData": {"mimeType": mime_type, "data": base64_image}})
                contents.append({"role": "user", "parts": current_parts})
                
                response = client.models.generate_content(
                    model=model_id,
                    contents=contents
                )
                raw_text = response.text
                
            elif "Claude" in selected_model_name:
                import anthropic
                if not api_anthropic: raise Exception("Falta ANTHROPIC_API_KEY.")
                client = anthropic.Anthropic(api_key=api_anthropic)
                model_id = "claude-sonnet-5"
                if "Fable" in selected_model_name: model_id = "claude-fable-5"
                elif "Opus" in selected_model_name: model_id = "claude-opus-4-8"
                
                # Construcción de mensajes Claude con historial multiturno
                claude_messages = []
                for h in history_for_ai:
                    claude_role = "assistant" if h["role"] == "assistant" else "user"
                    claude_messages.append({"role": claude_role, "content": h["content"]})
                
                # Mensaje actual (con imagen si existe)
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_image}}
                    ]
                claude_messages.append({"role": "user", "content": msg_content})
                
                response = client.messages.create(
                    model=model_id,
                    max_tokens=4000,
                    system=system_prompt,
                    messages=claude_messages
                )
                raw_text = response.content[0].text
                
            elif "Grok" in selected_model_name:
                import openai
                if not api_grok: raise Exception("Falta XAI_API_KEY.")
                client = openai.OpenAI(api_key=api_grok, base_url="https://api.x.ai/v1")
                model_id = "grok-4.5"
                if "4.20" in selected_model_name: model_id = "grok-420-reasoning"
                
                # Construcción de mensajes Grok (compatible OpenAI) con historial multiturno
                grok_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    grok_messages.append({"role": h["role"], "content": h["content"]})
                
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                grok_messages.append({"role": "user", "content": msg_content})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=grok_messages
                )
                raw_text = response.choices[0].message.content
                
            elif "ChatGPT" in selected_model_name:
                import openai
                if not api_openai: raise Exception("Falta OPENAI_API_KEY.")
                client = openai.OpenAI(api_key=api_openai)
                
                model_id = "gpt-4o"
                if "(" in selected_model_name and ")" in selected_model_name:
                    model_id = selected_model_name.split("(")[1].split(")")[0]
                
                # IMPORTANTE: Para modelos de razonamiento (o1, luna, etc.) que ignoran el rol "system",
                # se inyectan forzosamente las instrucciones de formato en el prompt del usuario.
                # Construcción del historial multiturno para ChatGPT/OpenAI
                openai_messages = []
                # Inyectar system_prompt en el primer mensaje del usuario
                if not history_for_ai:
                    combined_first = f"{system_prompt}\n\n{full_user_prompt}"
                    if base64_image:
                        msg_content = [
                            {"type": "text", "text": combined_first},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                        ]
                    else:
                        msg_content = combined_first
                    openai_messages.append({"role": "user", "content": msg_content})
                else:
                    # Primer mensaje del historial: inyectar system_prompt en él
                    first_h = history_for_ai[0]
                    openai_messages.append({"role": "user", "content": f"{system_prompt}\n\n{first_h['content']}"})
                    for h in history_for_ai[1:]:
                        openai_messages.append({"role": h["role"], "content": h["content"]})
                    # Mensaje actual
                    msg_content = full_user_prompt
                    if base64_image:
                        msg_content = [
                            {"type": "text", "text": full_user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                        ]
                    openai_messages.append({"role": "user", "content": msg_content})
                
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=openai_messages,
                        max_completion_tokens=8000
                    )
                    raw_text = response.choices[0].message.content
                except Exception as e1:
                    try:
                        response = client.chat.completions.create(
                            model=model_id,
                            messages=openai_messages,
                            max_tokens=8000
                        )
                        raw_text = response.choices[0].message.content
                    except Exception as e2:
                        try:
                            combined_prompt = f"{system_prompt}\n\n{full_user_prompt}"
                            response = client.completions.create(
                                model=model_id,
                                prompt=combined_prompt,
                                max_tokens=8000
                            )
                            raw_text = response.choices[0].text
                        except Exception:
                            raise e1
                
            elif "Mistral" in selected_model_name or "Codestral" in selected_model_name:
                import openai
                api_mistral = os.environ.get("MISTRAL_API_KEY")
                if not api_mistral: raise Exception("Falta MISTRAL_API_KEY.")
                client = openai.OpenAI(api_key=api_mistral, base_url="https://api.mistral.ai/v1")
                model_id = "mistral-large-latest"
                if "Codestral" in selected_model_name: model_id = "codestral-latest"
                
                # Construcción de mensajes Mistral (compatible OpenAI) con historial multiturno
                mistral_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    mistral_messages.append({"role": h["role"], "content": h["content"]})
                
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                mistral_messages.append({"role": "user", "content": msg_content})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=mistral_messages
                )
                raw_text = response.choices[0].message.content
                
            elif "(Local)" in selected_model_name:
                from local_agent_manager import JarvisLocalAgentManager
                
                ollama_tags = {
                    "Ornith-1.0 (Local)": "ornith:9b",
                    "Ornith-35b (Local)": "ornith:35b",
                    "Qwen2.5-Coder (Local)": "qwen2.5-coder:7b",
                    "DeepSeek-Coder (Local)": "deepseek-coder-v2"
                }
                target_model = ollama_tags.get(selected_model_name, "ornith:9b")
                
                agent = JarvisLocalAgentManager(model_name=target_model)
                
                is_ready, status = agent.check_system()
                if not is_ready:
                    self.gui.log_to_terminal("=== ERROR AGENTE LOCAL ===")
                    if status == "OLLAMA_NOT_RUNNING":
                        self.gui.log_to_terminal("❌ Ollama no está ejecutándose en esta máquina.")
                    else:
                        self.gui.log_to_terminal(f"❌ El modelo '{agent.model}' no está descargado.")
                        
                    self.gui.log_to_terminal("\n💡 GUÍA DE INSTALACIÓN:")
                    self.gui.log_to_terminal("1. Vaya a https://ollama.com y descargue Ollama.")
                    self.gui.log_to_terminal("2. Ejecute la aplicación Ollama en segundo plano.")
                    self.gui.log_to_terminal(f"3. Abra una terminal y escriba: ollama pull {agent.model}")
                    self.gui.log_to_terminal("4. Reinicie esta solicitud en JARVIS.")
                    self.gui.log_to_terminal("="*50)
                    raise Exception(f"Agente local no disponible ({status}).")
                
                if base64_image:
                    self.gui.log_to_terminal("> Atención: El agente local (texto) ignora las imágenes por ahora.")
                
                # Construcción de mensajes Ollama con historial multiturno
                local_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    local_messages.append({"role": h["role"], "content": h["content"]})
                local_messages.append({"role": "user", "content": full_user_prompt})
                
                response_text = agent.generate_response(local_messages, strip_thinking=True)
                if response_text:
                    raw_text = response_text
                else:
                    raise Exception("El agente local no devolvió ninguna respuesta.")
                
            self.gui.log_to_terminal(f"> Código recibido de {selected_model_name} !")
            self.gui.update_status("Escribiendo...", color="#9b59b6")
            
            # PASO 2.5: Procesamiento y generación de imágenes nativas
            self.gui.log_to_terminal("> Paso 4/4: Procesando imágenes nativas...")
            raw_text = self._process_images(raw_text, selected_model_name, selected_image_model, my_run_id)
            
            if self.run_id != my_run_id: raise Exception("Cancelado por el usuario")
            
            # Guardar en archivos
            self._parse_and_save_files(raw_text)
            
            # === MEMORIA OBSIDIAN: Guardar el intercambio en Journal_Discussions.md ===
            # Resumen de la respuesta IA (limitado para el diario)
            _response_summary = raw_text[:1500] if raw_text else "(código generado)"
            self._save_exchange_to_memory(prompt, _response_summary)
            self.gui.log_to_terminal("> [Memoria] Intercambio guardado en Obsidian (Journal_Discussions.md).")
            
            # === HISTORIAL: Agregar la respuesta IA al historial de conversación ===
            # Almacenamos un resumen útil para que los próximos mensajes tengan contexto
            self.conversation_history.append({"role": "assistant", "content": f"Procesé la solicitud '{prompt[:200]}' y generé el código correspondiente en el proyecto '{self.project_name}'."})
            
            self.gui.update_status("Terminado", color="#2ecc71", loading=False)
            self.gui.log_to_terminal("=== Proyecto generado con éxito ===")
            self.gui.log_chat("¡Listo! He generado su proyecto en la carpeta. Puede hacer clic en 'Abrir Carpeta' o 'Abrir en VS Code'.", sender="Jarvis")
            
        except Exception as e:
            if "Cancelado por el usuario" in str(e):
                self.gui.log_to_terminal("[STOP] : Generación cancelada por el usuario.")
                self.gui.update_status("Cancelado", color="#e74c3c", loading=False)
                # Eliminar el último mensaje del usuario del historial (cancelado)
                if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                    self.conversation_history.pop()
            else:
                self.gui.log_to_terminal(f"[ERROR API] : {str(e)}")
                self.gui.update_status("Error API", color="red", loading=False)
                self.gui.log_chat(f"Ocurrió un error: {str(e)}\n(Consulte el terminal para más detalles)", sender="Jarvis")
                # Eliminar el último mensaje del usuario del historial (error)
                if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                    self.conversation_history.pop()
        finally:
            if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="normal")
            if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="normal")
            if hasattr(self.gui, 'stop_button'): self.gui.stop_button.configure(state="disabled")

    def _enhance_prompt(self, user_prompt, is_new=True, base64_image=None, mime_type="image/jpeg", selected_model_name="Gemini", conv_history=None):
        """Mejora el prompt usando requests para evitar bloqueos del SDK."""
        if is_new:
            enhancement_prompt = f"""El usuario quiere crear un proyecto de software completamente nuevo (Web, Móvil, Script Python, etc.): '{user_prompt}'.
Redacta en su lugar un prompt de arquitectura y diseño ultradetallado.
INSTRUCCIONES ESTRICTAS:
- Si es un sitio web o una aplicación con interfaz gráfica: Exige un estilo ultra premium, moderno y elegante. Pide una excelente UX.
- Si es un script, un bot o una herramienta CLI: Exige un código robusto, documentado, con manejo de errores.
- No asumas que es web si el usuario pide Python u otra cosa.
Responde ÚNICAMENTE con el prompt final en bruto, sin adornos."""
        else:
            # Construir un resumen de la conversación reciente para dar contexto
            conv_context = ""
            if conv_history:
                # Tomar los últimos 6 intercambios (para no sobrecargar)
                recent = conv_history[-6:]
                lines = []
                for h in recent:
                    role_label = "Usuario" if h["role"] == "user" else "Jarvis"
                    lines.append(f"{role_label}: {h['content'][:300]}")
                if lines:
                    conv_context = "\n\nCONTEXTO DE LA CONVERSACIÓN ACTUAL:\n" + "\n".join(lines) + "\n"
            
            enhancement_prompt = f"""El usuario solicita una modificación en un proyecto existente.{conv_context}
Nueva solicitud del usuario: '{user_prompt}'.
Analiza la solicitud teniendo en cuenta el contexto de la conversación anterior:
1. Si es un PEQUEÑO retoque (corregir un error, ajustar la interfaz): Redacta un prompt técnico preciso. Prohíbe la refundición completa.
2. Si es una REFUNDICIÓN MAYOR o la adición de una gran funcionalidad: Redacta un prompt que permita modificar la arquitectura y generar nuevas imágenes con [GENERATE_IMAGE: descripción].
3. SI SE PROPORCIONA UNA IMAGEN, analízala con atención para entender el error visual o el modelo a reproducir.
4. IMPORTANTE: Si la solicitud es vaga o corta, usa el contexto de la conversación para deducir en qué elemento específico quiere actuar el usuario.

Redacta este prompt final para el desarrollador. Responde ÚNICAMENTE con el prompt en bruto, sin ninguna frase de introducción."""
            
        api_gemini_key = os.environ.get("GEMINI_API_KEY")
        api_grok_key = os.environ.get("XAI_API_KEY")
        api_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        api_mistral_key = os.environ.get("MISTRAL_API_KEY")
        api_openai_key = os.environ.get("OPENAI_API_KEY")
        
        if "Grok" in selected_model_name and api_grok_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_grok_key, base_url="https://api.x.ai/v1")
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.chat.completions.create(
                    model="grok-4.5",
                    messages=[{"role": "user", "content": msg_content}],
                    temperature=0.7,
                    max_completion_tokens=4000
                )
                enhanced_prompt = response.choices[0].message.content
                self.gui.log_to_terminal(f"> Prompt mejorado por Grok:\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Advertencia) La mejora con Grok falló ({e}).")
                
        elif "Claude" in selected_model_name and api_anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_anthropic_key)
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_image}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": msg_content}]
                )
                enhanced_prompt = response.content[0].text
                self.gui.log_to_terminal(f"> Prompt mejorado por Claude:\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Advertencia) La mejora con Claude falló ({e}).")
                
        elif "ChatGPT" in selected_model_name and api_openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_openai_key)
                
                model_id = "gpt-4o"
                if "(" in selected_model_name and ")" in selected_model_name:
                    model_id = selected_model_name.split("(")[1].split(")")[0]
                    
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                try:
                    kwargs = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": msg_content}]
                    }
                    is_reasoning_model = any(keyword in model_id.lower() for keyword in ["luna", "sol", "terra", "o1", "o3"])
                    if not is_reasoning_model:
                        kwargs["max_completion_tokens"] = 4000
                        
                    response = client.chat.completions.create(**kwargs)
                    enhanced_prompt = response.choices[0].message.content
                except Exception as e1:
                    try:
                        kwargs.pop("max_completion_tokens", None)
                        if not is_reasoning_model:
                            kwargs["max_tokens"] = 4000
                        response = client.chat.completions.create(**kwargs)
                        enhanced_prompt = response.choices[0].message.content
                    except Exception as e2:
                        try:
                            comp_kwargs = {
                                "model": model_id,
                                "prompt": enhancement_prompt
                            }
                            if not is_reasoning_model:
                                comp_kwargs["max_tokens"] = 4000
                            response = client.completions.create(**comp_kwargs)
                            enhanced_prompt = response.choices[0].text
                        except Exception:
                            # Lanzar el error más relevante (e1 o e2) para mostrarlo
                            raise e1
                self.gui.log_to_terminal(f"> Prompt mejorado por ChatGPT:\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Advertencia) La mejora con ChatGPT falló ({e}).")
                
        elif ("Mistral" in selected_model_name or "Codestral" in selected_model_name) and api_mistral_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_mistral_key, base_url="https://api.mistral.ai/v1")
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.chat.completions.create(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": msg_content}],
                    temperature=0.7,
                    max_tokens=4000
                )
                enhanced_prompt = response.choices[0].message.content
                self.gui.log_to_terminal(f"> Prompt mejorado por Mistral:\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Advertencia) La mejora con Mistral falló ({e}).")
                
        elif api_gemini_key:
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_gemini_key}"
                
                parts = [{"text": enhancement_prompt}]
                if base64_image:
                    parts.append({"inlineData": {"mimeType": mime_type, "data": base64_image}})
                
                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4000}
                }
                # Timeout estricto de 30 segundos para dar tiempo a Gemini 2.5 a 'pensar'
                response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
                response.raise_for_status()
                data = response.json()
                enhanced_prompt = data["candidates"][0]["content"]["parts"][0]["text"]
                self.gui.log_to_terminal(f"> Prompt mejorado por Gemini:\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Advertencia) La mejora automática falló ({e}).")
        
        # Fallback si error o falta de clave
        return user_prompt + " (Diseño muy moderno, con animaciones fluidas, sombras elegantes y colores premium)"

    def _process_images(self, text, selected_model_name, selected_image_model, my_run_id=None):
        import re
        import uuid
        import urllib.request
        from urllib.parse import quote
        import requests
        
        pattern = r"\[GENERATE_IMAGE:\s*(.*?)\]"
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            return text
            
        self.gui.log_to_terminal(f"> Detección de {len(matches)} imágenes a generar...")
        self.gui.update_status("Generando Imágenes...", color="#e74c3c", loading=True)
        
        assets_dir = os.path.join(self.project_path, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        for i, match in enumerate(matches):
            if self.run_id != my_run_id: raise Exception("Cancelado por el usuario")
            full_tag = match.group(0)
            prompt = match.group(1).strip()
            prompt_log = prompt[:30].replace('\n', ' ')
            self.gui.log_to_terminal(f"  - Generando imagen {i+1}/{len(matches)}: {prompt_log}...")
            filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(assets_dir, filename)
            rel_path = f"assets/{filename}"
            
            success = False
            
            use_grok = "Grok" in selected_image_model or ("Auto" in selected_image_model and "Grok" in selected_model_name)
            use_openai = "ChatGPT" in selected_image_model or ("Auto" in selected_image_model and "ChatGPT" in selected_model_name)
            use_gemini = "Gemini" in selected_image_model
            use_pollinations = "Pollinations" in selected_image_model or ("Auto" in selected_image_model and not use_grok and not use_openai)
            
            # API OPENAI IMAGEN NATIVA
            if use_openai and not success:
                api_openai_img = os.environ.get("OPENAI_API_KEY")
                if api_openai_img:
                    try:
                        import openai
                        import requests
                        client = openai.OpenAI(api_key=api_openai_img)
                        resp = client.images.generate(model="gpt-image-2", prompt=prompt, n=1)
                        img_url = resp.data[0].url
                        
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        img_resp = requests.get(img_url, headers=headers, timeout=30)
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Error OpenAI Image: {e}")
            
            # API GROK IMAGINE NATIVA
            if use_grok:
                api_grok = os.environ.get("XAI_API_KEY")
                if api_grok:
                    try:
                        import openai
                        import requests
                        client = openai.OpenAI(api_key=api_grok, base_url="https://api.x.ai/v1")
                        resp = client.images.generate(model="grok-imagine-image", prompt=prompt, n=1)
                        img_url = resp.data[0].url
                        
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        img_resp = requests.get(img_url, headers=headers, timeout=30)
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Error Grok Image: {e}")

            # API GEMINI IMAGEN 4.0 NATIVA
            if not success and use_gemini:
                api_gemini = os.environ.get("GEMINI_API_KEY")
                if api_gemini:
                    try:
                        import google.genai as genai
                        client = genai.Client(api_key=api_gemini)
                        resp = client.models.generate_images(
                            model='imagen-4.0-generate-001',
                            prompt=prompt
                        )
                        image_bytes = resp.generated_images[0].image.image_bytes
                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)
                        success = True
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Error Gemini Imagen: {e}")
            
            # FALLBACK ALTA CALIDAD FLUX (Pollinations API parametrizada)
            if not success and (use_pollinations or "Auto" in selected_image_model):
                import requests
                import time
                safe_prompt = quote(prompt)
                pollinations_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&width=1024&height=1024&nologo=true"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                
                for attempt in range(3):
                    try:
                        img_resp = requests.get(pollinations_url, headers=headers, timeout=30)
                        if img_resp.status_code == 429:
                            self.gui.log_to_terminal(f"  - Servidor de imágenes sobrecargado (Anti-spam). Pausa de 5s ({attempt+1}/3)...")
                            time.sleep(5)
                            continue
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                        time.sleep(1.5) # Pequeña pausa entre imágenes
                        break
                    except requests.exceptions.ReadTimeout:
                        self.gui.log_to_terminal(f"  - El servidor de imágenes está lento, reintentando ({attempt+1}/3)...")
                        time.sleep(2)
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Error Generación Imagen: {e}")
                        break
            
            if success:
                # Reemplazar la etiqueta por la ruta relativa (la IA maneja la etiqueta HTML o Python)
                text = text.replace(full_tag, rel_path)
            
        return text

    def _parse_and_save_files(self, raw_text):
        """Parsea la respuesta de la IA y escribe los archivos en el disco duro."""
        
        # Asegurar que la carpeta del proyecto existe antes de hacer nada
        os.makedirs(self.project_path, exist_ok=True)
        
        # Regex más permisiva: acepta si falta ---END_FILE--- (ej: generación truncada por ser muy larga)
        pattern = r"---BEGIN_FILE:\s*(.+?)---(.*?)(?=---END_FILE---|---BEGIN_FILE:|$)"
        matches = list(re.finditer(pattern, raw_text, re.DOTALL | re.IGNORECASE))
        
        if not matches:
            # Fallback 1: Extraer bloques de código markdown si el modelo ignoró las instrucciones (coincide con cualquier etiqueta de lenguaje)
            md_blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*(.*?)```", raw_text, re.DOTALL)
            if md_blocks:
                self.gui.log_to_terminal("> Formato Markdown detectado (Modo Rescate)...")
                content = "\n\n".join(md_blocks)
                filename = "index.html"
                full_path = os.path.join(self.project_path, filename)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content.strip())
                self.gui.log_to_terminal(f"> Creado: {filename} (vía modo rescate)")
                
                structure = {filename: "file"}
                self.gui.update_file_tree(structure)
                if os.path.exists(full_path):
                    self.gui.current_open_file = filename
                    self.gui.update_code_viewer(filename, content.strip())
                return
            
            # Fallback 2: Etiquetas HTML directas
            if "<html" in raw_text.lower() or "<!doctype html>" in raw_text.lower():
                self.gui.log_to_terminal("> Formato HTML bruto detectado (Modo Rescate)...")
                start_idx = raw_text.lower().find("<html")
                if start_idx == -1:
                    start_idx = raw_text.lower().find("<!doctype")
                end_idx = raw_text.lower().rfind("</html>")
                
                if start_idx != -1 and end_idx != -1:
                    content = raw_text[start_idx:end_idx + 7]
                    filename = "index.html"
                    full_path = os.path.join(self.project_path, filename)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content.strip())
                    self.gui.log_to_terminal(f"> Creado: {filename} (vía modo rescate)")
                    
                    structure = {filename: "file"}
                    self.gui.update_file_tree(structure)
                    if os.path.exists(full_path):
                        self.gui.current_open_file = filename
                        self.gui.update_code_viewer(filename, content.strip())
                    return

            # Fallback 3: Volcar el texto bruto como respuesta ya que todo lo demás falló
            self.gui.log_to_terminal("> ⚠️ Error de formato: La IA respondió en texto plano o con un error.")
            
            try:
                debug_path = os.path.join(self.project_path, "respuesta_ia_bruta.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
                self.gui.log_to_terminal(f"> 📝 El texto bruto de la IA se ha guardado en {debug_path}.")
                
                # Actualizar GUI para mostrar la respuesta bruta
                structure = {"respuesta_ia_bruta.txt": "file"}
                self.gui.update_file_tree(structure)
                if os.path.exists(debug_path):
                    self.gui.current_open_file = "respuesta_ia_bruta.txt"
                    self.gui.update_code_viewer("respuesta_ia_bruta.txt", raw_text)
            except Exception as e:
                self.gui.log_to_terminal(f"> No se pudo guardar el texto bruto: {str(e)}")
            return

        structure = {}
        first_file_name = None
        first_file_content = None
        
        for match in matches:
            filename = match.group(1).strip()
            content = match.group(2).strip()
            
            # Evitar saltos de ruta peligrosos
            if ".." in filename:
                continue

            full_path = os.path.join(self.project_path, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.gui.log_to_terminal(f"> Creado: {filename}")
            
            # Construcción del árbol para el mini-explorador
            parts = filename.replace("\\", "/").split('/')
            current = structure
            for p in parts[:-1]:
                if p not in current:
                    current[p] = {}
                current = current[p]
            current[parts[-1]] = "file"
            
            if not first_file_name:
                first_file_name = filename
                first_file_content = content
                
        # Actualizar la interfaz
        self.gui.update_file_tree(structure)
        if first_file_name:
            self.gui.update_code_viewer(first_file_name, first_file_content)


if __name__ == "__main__":
    app = JarvisDeveloperGUI()
    builder = ProjectBuilder(app)
    app.builder = builder  # Para que el STOP y send_message funcionen
    
    # Conectar la interfaz al orquestador IA
    app.on_new_project = lambda folder: builder.start_project(os.path.basename(folder), folder)
    app.on_open_project = lambda folder: builder.load_existing_project(folder)
    
    app.mainloop()