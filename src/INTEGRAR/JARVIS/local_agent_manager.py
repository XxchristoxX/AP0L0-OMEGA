import os
import re
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any
from openai import OpenAI

class JarvisLocalAgentManager:
    """
    Gestor para el agente local basado en el modelo Ornith (mediante Ollama).
    Permite una integración opcional (opt-in), privada y gratuita en JARVIS.
    """

    def __init__(self, model_name=None):
        # Configuración dinámica mediante variables de entorno o parámetro
        self.base_url: str = os.environ.get("JARVIS_OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model: str = model_name if model_name else os.environ.get("JARVIS_OLLAMA_MODEL", "ornith:9b")
        
        # Inicialización del cliente OpenAI (100% compatible con la API v1 de Ollama)
        # Se requiere una clave API ficticia para el SDK. Se pone un timeout largo (5 minutos) para modelos locales lentos.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama-local",
            timeout=300.0
        )

    def _obtener_url_tags_ollama(self) -> str:
        """Construye la URL de diagnóstico nativa de Ollama a partir de la base_url de OpenAI."""
        parsed = urlparse(self.base_url)
        # La API nativa de Ollama para listar modelos siempre está en /api/tags
        return f"{parsed.scheme}://{parsed.netloc}/api/tags"

    def check_system(self) -> Tuple[bool, str]:
        """
        Verifica rápidamente si Ollama está en ejecución y si el modelo requerido está descargado.
        Devuelve una tupla (Está_Listo, Código_Error).
        """
        api_url = self._obtener_url_tags_ollama()
        
        try:
            # Timeout corto para no bloquear la interfaz de usuario
            response = requests.get(api_url, timeout=3.0)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            # El servidor Ollama no responde (no iniciado o no instalado)
            return False, "OLLAMA_NOT_RUNNING"
            
        try:
            data = response.json()
            # Obtener la lista de nombres de modelos instalados (ej: ['ornith:9b', 'deepseek-coder-v2:latest'])
            modelos = [m.get("name") for m in data.get("models", [])]
            
            # Ollama suele añadir el tag ':latest' si no se especifica (ej: deepseek-coder-v2 -> deepseek-coder-v2:latest)
            modelo_encontrado = False
            for m in modelos:
                if m == self.model or m == f"{self.model}:latest" or self.model == m + ":latest":
                    modelo_encontrado = True
                    break
            
            if not modelo_encontrado:
                return False, "MODEL_NOT_PULLED"
                
        except ValueError:
            return False, "INVALID_RESPONSE"
            
        return True, "OK"

    def mostrar_onboarding(self, status: str) -> None:
        """
        Muestra una pantalla de onboarding textual pedagógica si el diagnóstico falla.
        """
        print("\n" + "="*70)
        print(" 🤖 INICIALIZACIÓN DEL AGENTE LOCAL (ORNITH-1.0) ".center(70, "="))
        print("="*70)
        
        if status == "OLLAMA_NOT_RUNNING":
            print("\n ❌ Ollama no parece estar iniciado o instalado en esta máquina.")
        elif status == "MODEL_NOT_PULLED":
            print(f"\n ❌ El modelo '{self.model}' aún no está descargado en su máquina.")
        else:
            print("\n ❌ Se ha producido un error desconocido con el servicio local.")
            
        print("\n 💡 ¿Por qué usar este agente local opcional?")
        print("    • 100% Privado : Todos sus datos y cálculos permanecen en su máquina.")
        print("    • 100% Gratuito: No se necesita clave API, ni suscripción.")
        print("    • Autónomo    : La IA usa su tarjeta gráfica o su procesador.")
        
        print(f"\n 📦 Espacio requerido: ~5.6 GB para la versión recomendada ({self.model}).")
        
        print("\n 🚀 GUÍA DE INSTALACIÓN PASO A PASO:")
        print("    1. Vaya a https://ollama.com y descargue Ollama para su sistema.")
        print("    2. Instale y ejecute la aplicación Ollama en segundo plano.")
        print("    3. Abra un nuevo terminal (o símbolo del sistema) y escriba exactamente:")
        print(f"       > ollama pull {self.model}")
        print("    4. Espere mientras se descarga el modelo.")
        print("    5. Reinicie JARVIS. ¡Ya está!")
        print("\n" + "="*70 + "\n")

    def limpiar_pensamiento(self, text: str, eliminar_reflexion: bool = True) -> str:
        """
        Limpia la salida para extraer o eliminar la reflexión de la IA (etiquetas <think>).
        """
        if not text:
            return ""
            
        if eliminar_reflexion:
            # Elimina el bloque completo <think> ... </think> y los saltos de línea alrededor
            limpiado = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
            
            # Seguridad: Si la IA se cortó antes de la etiqueta de cierre o se olvidó de ponerla,
            # se elimina solo la etiqueta <think> de apertura para no borrar todo el código HTML que sigue.
            limpiado = limpiado.replace("<think>", "").replace("</think>", "")
            
            return limpiado.strip()
            
        return text.strip()

    def generate_response(self, messages: List[Dict[str, str]], eliminar_reflexion: bool = True) -> Optional[str]:
        """
        Llama al agente local con el historial de mensajes.
        Usa parámetros óptimos para la reflexión de la IA.
        """
        # 1. Verificación silenciosa (fail-fast)
        ok, status = self.check_system()
        if not ok:
            self.mostrar_onboarding(status)
            return None
            
        try:
            # 2. Llamada a la API nativa de Ollama (para poder forzar el tamaño del contexto 'num_ctx')
            # La API de OpenAI por defecto no permite cambiar num_ctx fácilmente, ¡limitando a 2048 tokens!
            from urllib.parse import urlparse
            import requests
            
            parsed = urlparse(self.base_url)
            api_url = f"{parsed.scheme}://{parsed.netloc}/api/chat"
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "num_predict": -1,     # -1 = Sin límite estricto, genera hasta terminar (o hasta num_ctx)
                    "num_ctx": 32768       # Contexto gigante para prompts grandes y código largo
                }
            }
            
            # Timeout infinito (None) porque un modelo grande (ej: 35b) generando 10000 tokens puede tardar 10-20 minutos en un PC normal.
            response = requests.post(api_url, json=payload, timeout=None)
            response.raise_for_status()
            
            data = response.json()
            texto_bruto = data.get("message", {}).get("content", "")
            
            # 3. Tratamiento de la reflexión
            return self.limpiar_pensamiento(texto_bruto, eliminar_reflexion=eliminar_reflexion)
            
        except Exception as e:
            # Propagar el error para que la interfaz gráfica (project_builder) pueda mostrarlo
            raise Exception(f"Error con el agente local: {str(e)}")


