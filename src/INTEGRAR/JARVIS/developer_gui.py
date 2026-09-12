import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
import subprocess
import threading
import json
try:
    from tkinterweb import HtmlFrame
except ImportError:
    HtmlFrame = None

# Configuración base del tema
ctk.set_appearance_mode("Dark")  # Modos: "System" (estándar), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Temas: "blue" (estándar), "green", "dark-blue"

class JarvisDeveloperGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Ocultar la consola de Windows en segundo plano
        if os.name == 'nt':
            import ctypes
            hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd_console:
                ctypes.windll.user32.ShowWindow(hwnd_console, 0)

        self.title("Jarvis Developer UI")
        self.geometry("1400x900")
        self.minsize(800, 600)
        
        # === LAYOUT PRINCIPAL ===
        self.grid_columnconfigure(0, weight=1) # Panel de chat (se expande por defecto)
        self.grid_columnconfigure(1, weight=0) # Panel de desarrollo (contraído por defecto)
        self.grid_rowconfigure(0, weight=1)
        
        self.current_project_path = ""
        self.current_open_file = None
        self.dev_panel_visible = False
        
        self.recent_projects_file = "recent_projects.json"
        self.recent_projects = self._load_recent_projects()

        self._build_chat_panel()
        self._build_dev_panel()
        
        # Ocultar el panel de desarrollo al inicio
        self.dev_frame.grid_remove()

    def _build_chat_panel(self):
        # --- PANEL IZQUIERDO: CHAT ---
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        
        # Encabezado del Chat (Selector de Modelo)
        self.chat_header = ctk.CTkFrame(self.chat_frame, height=50, fg_color="transparent")
        self.chat_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.header_label = ctk.CTkLabel(self.chat_header, text="Jarvis Assistant", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(side="left")

        # Crédito Tech en Clair
        self.credit_label = ctk.CTkLabel(self.chat_header, text="creado por www.techenclair.fr - Proyecto OpenSource (Prohibida su reventa)", font=ctk.CTkFont(size=12, slant="italic"), text_color="#7f8c8d")
        self.credit_label.pack(side="left", padx=(15, 0), pady=(4, 0))

        # Selector visual de Modelo
        self.model_var = ctk.StringVar(value="Gemini 2.5 Flash")
        self.model_selector = ctk.CTkOptionMenu(
            self.chat_header, 
            values=["Gemini 3.5 Flash", "Gemini 3.1 Pro", "Gemini 2.5 Flash", "Gemini 2.5 Pro", "Claude 5 Sonnet", "Claude 5 Fable", "Claude 4.8 Opus", "Grok 4.5", "Grok 4.20", "Mistral Large", "Codestral", "Ornith-1.0 (Local)", "Ornith-35b (Local)", "Qwen2.5-Coder (Local)", "DeepSeek-Coder (Local)"],
            variable=self.model_var,
            command=self.on_model_change
        )
        self.model_selector.pack(side="right")
        
        self.model_label = ctk.CTkLabel(self.chat_header, text="Modelo:")
        self.model_label.pack(side="right", padx=10)

        # Selector de Motor de Imágenes
        self.image_model_var = ctk.StringVar(value="Imágenes: Auto")
        self.image_model_selector = ctk.CTkOptionMenu(
            self.chat_header,
            values=["Imágenes: Auto", "Imágenes: Pollinations", "Imágenes: Gemini", "Imágenes: Grok"],
            variable=self.image_model_var,
            width=160,
            fg_color="#2c3e50",
            button_color="#34495e",
            button_hover_color="#2c3e50"
        )
        self.image_model_selector.pack(side="right", padx=(0, 10))
        
        # Checkbox "Prompt Auto"
        self.enrich_prompt_var = ctk.BooleanVar(value=True)
        self.enrich_prompt_checkbox = ctk.CTkCheckBox(
            self.chat_header,
            text="Prompt Auto",
            variable=self.enrich_prompt_var,
            font=ctk.CTkFont(size=12)
        )
        self.enrich_prompt_checkbox.pack(side="right", padx=(0, 15))

        # Historial del Chat
        self.chat_history = ctk.CTkTextbox(self.chat_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_history.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.chat_history.insert("0.0", "Jarvis: ¡Hola! Estoy listo. ¿Qué desea desarrollar hoy?\n\n")
        self.chat_history.configure(state="disabled")
        
        # Zona de entrada
        self.chat_input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.chat_input_frame.grid(row=2, column=0, sticky="ew")
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        
        self.attached_image_path = None
        self.attachment_label = ctk.CTkLabel(self.chat_input_frame, text="", text_color="#f39c12", font=ctk.CTkFont(size=12, slant="italic"))
        self.attachment_label.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
        
        self.chat_input = ctk.CTkTextbox(self.chat_input_frame, height=80, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_input.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        # Manejo de la pulsación de Enter para enviar (sin salto de línea)
        def _on_enter(event):
            self.send_message()
            return "break"
            
        self.chat_input.bind("<Return>", _on_enter)
        # Shift+Enter hará un salto de línea real por defecto
        self.chat_input.bind("<Shift-Return>", lambda e: None)
        
        self.attach_button = ctk.CTkButton(self.chat_input_frame, text="📎", width=40, height=40, fg_color="#34495e", hover_color="#2c3e50", command=self.attach_image)
        self.attach_button.grid(row=1, column=1, padx=(0, 10))
        
        self.send_button = ctk.CTkButton(self.chat_input_frame, text="Enviar", width=90, height=40, command=self.send_message)
        self.send_button.grid(row=1, column=2)
        
        self.stop_button = ctk.CTkButton(self.chat_input_frame, text="🛑 STOP", width=90, height=40, fg_color="#e74c3c", hover_color="#c0392b", command=self.on_stop_clicked)
        self.stop_button.grid(row=1, column=3, padx=(10, 0))
        self.stop_button.configure(state="disabled") # Desactivado por defecto

        self.new_proj_button = ctk.CTkButton(self.chat_input_frame, text="Crear Proyecto...", width=120, height=40, fg_color="#27ae60", hover_color="#2ecc71", command=self.ask_new_project_directory)
        self.new_proj_button.grid(row=1, column=4, padx=(10, 5))
        
        self.recent_menu = ctk.CTkOptionMenu(
            self.chat_input_frame, 
            values=["Ningún proyecto"], 
            width=130, 
            height=40, 
            command=self.on_recent_selected
        )
        self.recent_menu.grid(row=1, column=5, padx=(5, 0))
        self.recent_menu.set("Recientes...")
        self._update_recent_menu()

    def attach_image(self):
        file_path = ctk.filedialog.askopenfilename(
            title="Adjuntar una imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp")]
        )
        if file_path:
            self.attached_image_path = file_path
            filename = os.path.basename(file_path)
            self.attachment_label.configure(text=f"📎 Imagen adjunta: {filename}")

    def on_stop_clicked(self):
        if hasattr(self, 'builder') and self.builder:
            self.builder.cancel_generation()
            self.log_chat("Cancelación solicitada...", sender="Sistema")

    def send_message(self):
        try:
            with open("DEBUG_ALIVE.txt", "a") as f: f.write("send_message ha comenzado!\n")
        except: pass
        
        try:
            msg = self.chat_input.get("1.0", "end-1c")
            if not msg.strip(): return
            
            self.log_chat(msg, sender="Usted")
            self.chat_input.delete("1.0", "end")
            
            img_path = getattr(self, 'attached_image_path', None)
            self.attached_image_path = None
            if hasattr(self, 'attachment_label'): self.attachment_label.configure(text="")
            
            if hasattr(self, 'stop_button'): self.stop_button.configure(state="normal")
            
            if hasattr(self, 'builder') and self.builder:
                self.builder.handle_message(msg, img_path)
            else:
                self.log_chat(f"Error interno: 'builder' falta o es inválido. (hasattr={hasattr(self, 'builder')})", sender="Error")
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            try:
                self.log_chat(f"CRASH COMPLETO en send_message:\n{err}", sender="Error Crítico")
            except:
                with open("CRASH_LOG.txt", "w") as f:
                    f.write(err)

    def _load_recent_projects(self):
        if os.path.exists(self.recent_projects_file):
            try:
                with open(self.recent_projects_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_recent_project(self, path):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10] # Guarda los 10 últimos
        try:
            with open(self.recent_projects_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_projects, f)
        except:
            pass
        self._update_recent_menu()
        
    def _update_recent_menu(self):
        if hasattr(self, 'recent_menu'):
            if self.recent_projects:
                names = [os.path.basename(p) for p in self.recent_projects if os.path.exists(p)]
                if names:
                    self.recent_menu.configure(values=names)
                else:
                    self.recent_menu.configure(values=["Ningún proyecto"])
            else:
                self.recent_menu.configure(values=["Ningún proyecto"])
            self.recent_menu.set("Recientes...")

    def on_recent_selected(self, choice):
        if choice == "Ningún proyecto" or choice == "Recientes...":
            return
        # Encontrar la ruta completa
        path = next((p for p in self.recent_projects if os.path.basename(p) == choice), None)
        if path and os.path.exists(path):
            self._save_recent_project(path)
            self.log_chat(f"Abriendo proyecto existente: {path}", sender="Usted")
            if hasattr(self, 'on_open_project'):
                self.on_open_project(path)
        else:
            self.log_chat(f"La carpeta del proyecto parece no existir o ha sido eliminada.", sender="Sistema")

    def ask_new_project_directory(self):
        folder_selected = ctk.filedialog.askdirectory(title="Elegir la carpeta del nuevo proyecto")
        if folder_selected:
            self._save_recent_project(folder_selected)
            self.log_chat(f"Creando proyecto en: {folder_selected}", sender="Usted")
            if hasattr(self, 'on_new_project'):
                self.on_new_project(folder_selected)
            else:
                self.log_chat("La función de creación no está conectada.", sender="Sistema")

    def _build_dev_panel(self):
        # --- PANEL DERECHO: DEV PANEL ---
        self.dev_frame = ctk.CTkFrame(self, width=700, corner_radius=10)
        self.dev_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        
        # Configuración de filas del Panel de Desarrollo
        self.dev_frame.grid_columnconfigure(0, weight=1)
        self.dev_frame.grid_rowconfigure(1, weight=1) # Zona explorador + código (ocupa todo el espacio)
        
        # 1. Encabezado del Panel de Desarrollo (Estado y Acciones)
        self.dev_header = ctk.CTkFrame(self.dev_frame, height=50, fg_color="transparent")
        self.dev_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Indicador de estado
        self.status_indicator = ctk.CTkLabel(
            self.dev_header, 
            text="🟢 Listo", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2ecc71"
        )
        self.status_indicator.pack(side="left", padx=10)
        
        # Barra de progreso animada
        self.progress_bar = ctk.CTkProgressBar(self.dev_header, mode="indeterminate", width=150)
        # No mostrada por defecto
        
        # Botones de acción rápida
        self.btn_vscode = ctk.CTkButton(self.dev_header, text="Abrir en VS Code", width=140, command=self.open_in_vscode)
        self.btn_vscode.pack(side="right", padx=5)
        
        self.btn_folder = ctk.CTkButton(self.dev_header, text="Abrir Carpeta", width=120, command=self.open_folder)
        self.btn_folder.pack(side="right", padx=5)
        
        # 2. Zona Central: Explorador y Visor de Código
        self.dev_main_split = ctk.CTkFrame(self.dev_frame, fg_color="transparent")
        self.dev_main_split.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.dev_main_split.grid_columnconfigure(0, weight=1) # Explorador (estrecho)
        self.dev_main_split.grid_columnconfigure(1, weight=4) # Visor de Código (ancho)
        self.dev_main_split.grid_rowconfigure(0, weight=1)
        
        # Mini-Explorador
        self.explorer_frame = ctk.CTkFrame(self.dev_main_split, corner_radius=5)
        self.explorer_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        self.explorer_label = ctk.CTkLabel(self.explorer_frame, text="Archivos", font=ctk.CTkFont(weight="bold"))
        self.explorer_label.pack(pady=5, padx=10, anchor="w")
        
        # Estilo para el Treeview (Tkinter clásico integrado en CustomTkinter)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0, font=("Segoe UI", 11))
        style.map('Treeview', background=[('selected', '#1f538d')])
        
        self.file_tree = ttk.Treeview(self.explorer_frame, show="tree")
        self.file_tree.pack(expand=True, fill="both", padx=5, pady=5)
        self.file_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # Visor de Código y Vista Previa con pestañas
        self.tabs = ctk.CTkTabview(self.dev_main_split, corner_radius=5)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        self.tab_code = self.tabs.add("Código")
        self.tab_preview = self.tabs.add("Vista Visual")
        
        # Zona Código
        self.tab_code.grid_columnconfigure(0, weight=1)
        self.tab_code.grid_rowconfigure(1, weight=1)
        
        self.save_btn = ctk.CTkButton(self.tab_code, text="💾 Guardar", fg_color="#27ae60", hover_color="#2ecc71", command=self.save_current_code)
        self.save_btn.grid(row=0, column=0, pady=(5, 0), sticky="e", padx=5)
        
        self.code_viewer = ctk.CTkTextbox(self.tab_code, font=ctk.CTkFont(family="Consolas", size=13), wrap="none")
        self.code_viewer.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Zona Vista Visual
        self.tab_preview.grid_columnconfigure(0, weight=1)
        self.tab_preview.grid_rowconfigure(1, weight=1)
        
        self.browser_btn = ctk.CTkButton(self.tab_preview, text="🌐 Abrir en mi Navegador Real (Recomendado)", fg_color="#e67e22", hover_color="#d35400", command=self.open_in_browser)
        self.browser_btn.grid(row=0, column=0, pady=(5, 5), sticky="ew", padx=10)
        
        if HtmlFrame:
            self.web_preview = HtmlFrame(self.tab_preview)
            self.web_preview.grid(row=1, column=0, sticky="nsew")
        else:
            lbl = ctk.CTkLabel(self.tab_preview, text="tkinterweb no está instalado.")
            lbl.grid(row=1, column=0, sticky="nsew")



    def on_model_change(self, choice):
        self.log_chat(f"Modelo cambiado a: {choice}", sender="Sistema")
        
        if "(Local)" in choice:
            from local_agent_manager import JarvisLocalAgentManager
            
            # Mapeo entre el nombre de visualización y la etiqueta exacta de Ollama
            ollama_tags = {
                "Ornith-1.0 (Local)": "ornith:9b",
                "Ornith-35b (Local)": "ornith:35b",
                "Qwen2.5-Coder (Local)": "qwen2.5-coder:7b",
                "DeepSeek-Coder (Local)": "deepseek-coder-v2"
            }
            
            target_model = ollama_tags.get(choice, "ornith:9b")
            agent = JarvisLocalAgentManager(model_name=target_model)
            
            is_ready, status = agent.check_system()
            if not is_ready:
                self._show_ollama_onboarding(agent, status)

    def _show_ollama_onboarding(self, agent, status):
        onboarding_win = ctk.CTkToplevel(self)
        onboarding_win.title("Agente Local No Detectado")
        onboarding_win.geometry("600x400")
        onboarding_win.attributes("-topmost", True)
        onboarding_win.grab_set() 
        
        lbl_title = ctk.CTkLabel(onboarding_win, text="🤖 Instalación del Agente Local", font=ctk.CTkFont(size=20, weight="bold"))
        lbl_title.pack(pady=(20, 10))
        
        info_text = "El agente local 100% privado y gratuito requiere Ollama.\n\n"
        if status == "OLLAMA_NOT_RUNNING":
            info_text += "❌ Ollama no está instalado o no está en ejecución.\n\n"
            info_text += "Paso 1: Descargue e instale Ollama en su PC.\n"
            info_text += "Paso 2: Ejecute la aplicación Ollama en segundo plano.\n"
            info_text += f"Paso 3: Vuelva aquí y seleccione nuevamente el modelo."
        else:
            info_text += f"❌ El modelo requerido ({agent.model}) aún no está descargado.\n\n"
            info_text += "¡Tiene Ollama! Solo necesita descargar el modelo (~5.6 GB).\n"
            info_text += f"¿Desea que JARVIS descargue el modelo por usted?"
            
        lbl_info = ctk.CTkLabel(onboarding_win, text=info_text, justify="left", font=ctk.CTkFont(size=14))
        lbl_info.pack(padx=20, pady=20)
        
        btn_frame = ctk.CTkFrame(onboarding_win, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        if status == "OLLAMA_NOT_RUNNING":
            def open_website():
                import webbrowser
                webbrowser.open("https://ollama.com/download")
            btn_web = ctk.CTkButton(btn_frame, text="Descargar Ollama", command=open_website)
            btn_web.pack(side="left", padx=10)
        else:
            def auto_install():
                self.log_chat(f"Iniciando la descarga de {agent.model}... Por favor, espere.", sender="Sistema")
                onboarding_win.destroy()
                import threading
                import requests
                import json
                
                def pull_task():
                    try:
                        self.update_status("Descargando...", color="#f39c12", loading=True)
                        response = requests.post(
                            "http://127.0.0.1:11434/api/pull", 
                            json={"name": agent.model},
                            stream=True
                        )
                        
                        last_progress = -1
                        for line in response.iter_lines():
                            if line:
                                data = json.loads(line.decode('utf-8'))
                                if 'completed' in data and 'total' in data and data['total'] > 0:
                                    percent = int((data['completed'] / data['total']) * 100)
                                    if percent % 10 == 0 and percent != last_progress:
                                        # Usar after para actualizar la GUI desde el hilo de forma segura
                                        self.after(0, lambda p=percent: self.log_chat(f"⏳ Descarga: {p}%", sender="Sistema"))
                                        last_progress = percent
                        
                        self.after(0, lambda: self.log_chat(f"✅ Modelo {agent.model} descargado con éxito. ¡Ya puede usarlo!", sender="Sistema"))
                    except Exception as e:
                        self.after(0, lambda err=e: self.log_chat(f"❌ Error inesperado: {err}", sender="Sistema"))
                    finally:
                        self.after(0, lambda: self.update_status("Listo", color="white", loading=False))
                        
                threading.Thread(target=pull_task, daemon=True).start()
                
            btn_install = ctk.CTkButton(btn_frame, text="Descargar el modelo automáticamente", command=auto_install, fg_color="#27ae60", hover_color="#2ecc71")
            btn_install.pack(side="left", padx=10)
            
        btn_close = ctk.CTkButton(btn_frame, text="Cerrar", command=onboarding_win.destroy, fg_color="#e74c3c", hover_color="#c0392b")
        btn_close.pack(side="left", padx=10)

    def update_status(self, text, color="white", loading=False):
        def _do_update():
            if hasattr(self, 'status_indicator'):
                self.status_indicator.configure(text=text, text_color=color)
                
            if hasattr(self, 'progress_bar'):
                if loading:
                    self.progress_bar.pack(side="left", padx=10)
                    self.progress_bar.start()
                else:
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
        self.after(0, _do_update)

    def log_to_terminal(self, message):
        def _do_log():
            self.chat_history.configure(state="normal")
            self.chat_history.insert("end", f"> 💻 Terminal: {message}\n\n")
            self.chat_history.see("end")
            self.chat_history.configure(state="disabled")
        self.after(0, _do_log)

    def log_chat(self, text, sender="Jarvis"):
        def _do_chat():
            self.chat_history.configure(state="normal")
            self.chat_history.insert("end", f"{sender}: {text}\n\n")
            self.chat_history.configure(state="disabled")
            self.chat_history.see("end")
        self.after(0, _do_chat)

    # === FUNCIONES PARA EL ORQUESTADOR (Project Builder) ===

    def show_dev_panel(self):
        if not self.dev_panel_visible:
            self.dev_frame.grid()
            # Redimensionar los pesos para que ambas columnas se muestren bien
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            self.dev_panel_visible = True

    def hide_dev_panel(self):
        if self.dev_panel_visible:
            self.dev_frame.grid_remove()
            self.grid_columnconfigure(1, weight=0)
            self.dev_panel_visible = False



    def update_code_viewer(self, filename, code_content):
        """Actualiza la zona de código central y el navegador si es web."""
        self.current_open_file = filename
        self.tabs.set("Código")
        self.code_viewer.delete("0.0", "end")
        self.code_viewer.insert("0.0", code_content)
        
        # Actualizar la vista previa si es un archivo web
        if filename.endswith(".html"):
            if hasattr(self, 'web_preview') and HtmlFrame:
                full_path = os.path.join(self.current_project_path, filename)
                if os.path.exists(full_path):
                    try:
                        base_uri = f"file:///{self.current_project_path.replace(os.sep, '/')}/"
                        self.web_preview.load_html(code_content, base_url=base_uri)
                    except:
                        self.web_preview.load_file(f"file:///{full_path.replace(os.sep, '/')}")
                    self.tabs.set("Vista Visual")
            
            self.browser_btn.configure(text="🌐 Abrir en mi Navegador Real (Recomendado)", command=self.open_in_browser)
            if hasattr(self, 'python_warning_lbl'): self.python_warning_lbl.grid_remove()
            if hasattr(self, 'web_preview'): self.web_preview.grid(row=1, column=0, sticky="nsew")
            
        elif filename.endswith(".py"):
            full_path = os.path.join(self.current_project_path, filename)
            self.browser_btn.configure(text="🚀 Ejecutar este Script Python", command=lambda p=full_path: self.run_python_script(p))
            
            if hasattr(self, 'web_preview'): self.web_preview.grid_remove()
            if not hasattr(self, 'python_warning_lbl'):
                self.python_warning_lbl = ctk.CTkLabel(self.tab_preview, text="")
            self.python_warning_lbl.configure(text="Vista visual no disponible para scripts Python.\nHaga clic en el botón de arriba para ejecutarlo.")
            self.python_warning_lbl.grid(row=1, column=0, sticky="nsew")
            
        else:
            self.browser_btn.configure(text="📁 Abrir la carpeta del proyecto", command=self.open_folder)
            
            if hasattr(self, 'web_preview'): self.web_preview.grid_remove()
            if not hasattr(self, 'python_warning_lbl'):
                self.python_warning_lbl = ctk.CTkLabel(self.tab_preview, text="")
            self.python_warning_lbl.configure(text="Vista visual no disponible para este tipo de archivo.")
            self.python_warning_lbl.grid(row=1, column=0, sticky="nsew")

    def set_project_path(self, path):
        """Define la carpeta raíz del proyecto actual."""
        self.current_project_path = path

    def update_file_tree(self, structure_dict, parent=""):
        """
        Actualiza el árbol de archivos.
        Ejemplo de structure_dict: {'src': {'main.py': 'file'}, 'README.md': 'file'}
        """
        if parent == "":
            self.file_tree.delete(*self.file_tree.get_children())
            
        for name, content in structure_dict.items():
            node = self.file_tree.insert(parent, "end", text=name, open=True)
            if isinstance(content, dict):
                self.update_file_tree(content, node)

    def on_tree_double_click(self, event):
        item_id = self.file_tree.selection()
        if not item_id:
            return
        
        # Reconstruir la ruta
        item = item_id[0]
        path_parts = [self.file_tree.item(item, "text")]
        parent = self.file_tree.parent(item)
        while parent:
            path_parts.insert(0, self.file_tree.item(parent, "text"))
            parent = self.file_tree.parent(parent)
            
        rel_path = "/".join(path_parts)
        full_path = os.path.join(self.current_project_path, rel_path)
        
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.update_code_viewer(rel_path, content)
            except Exception as e:
                self.log_to_terminal(f"No se pudo abrir el archivo: {e}")

    def save_current_code(self):
        if not self.current_open_file or not self.current_project_path:
            return
        full_path = os.path.join(self.current_project_path, self.current_open_file)
        try:
            content = self.code_viewer.get("0.0", "end-1c")
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log_to_terminal(f"> Archivo guardado: {self.current_open_file}")
            # Si es un archivo web, recargar la vista previa
            if self.current_open_file.endswith(".html") and hasattr(self, 'web_preview'):
                try:
                    self.web_preview.load_html(content)
                except:
                    self.web_preview.load_file(f"file:///{full_path.replace(os.sep, '/')}")
        except Exception as e:
            self.log_to_terminal(f"Error al guardar: {e}")

    # === ACCIONES RÁPIDAS ===

    def open_in_browser(self):
        import webbrowser
        if self.current_project_path:
            index_path = os.path.join(self.current_project_path, "index.html")
            if os.path.exists(index_path):
                webbrowser.open("file://" + index_path)
            else:
                self.log_to_terminal("Error: no se encontró index.html para el navegador.")

    def run_python_script(self, filepath):
        import subprocess
        import threading
        import sys
        
        self.log_to_terminal(f"> Lanzando el script: {filepath} ...")
        
        def run_thread():
            try:
                # Usar sys.executable para usar el Python actual (con todas las dependencias de Jarvis)
                process = subprocess.Popen([sys.executable, filepath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=os.path.dirname(filepath))
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.log_to_terminal(f"[Script] {line.strip()}")
                process.stdout.close()
                process.wait()
                self.log_to_terminal(f"> Script terminado (Código de retorno: {process.returncode})")
            except Exception as e:
                self.log_to_terminal(f"> Error al ejecutar: {e}")
                
        threading.Thread(target=run_thread, daemon=True).start()

    def open_folder(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            self.log_to_terminal("Error: Carpeta del proyecto no definida o no encontrada.")
            return
        
        if os.name == 'nt': # Windows
            os.startfile(self.current_project_path)
        elif os.name == 'posix': # Mac/Linux
            subprocess.call(('open', self.current_project_path))

    def open_in_vscode(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            self.log_to_terminal("Error: Carpeta del proyecto no definida o no encontrada.")
            return
        
        try:
            subprocess.Popen(["code", self.current_project_path], shell=True)
            self.log_to_terminal("> Abriendo VS Code...")
        except Exception as e:
            self.log_to_terminal(f"> Error al abrir VS Code: {e}")

if __name__ == "__main__":
    app = JarvisDeveloperGUI()
    app.mainloop()