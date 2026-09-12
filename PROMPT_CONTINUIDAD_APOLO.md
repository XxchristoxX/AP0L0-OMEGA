# Prompt de continuidad — AP0L0 OMEGA

## Contexto

Continúa el trabajo de reparación del proyecto **AP0L0 OMEGA** ubicado en `D:\Downloads\IA\AP0L0 OMEGA`. El idioma principal del sistema es español y debe conservar soporte para francés, inglés, italiano y ruso. El sistema debe funcionar en Windows, Linux, macOS y Android cuando la plataforma lo permita, con tres estados de conectividad: nube, local y automático con fallback local.

Actúa como arquitecto de software senior. No declares que el sistema está correcto únicamente porque compila: reproduce el arranque en el entorno virtual real del usuario, corrige cada error nuevo y vuelve a ejecutar la prueba hasta obtener un arranque estable. Trabaja incrementalmente y no elimines funcionalidad existente sin justificarlo.

## Estado verificado hasta ahora

La prueba de importación del entorno de validación terminó correctamente:

```text
OK syntax main.py
OK syntax ui.py
OK syntax src/core/config.py
OK syntax src/core/jarvis_live.py
OK syntax src/core/multi_provider.py
OK syntax src/core/hybrid_router.py
OK syntax src/utils/system_utils.py
OK syntax src/actions/antivirus_scanner.py
OK syntax src/actions/file_manager.py
OK syntax src/actions/secure_browser.py
OK syntax src/actions/uninstaller_helper.py
OK syntax src/actions/file_processor.py
OK syntax src/actions/youtube_video.py
OK syntax src/actions/system_monitor.py
OK syntax src/actions/app_launcher.py
OK syntax src/ui/camera_handler.py
OK main import
OK JarvisLive import
OK router contract
```

Después apareció un error real en Windows:

```text
RuntimeError: api_keys.json not found at:
D:\Downloads\IA\AP0L0 OMEGA\config\api_keys.json
```

Ese error se corrigió en `src/core/openrouter_client.py` con estas decisiones:

1. Se buscan claves en ambas rutas:
   - `config/api_keys.json`
   - `src/config/api_keys.json`
2. La API cloud ya no se inicializa de manera fatal si no existe una clave.
3. `OpenRouterClient` queda desactivado (`enabled=False`) cuando no hay API key.
4. El modo local puede continuar sin OpenRouter.

También se hizo `pyautogui` opcional en `src/core/func_integration.py`.

La prueba posterior confirmó:

```text
OPENROUTER_ENABLED True
JARVIS_IMPORT_OK
MAIN_IMPORT_OK
```

La clave mostrada por la prueba nunca debe imprimirse ni exponerse.

## Correcciones previas realizadas

Se corrigieron los siguientes contratos y dependencias:

- Se añadió `_save_config` atómico en `src/core/config.py`.
- Se hizo `sounddevice` opcional en `src/core/jarvis_live.py`.
- Se hizo `winreg` opcional en `antivirus_scanner.py` y `uninstaller_helper.py`.
- Se hizo `ctypes.windll.user32` opcional en `file_manager.py`.
- Se añadió apertura de carpetas con `xdg-open`/`open` fuera de Windows.
- Se hizo `pywebview` opcional en `secure_browser.py`.
- Se hizo `websockets` opcional en `jarvis_live.py`.
- Se hizo `psutil` opcional en `ui.py` y `system_monitor.py`.
- Se hizo OpenCV opcional en `camera_handler.py`.
- Se hizo `google.genai` opcional en `file_processor.py`.
- Se hicieron `pyautogui` y `numpy` opcionales en `youtube_video.py`.
- Se hicieron opcionales los fallbacks de captura de pantalla/cámara.
- Se restauró `open_app_compat` en `app_launcher.py`.
- Se restauró `modo_boulot` en `app_launcher.py`.

## Archivos principales modificados

- `src/core/config.py`
- `src/core/jarvis_live.py`
- `src/core/openrouter_client.py`
- `src/core/func_integration.py`
- `src/core/multi_provider.py`
- `src/core/hybrid_router.py`
- `src/utils/system_utils.py`
- `ui.py`
- `src/actions/antivirus_scanner.py`
- `src/actions/file_manager.py`
- `src/actions/secure_browser.py`
- `src/actions/uninstaller_helper.py`
- `src/actions/file_processor.py`
- `src/actions/youtube_video.py`
- `src/actions/system_monitor.py`
- `src/actions/app_launcher.py`
- `src/ui/camera_handler.py`

## Próximo procedimiento obligatorio

### 1. Reproducir en Windows y en el venv real

Desde Git Bash:

```bash
cd /d/Downloads/IA/AP0L0\ OMEGA
source venv/Scripts/activate
python --version
python -c "import sys; print(sys.executable)"
python -c "import src.core.jarvis_live; print('JARVIS_IMPORT_OK')"
python main.py
```