# ==============================================================================
# EJEMPLO DE INTEGRACIÓN EN EL BUCLE PRINCIPAL DE JARVIS (FALSO MENÚ TERMINAL)
# ==============================================================================
if __name__ == "__main__":
    import time

    def bucle_principal_jarvis():
        print("="*50)
        print(" 🧠 JARVIS DEVELOPER OS - Menú Principal")
        print("="*50)
        print(" [1] Hablar con el agente en la nube (OpenAI/Gemini)")
        print(" [2] Hablar con el agente local (Ornith-1.0)")
        print(" [3] Salir")
        
        opcion = input("\n Seleccione una opción: ").strip()
        
        if opcion == "2":
            # Inicialización (ligera, no bloquea si no se usa)
            agente_local = JarvisLocalAgentManager()
            
            print("\n[Sistema] Verificando requisitos previos locales...")
            time.sleep(0.5) # Simula una pequeña carga
            
            # Verifica y bloquea si el sistema no está listo
            listo, status = agente_local.check_system()
            if not listo:
                agente_local.mostrar_onboarding(status)
                return # Vuelve al menú o sale
                
            print("✅ Agente local listo. Puede hablar (escriba 'exit' para salir).")
            
            # Bucle de chat
            messages = [{"role": "system", "content": "Eres JARVIS, un asistente IA experto."}]
            
            while True:
                entrada_usuario = input("\nUsted: ").strip()
                if entrada_usuario.lower() == 'exit':
                    break
                if not entrada_usuario:
                    continue
                    
                messages.append({"role": "user", "content": entrada_usuario})
                print("\nJARVIS está reflexionando (local)... ⏳")
                
                # Generación de la respuesta (eliminar_reflexion=True por defecto para no saturar la UX)
                texto_respuesta = agente_local.generate_response(messages, eliminar_reflexion=True)
                
                if texto_respuesta:
                    print(f"\nJARVIS (Ornith) : {texto_respuesta}")
                    messages.append({"role": "assistant", "content": texto_respuesta})
                else:
                    # La pantalla de error ya se ha mostrado por generate_response si es necesario
                    break

    bucle_principal_jarvis()