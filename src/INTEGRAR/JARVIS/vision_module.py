import os
import base64
import time
try:
    import pyautogui
except ImportError:
    pyautogui = None
try:
    import cv2
except ImportError:
    cv2 = None
import asyncio
import json
try:
    import requests
except ImportError:
    requests = None
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def jarvis_vision_clicar(instruccion):
    try:
        # Esperar un poco para que la UI esté estable
        time.sleep(0.5)
        ruta_ss = "jarvis_vision_temp.png"
        captura = pyautogui.screenshot()
        captura.save(ruta_ss)
        img_w, img_h = captura.size  # Dimensiones reales de la captura de pantalla
        from PIL import Image
        img = Image.open(ruta_ss)
        prompt_vision = (
            f"Eres el ojo de JARVIS. Aquí tienes una captura de la pantalla de Christopher ({img_w}x{img_h} píxeles).\n"
            f"Instrucción: {instruccion}\n"
            "Encuentra el elemento solicitado (botón, texto, icono o número en una lista) en la pantalla.\n"
            "Si la instrucción menciona un número (ej: 'música número 4'), busca ese número o la pista correspondiente en la lista.\n"
            "Responde ÚNICAMENTE en JSON con este formato:\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"descripción corta del elemento\"}\n"
            "Las coordenadas están normalizadas de 0 a 1000 (0=esquina superior izquierda, 1000=esquina inferior derecha)."
        )
        import builtins
        client = builtins.client
        model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        response = client.models.generate_content(model=model_name, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        print(f"[VISION] Gemini ha devuelto: {rep_text}")
        inicio = rep_text.find('{')
        fin = rep_text.rfind('}')
        if inicio != -1 and fin != -1:
            rep_text = rep_text[inicio:fin+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        # Centro de la bounding box, convertido a píxeles reales mediante las dimensiones de la captura
        centro_y = (ymin + ymax) / 2
        centro_x = (xmin + xmax) / 2
        target_x = int((centro_x / 1000) * img_w)
        target_y = int((centro_y / 1000) * img_h)
        
        print(f"[VISION] Objetivo identificado: {data.get('description', 'desconocido')} en ({target_x}, {target_y})")

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.2)
        
        # DOBLE CLIC si es una música o un número para asegurar la reproducción
        t_inst = instruccion.lower()
        if any(palabra in t_inst for palabra in ["musica", "cancion", "pista", "numero", "número", "tema"]):
            print(f"[VISION] Doble clic en el elemento de lista: {target_x}, {target_y}")
            pyautogui.doubleClick()
        else:
            pyautogui.click()

        if os.path.exists(ruta_ss):
            os.remove(ruta_ss)
        desc = data.get("description", instruccion)
        return f"Hecho Christopher, he hecho clic en: {desc}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "Veo la interfaz, pero no he podido identificar el elemento preciso, Christopher."

async def jarvis_vision_escribir(instruccion, texto_a_escribir):
    try:
        import pyperclip
        ruta_ss = "jarvis_vision_temp.png"
        captura = pyautogui.screenshot()
        captura.save(ruta_ss)
        img_w, img_h = captura.size
        from PIL import Image
        img = Image.open(ruta_ss)
        prompt_vision = (
            f"Eres la visión de JARVIS. Christopher quiere escribir en el campo: {instruccion}.\n"
            f"Resolución de la captura: {img_w}x{img_h} píxeles.\n"
            "Encuentra EXACTAMENTE la posición de este campo de entrada de texto.\n"
            "Las coordenadas están normalizadas de 0 a 1000.\n"
            "Responde ÚNICAMENTE en JSON:\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"descripción del campo\"}\n"
            "Ejemplo: {\"box\": [250, 480, 290, 520], \"description\": \"campo de búsqueda de Google\"}"
        )
        import builtins
        client = builtins.client
        model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        response = client.models.generate_content(model=model_name, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        inicio = rep_text.find('{')
        fin = rep_text.rfind('}')
        if inicio != -1 and fin != -1:
            rep_text = rep_text[inicio:fin+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        centro_y = (ymin + ymax) / 2
        centro_x = (xmin + xmax) / 2
        target_x = int((centro_x / 1000) * img_w)
        target_y = int((centro_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')  # Borrar contenido existente
        time.sleep(0.1)
        # Pegar mediante portapapeles para soportar acentos y caracteres especiales
        pyperclip.copy(texto_a_escribir)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press('enter')

        if os.path.exists(ruta_ss):
            os.remove(ruta_ss)
        return f"Hecho Christopher. He escrito '{texto_a_escribir}' en {instruccion}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "He tenido un pequeño problema técnico para escribir el texto, Christopher."

async def jarvis_vision_buscar_en_sitio(texto_busqueda):
    """Encuentra la barra de búsqueda en la página actual y escribe la consulta."""
    try:
        import pyperclip
        ruta_ss = "jarvis_vision_temp.png"
        captura = pyautogui.screenshot()
        captura.save(ruta_ss)
        img_w, img_h = captura.size
        from PIL import Image
        img = Image.open(ruta_ss)
        prompt_vision = (
            f"Eres la visión de JARVIS. Christopher quiere buscar en el sitio mostrado en la pantalla.\n"
            f"Resolución de la captura: {img_w}x{img_h} píxeles.\n"
            "Localiza la BARRA DE BÚSQUEDA principal del sitio (campo search, zona con icono de lupa, "
            "placeholder 'Buscar', 'Search', 'Chercher'...).\n"
            "Si ves una barra de direcciones de navegador Y una barra de búsqueda del sitio, "
            "prefiere la barra de búsqueda del sitio.\n"
            "Las coordenadas están normalizadas de 0 a 1000 (0=arriba-izquierda, 1000=abajo-derecha).\n"
            "Responde ÚNICAMENTE en JSON:\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"descripción de la barra encontrada\"}\n"
            "Ejemplo: {\"box\": [48, 220, 78, 820], \"description\": \"barra de búsqueda de YouTube\"}"
        )
        import builtins
        client = builtins.client
        model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        response = client.models.generate_content(model=model_name, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        inicio = rep_text.find('{')
        fin = rep_text.rfind('}')
        if inicio != -1 and fin != -1:
            rep_text = rep_text[inicio:fin+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        centro_y = (ymin + ymax) / 2
        centro_x = (xmin + xmax) / 2
        target_x = int((centro_x / 1000) * img_w)
        target_y = int((centro_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.35)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyperclip.copy(texto_busqueda)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')

        if os.path.exists(ruta_ss):
            os.remove(ruta_ss)
        desc = data.get("description", "barra de búsqueda")
        return f"Hecho Christopher. He escrito '{texto_busqueda}' en {desc} y he validado."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "No he podido encontrar la barra de búsqueda en este sitio, Christopher."

async def jarvis_vision_camara(pregunta_usuario=None):
    """Captura una imagen desde la cámara (mediante frontend u OpenCV) y la analiza con Gemini Vision."""
    import builtins
    USER_NAME = builtins.get_user_name() if hasattr(builtins, "get_user_name") else "Christopher"
    hablar = builtins.hablar
    pedir_ia_vision = builtins.pedir_ia_vision
    
    img_b64 = None
    
    # ── 1. Intentar obtener la imagen directamente desde el frontend (cámara activa o getUserMedia) ──
    try:
        if hasattr(builtins, "solicitar_captura_camara"):
            print("[CAMARA] Intentando obtener el frame desde el frontend...")
            img_b64 = await builtins.solicitar_captura_camara()
            if img_b64:
                print("[CAMARA] Frame obtenido con éxito desde el frontend.")
    except Exception as e:
        print(f"[CAMARA] Error al capturar desde el frontend: {e}")

    # ── 2. Fallback con OpenCV si el frontend no devolvió imagen ──
    if not img_b64:
        print("[CAMARA] Fallback: Usando OpenCV (cv2.VideoCapture)...")
        if cv2 is None:
            return f"Lo siento {USER_NAME}, el módulo de visión por cámara (OpenCV) no está instalado."
        
        cap = None
        try:
            ruta_config = "jarvis_config.json"
            idx_camara = None
            etiqueta_camara = None
            if os.path.exists(ruta_config):
                try:
                    with open(ruta_config, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        idx_camara = config.get("camera_device_index")
                        etiqueta_camara = config.get("camera_device_label")
                except Exception as e:
                    print(f"[VISION] Error al cargar la configuración de cámara: {e}")
            
            # Coincidir por nombre mediante pygrabber en Windows (con tolerancia a codificaciones/acentos)
            if etiqueta_camara:
                try:
                    from pygrabber.dshow_graph import FilterGraph
                    graph = FilterGraph()
                    dispositivos = graph.get_input_devices()
                    
                    def coincidir_nombres(etiqueta, nombre_disp):
                        def obtener_palabras_limpias(s):
                            # Reemplaza caracteres no alfanuméricos por espacios
                            limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in s.lower())
                            return {p for p in limpio.split() if len(p) > 2}
                        palabras_etiqueta = obtener_palabras_limpias(etiqueta)
                        palabras_disp = obtener_palabras_limpias(nombre_disp)
                        # Coincide si al menos 2 palabras significativas se comparten
                        return len(palabras_etiqueta.intersection(palabras_disp)) >= 2

                    for idx, nombre in enumerate(dispositivos):
                        if coincidir_nombres(etiqueta_camara, nombre):
                            idx_camara = idx
                            print(f"[CAMARA] Coincidencia por etiqueta: '{etiqueta_camara}' -> Índice {idx_camara} ({nombre})")
                            break
                except Exception as e:
                    print(f"[CAMARA] Error al enumerar pygrabber: {e}")

            if idx_camara is not None:
                try:
                    idx_camara = int(idx_camara)
                    cap = cv2.VideoCapture(idx_camara, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap.release()
                        cap = cv2.VideoCapture(idx_camara)
                except Exception as e:
                    print(f"[CAMARA] Error al abrir índice {idx_camara}: {e}")
                    cap = None

            if not cap or not cap.isOpened():
                for idx in [0, 1, 2]:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        break
                    cap.release()
                if not cap or not cap.isOpened():
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        return f"Lo siento {USER_NAME}, no puedo acceder a su cámara. Verifique que no esté siendo usada por otra aplicación."

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            inicio = time.time()
            while time.time() - inicio < 2.0:
                cap.read()
                await asyncio.sleep(0.1)
                
            ret, frame = cap.read()
            if not ret or frame is None:
                return f"Lo siento {USER_NAME}, la captura ha fallado."
            
            ruta_temp = "jarvis_camera_temp.jpg"
            cv2.imwrite(ruta_temp, frame)
            with open(ruta_temp, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            if os.path.exists(ruta_temp):
                os.remove(ruta_temp)
        except Exception as e:
            return f"Lo siento {USER_NAME}, ha ocurrido un error técnico: {e}"
        finally:
            if cap:
                cap.release()

    # ── 3. Análisis con Gemini Vision ──
    prompt_cam = f"{USER_NAME} te muestra una imagen desde su cámara. Su pregunta: '{pregunta_usuario or 'Describe lo que ves'}'. Analiza la imagen y responde con precisión."
    await hablar(f"Hecho {USER_NAME}, estoy mirando lo que ve su cámara...")
    return await pedir_ia_vision(prompt_cam, img_b64)

async def jarvis_vision_navegador(pregunta_usuario=None):
    """Captura una imagen desde el navegador mediante WebSocket y la analiza con Gemini Vision."""
    import builtins
    USER_NAME = builtins.get_user_name() if hasattr(builtins, "get_user_name") else "Christopher"
    hablar = builtins.hablar
    pedir_ia_vision = builtins.pedir_ia_vision
    CLIENTES_CONECTADOS = getattr(builtins, "CONNECTED_CLIENTS", set())
    
    # Redirigir automáticamente a la cámara si está activa en pantalla
    if getattr(builtins, "WEBCAM_ACTIVA", False):
        print("[VISION] La webcam está activa. Redirigiendo visión del navegador a la cámara.")
        return await jarvis_vision_camara(pregunta_usuario)
        
    try:
        if not CLIENTES_CONECTADOS:
            return f"Lo siento {USER_NAME}, la interfaz web (navegador) no está conectada actualmente."
            
        await hablar(f"Activo la visión del navegador, un momento {USER_NAME}...")
        img_b64 = await solicitar_captura_pantalla()
        
        if not img_b64:
            return f"Lo siento {USER_NAME}, el flujo de video está inactivo. Recuerde hacer clic en el botón 'Activar visión' en la esquina superior derecha de la interfaz web."
            
        if pregunta_usuario:
            prompt_vision = f"{USER_NAME} te muestra su navegador/pantalla. Su pregunta: '{pregunta_usuario}'. Analiza la imagen y responde con precisión."
        else:
            prompt_vision = f"Analiza esta captura del navegador/pantalla de {USER_NAME} y descríbele en detalle lo que ves."
            
        respuesta = await pedir_ia_vision(prompt_vision, img_b64)
        return respuesta
        
    except Exception as e:
        print(f"[VISION NAVEGADOR ERROR] {e}")
        return f"Lo siento {USER_NAME}, ha ocurrido un error al acceder a la visión del navegador: {e}"