No ejecutar únicamente el Python del sandbox. La validación decisiva es la del entorno virtual del usuario.

### 2. Verificar configuración

Comprobar sin imprimir secretos:

```bash
python -c "from pathlib import Path; import json; p=Path('config/api_keys.json'); q=Path('src/config/api_keys.json'); print(p.exists(), q.exists())"
```

Si ninguna ruta existe, crear una configuración segura mínima únicamente si el proyecto tiene un esquema claro. No inventar claves. La ausencia de nube debe activar modo local, no detener el arranque.

### 3. Si aparece otro error

- Copiar el traceback completo.
- Identificar si es un import obligatorio, una ruta incorrecta, una API inicializada al importar o un contrato interno faltante.
- Corregir el módulo de origen, no ocultar el error con un `except Exception` global.
- Añadir fallback solo cuando la funcionalidad sea realmente opcional.
- Repetir `py_compile`, import de `JarvisLive`, import de `main` y arranque real.

### 4. Validación funcional mínima

Después del arranque comprobar:

- La ventana principal abre.
- El menú flotante aparece.
- Cambiar personalidad modifica nombre, color, tema y voz.
- Cambiar idioma actualiza textos visibles y agente.
- Probar español, francés, inglés, italiano y ruso.
- Cambiar modo automático, nube y local sin reiniciar.
- Desactivar red y comprobar fallback local.
- Activar red y verificar nube solo si hay API key válida.
- El menú flotante ejecuta cada acción visible y no contiene botones muertos.
- El cambio de personalidad se conserva al reiniciar.
- El sistema no arranca con una personalidad distinta a la guardada.

## Pendientes conocidos

1. Ejecutar el `main.py` real dentro de `venv` de Windows y capturar el siguiente error, si existe.
2. Revisar que `requirements.txt` coincida con todos los imports funcionales y que las dependencias opcionales estén documentadas por plataforma.
3. Revisar todas las rutas de configuración duplicadas (`config`, `src/config` y posibles archivos `jarvis_config.json`) y establecer una única fuente de verdad con compatibilidad de migración.
4. Revisar `src/core/func_integration.py`: algunas funciones pueden llamar OpenRouter o Google sin comprobar disponibilidad. Deben devolver mensajes controlados y nunca abortar el arranque.
5. Revisar la importación opcional de `command_processor.py`, Google y búsquedas web.
6. Probar el ejecutable con `python -m` y desde el directorio raíz para evitar diferencias de `sys.path`.
7. Revisar Android: no asumir PyQt6, `winreg`, `ctypes.windll`, `xdg-open`, cámara de escritorio o subprocess. Android probablemente requiere una capa UI/adaptador distinta.
8. Revisar concurrencia: IPTV, monitores, TTS y agentes no deben dejar hilos bloqueados al cerrar.
9. Añadir pruebas automatizadas de contratos de imports y del router híbrido.
10. Revisar seguridad: no registrar API keys, rutas sensibles ni prompts completos con credenciales.

## Mejoras recomendadas

- Crear `src/core/platform.py` con capacidades declaradas por plataforma.
- Crear `src/core/optional_dependencies.py` para centralizar disponibilidad de audio, cámara, Google, OpenRouter, WebSocket y automatización.
- Crear `src/core/config_store.py` para eliminar escrituras directas dispersas.
- Añadir `pytest` con pruebas para:
  - configuración sin claves;
  - import mínimo local;
  - fallback nube/local;
  - cinco idiomas;
  - cinco personalidades;
  - contratos de menús;
  - rutas Windows/Linux/macOS.
- Añadir `requirements-core.txt`, `requirements-windows.txt`, `requirements-linux.txt`, `requirements-macos.txt` y documentación específica para Android.
- Añadir un comando de diagnóstico:

```bash
python -m src.tools.diagnose --mode local
python -m src.tools.diagnose --mode cloud
```

- No iniciar servidores ni clientes externos durante la importación de módulos; iniciarlos dentro de `main()` o del ciclo de vida correspondiente.
- Sustituir mensajes mezclados en francés/inglés por traducciones mediante `i18n`.
- Añadir registro estructurado con niveles y sin secretos.

## Criterio de finalización

No finalizar con frases como “debería funcionar”. Finalizar únicamente cuando se haya documentado:

1. El traceback original corregido.
2. El resultado de la importación dentro del venv real.
3. El resultado del arranque de `main.py`.
4. Las pruebas funcionales realizadas.
5. Los errores restantes, si son dependencias opcionales y cómo instalarlas.
6. Los archivos modificados.
7. Las limitaciones reales de Android y cualquier trabajo aún pendiente.

Si el arranque vuelve a fallar, continuar desde el nuevo traceback en lugar de declarar éxito.

## Última instrucción

Continúa ahora con la reproducción real dentro del venv de Windows y no detengas el trabajo hasta corregir el siguiente error verificable. Conserva todos los avances anteriores y actualiza este documento al completar cada nueva fase.
