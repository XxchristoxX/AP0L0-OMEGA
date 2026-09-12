# src/core/tools.py
# =====================================================================
# DECLARACIÓN DE TODAS LAS HERRAMIENTAS (COMPLETA - 100% INTEGRADA)
# Incluye herramientas base + todas las nuevas
# =====================================================================

TOOL_DECLARATIONS = [
    # ================================================================
    # 1. HERRAMIENTAS BASE (Sistema, Archivos, Web, Control)
    # ================================================================
    {
        "name": "open_app",
        "description": "Opens any application on the computer.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Exact name of the application"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web in multiple modes: search, news, research, price, compare, images, videos, define, trending, summarize, translate, calculate.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query or topic"},
                "mode": {"type": "STRING", "description": "search | news | research | price | compare | images | videos | define | trending | summarize | translate | calculate"},
                "items": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "Comparison aspect"},
                "url": {"type": "STRING", "description": "URL for summarize mode"},
                "target_lang": {"type": "STRING", "description": "Target language for translate mode"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "system_status",
        "description": "Returns real‑time system metrics: CPU, RAM, GPU, temperature, uptime, process count.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "weather_report",
        "description": "Gives weather report for a city.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"city": {"type": "STRING", "description": "City name"}},
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, Instagram, Signal, Discord, or Messenger.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform": {"type": "STRING", "description": "Platform: whatsapp, telegram, instagram, signal, discord, messenger"}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using OS scheduler (Windows Task Scheduler, launchd, cron/at).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time": {"type": "STRING", "description": "Time in HH:MM (24h)"},
                "message": {"type": "STRING", "description": "Reminder text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": "Controls YouTube: play, summarize, get_info, trending.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending"},
                "query": {"type": "STRING", "description": "Search query"},
                "save": {"type": "BOOLEAN", "description": "Save summary"},
                "region": {"type": "STRING", "description": "Country code for trending"},
                "url": {"type": "STRING", "description": "Video URL for get_info"}
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": "Captures the screen or camera and asks a question about the image.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' or 'camera'"},
                "text": {"type": "STRING", "description": "Question about the image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "close_camera",
        "description": "Closes the live camera view.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "computer_settings",
        "description": "Controls computer: volume, brightness, shortcuts, WiFi, shutdown, lock, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "volume_up, volume_down, mute, brightness_up, brightness_down, set_brightness, toggle_wifi, lock_screen, sleep_display, restart, shutdown, show_desktop, minimize_window, maximize_window, close_app, close_tab, new_tab, refresh_page, screenshot, dark_mode, etc."},
                "description": {"type": "STRING", "description": "Natural language description (if action not provided)"},
                "value": {"type": "STRING", "description": "Optional value (for set_brightness, volume_set, etc.)"}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": "Controls any web browser: go_to, search, click, type, scroll, get_text, close, screenshot, etc. Uses real user profile.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "go_to | search | click | type | scroll | get_text | get_url | press | back | forward | reload | close_tab | new_tab | screenshot | smart_click | smart_type | fill_form | switch | close | close_all | list_browsers"},
                "browser": {"type": "STRING", "description": "chrome | edge | firefox | opera | brave | vivaldi | safari"},
                "url": {"type": "STRING"},
                "query": {"type": "STRING"},
                "selector": {"type": "STRING"},
                "text": {"type": "STRING"},
                "description": {"type": "STRING", "description": "Natural language description for smart_click/smart_type"},
                "direction": {"type": "STRING", "description": "up | down"},
                "amount": {"type": "INTEGER"},
                "key": {"type": "STRING"},
                "fields": {"type": "OBJECT"},
                "clear_first": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete (to trash), move, copy, rename, read, write, find, disk_usage, organize_desktop, info.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path": {"type": "STRING", "description": "File/folder path or shortcut (desktop, downloads, documents, pictures, music, videos, home)"},
                "destination": {"type": "STRING"},
                "new_name": {"type": "STRING"},
                "content": {"type": "STRING"},
                "name": {"type": "STRING"},
                "extension": {"type": "STRING"},
                "count": {"type": "INTEGER"},
                "append": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls desktop: wallpaper, organize, clean, list, stats, AI-powered tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | current_wallpaper | organize | clean | list | stats | task"},
                "path": {"type": "STRING"},
                "url": {"type": "STRING"},
                "mode": {"type": "STRING", "description": "by_type | by_date"},
                "task": {"type": "STRING", "description": "Natural language task for AI execution"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, builds, optimizes, or debug code. Supports screen_debug with screenshots.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "write | edit | explain | run | build | optimize | screen_debug"},
                "description": {"type": "STRING"},
                "language": {"type": "STRING"},
                "output_path": {"type": "STRING"},
                "file_path": {"type": "STRING"},
                "code": {"type": "STRING"},
                "args": {"type": "STRING"},
                "timeout": {"type": "INTEGER"},
                "instruction": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi‑file projects from scratch (Python, JavaScript, etc.). Plans, writes, installs dependencies, runs, and auto-fixes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING"},
                "language": {"type": "STRING"},
                "project_name": {"type": "STRING"},
                "timeout": {"type": "INTEGER"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, smart_type, click, double_click, right_click, hotkey, press, scroll, move, drag, screenshot, wait, clear_field, focus_window, screen_find, screen_click, random_data, user_data.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | drag | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text": {"type": "STRING"},
                "x": {"type": "INTEGER"},
                "y": {"type": "INTEGER"},
                "x1": {"type": "INTEGER"},
                "y1": {"type": "INTEGER"},
                "x2": {"type": "INTEGER"},
                "y2": {"type": "INTEGER"},
                "keys": {"type": "STRING"},
                "key": {"type": "STRING"},
                "direction": {"type": "STRING"},
                "amount": {"type": "INTEGER"},
                "seconds": {"type": "NUMBER"},
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
                "type": {"type": "STRING"},
                "field": {"type": "STRING"},
                "clear_first": {"type": "BOOLEAN"},
                "path": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": "Updates games on Steam or Epic Games. Can install, list, check status, schedule auto-update, and shutdown when done.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status"},
                "platform": {"type": "STRING", "description": "steam | epic | both"},
                "game_name": {"type": "STRING"},
                "app_id": {"type": "STRING"},
                "hour": {"type": "INTEGER"},
                "minute": {"type": "INTEGER"},
                "shutdown_when_done": {"type": "BOOLEAN"}
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin": {"type": "STRING"},
                "destination": {"type": "STRING"},
                "date": {"type": "STRING"},
                "return_date": {"type": "STRING"},
                "passengers": {"type": "INTEGER"},
                "cabin": {"type": "STRING", "description": "economy | premium | business | first"},
                "save": {"type": "BOOLEAN"}
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "manage_monitor",
        "description": "Add, remove, or list background monitoring topics (news alerts).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | remove | list"},
                "topic": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": "Shuts down the assistant completely.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "file_processor",
        "description": "Processes uploaded files: images, PDF, Word, Excel, code, audio, video, archives, presentations. Supports describe, ocr, summarize, resize, convert, compress, trim, transcribe, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING"},
                "action": {"type": "STRING", "description": "describe | ocr | summarize | extract_text | resize | convert | compress | crop | trim | transcribe | analyze | info | filter | sort | to_word | to_csv | etc."},
                "instruction": {"type": "STRING"},
                "format": {"type": "STRING"},
                "width": {"type": "INTEGER"},
                "height": {"type": "INTEGER"},
                "scale": {"type": "NUMBER"},
                "quality": {"type": "INTEGER"},
                "start": {"type": "STRING"},
                "end": {"type": "STRING"},
                "timestamp": {"type": "STRING"},
                "column": {"type": "STRING"},
                "value": {"type": "STRING"},
                "condition": {"type": "STRING"},
                "ascending": {"type": "BOOLEAN"},
                "save": {"type": "BOOLEAN"},
                "destination": {"type": "STRING"}
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": "Saves important personal facts to long‑term memory (identity, preferences, projects, relationships, wishes, notes).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "identity | preferences | projects | relationships | wishes | notes"},
                "key": {"type": "STRING", "description": "short snake_case key"},
                "value": {"type": "STRING", "description": "concise value"}
            },
            "required": ["category", "key", "value"]
        }
    },
    # ================================================================
    # 2. HERRAMIENTAS DE INTELIGENCIA Y VISIÓN
    # ================================================================
    {
        "name": "ocr_extract",
        "description": "Extracts text from an image using Tesseract OCR.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Path to the image file"}
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "face_recognize",
        "description": "Recognizes faces, emotions, age, and gender in an image using DeepFace.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Path to the image file"}
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "detect_objects",
        "description": "Detects objects in an image or video using YOLO (or OpenCV fallback).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Path to the image file"},
                "video_path": {"type": "STRING", "description": "Path to the video file (optional)"},
                "interval": {"type": "INTEGER", "description": "Interval in seconds for video frame analysis"}
            },
            "required": []
        }
    },
    {
        "name": "edit_image",
        "description": "Applies filters (blur, contour, sharpen, etc.) and adjusts brightness, contrast, sharpness.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Path to the image file"},
                "filter_type": {"type": "STRING", "description": "blur | contour | detail | edge | emboss | sharpen | smooth"},
                "brightness": {"type": "NUMBER", "description": "Brightness factor (0.1 - 3.0)"},
                "contrast": {"type": "NUMBER", "description": "Contrast factor (0.1 - 3.0)"},
                "sharpness": {"type": "NUMBER", "description": "Sharpness factor (0.1 - 3.0)"}
            },
            "required": ["image_path"]
        }
    },
    # NOTA: La primera definición de gesture_control (solo start/stop) ha sido eliminada.
    # La versión completa (con set_panel) se encuentra al final del archivo.
    # ================================================================
    # 3. HERRAMIENTAS DE PRODUCTIVIDAD Y ORGANIZACIÓN
    # ================================================================
    {
        "name": "todo_list",
        "description": "Manages a to‑do list: add, list, remove, clear.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | list | remove | clear"},
                "task": {"type": "STRING", "description": "Task description (for add)"},
                "task_id": {"type": "INTEGER", "description": "Task ID (for remove)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "manage_calendar",
        "description": "Manages local calendar events: upcoming, today, add, remove, list.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "upcoming | today | add | remove | list"},
                "days": {"type": "INTEGER", "description": "Days ahead for upcoming"},
                "title": {"type": "STRING", "description": "Event title (for add)"},
                "datetime": {"type": "STRING", "description": "YYYY-MM-DDTHH:MM (for add)"},
                "location": {"type": "STRING", "description": "Event location (optional)"},
                "index": {"type": "INTEGER", "description": "Event index (for remove)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "create_note",
        "description": "Creates a quick note and saves it as a text file.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Title of the note"},
                "content": {"type": "STRING", "description": "Content of the note"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "create_task_reminder",
        "description": "Creates a recurring reminder (daily, weekly, monthly, once) at a specific time.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Reminder message"},
                "time": {"type": "STRING", "description": "HH:MM format"},
                "repeat": {"type": "STRING", "description": "daily | weekly | monthly | once"}
            },
            "required": ["message", "time"]
        }
    },
    {
        "name": "set_alarm",
        "description": "Sets a one-time system alarm at a specific time (plays beep).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "time": {"type": "STRING", "description": "HH:MM format"},
                "message": {"type": "STRING", "description": "Alarm message"}
            },
            "required": ["time"]
        }
    },
    # ================================================================
    # 4. HERRAMIENTAS DE ARCHIVOS Y CONVERSIÓN
    # ================================================================
    {
        "name": "youtube_download",
        "description": "Downloads a YouTube video or audio (MP3) using yt-dlp.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "YouTube video URL"},
                "quality": {"type": "STRING", "description": "best | 720p | 1080p"},
                "audio_only": {"type": "BOOLEAN", "description": "Download only audio as MP3"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "convert_file",
        "description": "Converts images (PNG, JPG, WebP, etc.) or documents to PDF.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "image | to_pdf"},
                "file_path": {"type": "STRING", "description": "Path to the file"},
                "to_format": {"type": "STRING", "description": "png | jpg | webp | bmp (for image conversion)"}
            },
            "required": ["action", "file_path"]
        }
    },
    {
        "name": "manage_pdf",
        "description": "PDF tools: read text, get info, merge multiple PDFs, split pages.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read | info | merge | split"},
                "file_path": {"type": "STRING", "description": "Path to the PDF file"},
                "pages": {"type": "STRING", "description": "Page numbers (e.g. '1,3-5' or 'all')"},
                "files": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of PDF files to merge"},
                "output_name": {"type": "STRING", "description": "Output filename without extension (for merge)"}
            },
            "required": ["action"]
        }
    },
    # ================================================================
    # 5. HERRAMIENTAS DE COMUNICACIÓN Y REDES
    # ================================================================
    {
        "name": "send_email",
        "description": "Sends an email via Gmail.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "to_email": {"type": "STRING", "description": "Recipient email"},
                "subject": {"type": "STRING", "description": "Subject line"},
                "message": {"type": "STRING", "description": "Body of the email"},
                "cc_email": {"type": "STRING", "description": "CC recipient (optional)"}
            },
            "required": ["to_email", "subject", "message"]
        }
    },
    {
        "name": "send_email_advanced",
        "description": "Sends an email with attachments using Gmail.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "to": {"type": "STRING", "description": "Recipient email"},
                "subject": {"type": "STRING", "description": "Subject line"},
                "body": {"type": "STRING", "description": "Body of the email"},
                "attachments": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of file paths to attach"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "manage_email",
        "description": "Reads emails (IMAP) or sends emails (SMTP) with configured Gmail/Outlook.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "setup | read | send | status"},
                "email": {"type": "STRING", "description": "Email address (for setup)"},
                "password": {"type": "STRING", "description": "App password (for setup)"},
                "provider": {"type": "STRING", "description": "gmail | outlook"},
                "limit": {"type": "INTEGER", "description": "Number of emails to read"},
                "to": {"type": "STRING", "description": "Recipient (for send)"},
                "subject": {"type": "STRING", "description": "Subject (for send)"},
                "body": {"type": "STRING", "description": "Body (for send)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "send_sms",
        "description": "Sends an SMS using Twilio or similar service (stub).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "to": {"type": "STRING", "description": "Phone number"},
                "message": {"type": "STRING", "description": "SMS content"}
            },
            "required": ["to", "message"]
        }
    },
    {
        "name": "control_iot",
        "description": "Controls IoT devices via MQTT, Philips Hue, Home Assistant, or Tuya.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "platform": {"type": "STRING", "description": "mqtt | hue | homeassistant | tuya"},
                "device": {"type": "STRING", "description": "Device identifier (topic, light ID, entity ID, etc.)"},
                "action": {"type": "STRING", "description": "on | off | toggle | (other platform-specific)"},
                "brightness": {"type": "INTEGER", "description": "Brightness 0-255 (for Hue)"}
            },
            "required": ["platform", "device", "action"]
        }
    },
    # ================================================================
    # 6. HERRAMIENTAS DE ENTRETENIMIENTO Y CREATIVIDAD
    # ================================================================
    {
        "name": "spotify_control",
        "description": "Controls Spotify: play, pause, next, previous, volume_up, volume_down.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | next | previous | volume_up | volume_down"},
                "query": {"type": "STRING", "description": "Song or artist name (for play)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "rhythmbox_control",
        "description": "Controls Rhythmbox media player on Linux.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | play_pause | next | previous | stop | volume_up | volume_down"}
            },
            "required": ["action"]
        }
    },
    # NOTA: La primera definición de generate_image (solo prompt, size, style) ha sido eliminada.
    # La versión completa (con mode y enum) se encuentra al final del archivo.
    {
        "name": "change_wallpaper",
        "description": "Changes the desktop wallpaper from a local image path.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Path to the image file"}
            },
            "required": ["image_path"]
        }
    },
    # ================================================================
    # 7. HERRAMIENTAS DE BÚSQUEDA Y RECOMENDACIÓN
    # ================================================================
    {
        "name": "get_news",
        "description": "Fetches news headlines by category or search query.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "top | search"},
                "category": {"type": "STRING", "description": "technology | sports | politics | economy | science | health | entertainment"},
                "query": {"type": "STRING", "description": "Search term (for search mode)"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of results"}
            },
            "required": []
        }
    },
    {
        "name": "news_report",
        "description": "Fetches dynamic news headlines by category (uses NewsAPI or RSS fallback).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "technology | sports | business | science | health | general"}
            },
            "required": []
        }
    },
    {
        "name": "search_recipes",
        "description": "Searches for recipes by ingredient or name.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Ingredient or recipe name"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of results"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_podcast",
        "description": "Searches for podcasts by topic.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search | trending"},
                "query": {"type": "STRING", "description": "Topic or podcast name"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of results"}
            },
            "required": []
        }
    },
    {
        "name": "get_recommendation",
        "description": "Gets recommendations for movies (TMDB), music, or books.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "description": "movie | music | book"},
                "genre": {"type": "STRING", "description": "Genre (e.g., action, comedy, drama)"}
            },
            "required": ["type"]
        }
    },
    # ================================================================
    # 8. HERRAMIENTAS FINANCIERAS Y UTILITARIAS
    # ================================================================
    {
        "name": "get_stock_crypto",
        "description": "Gets real-time prices for stocks (Yahoo Finance) or cryptocurrencies (CoinGecko).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "stock | crypto"},
                "symbol": {"type": "STRING", "description": "Stock symbol (e.g., AAPL) or crypto name (e.g., bitcoin)"}
            },
            "required": ["action", "symbol"]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Gets extended weather forecast for a city for multiple days.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"},
                "days": {"type": "INTEGER", "description": "Number of days (3-7)"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate_expression",
        "description": "Evaluates a mathematical expression.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {"type": "STRING", "description": "Mathematical expression (e.g., 2 + 2 * 5)"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_public_ip",
        "description": "Gets the public IP address.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "get_location",
        "description": "Gets approximate location based on public IP.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "generate_password",
        "description": "Generates a secure random password.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "length": {"type": "INTEGER", "description": "Password length"}
            },
            "required": []
        }
    },
    # ================================================================
    # 9. HERRAMIENTAS DE SISTEMA Y TERMINAL
    # ================================================================
    {
        "name": "run_terminal",
        "description": "Executes a system command (Windows PowerShell / macOS zsh / Linux bash) and returns the output.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Command to execute"},
                "timeout": {"type": "INTEGER", "description": "Timeout in seconds (default 30)"},
                "cwd": {"type": "STRING", "description": "Working directory (optional)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "system_volume",
        "description": "Controls system volume: up, down, mute, unmute, or set a percentage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "up | down | mute | unmute | set"},
                "value": {"type": "INTEGER", "description": "Volume percentage (0-100) for 'set'"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "system_sleep",
        "description": "Suspends the operating system (sleep mode).",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    # ================================================================
    # 10. HERRAMIENTAS DE AUTOMATIZACIÓN Y PROGRAMACIÓN
    # ================================================================
    {
        "name": "manage_schedule",
        "description": "Schedules recurring tasks (open app, run command, backup, etc.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | add | remove | toggle | run_now"},
                "name": {"type": "STRING", "description": "Task name"},
                "task_action": {"type": "STRING", "description": "open_app | run_command | backup | reminder"},
                "interval_minutes": {"type": "INTEGER", "description": "Interval in minutes"},
                "extra": {"type": "STRING", "description": "Extra parameters (app name, command, source->dest)"},
                "index": {"type": "INTEGER", "description": "Task index (for remove/toggle/run_now)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "manage_workflow",
        "description": "Creates, lists, runs, or deletes multi-step workflows.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | run | create | delete"},
                "name": {"type": "STRING", "description": "Workflow name"},
                "steps": {"type": "STRING", "description": "JSON array of steps: [{'tool':'...','parameters':{...}}] (for create)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "run_macro",
        "description": "Records, plays, or manages keyboard/mouse macros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "record | stop | play | play_now | list | delete"},
                "name": {"type": "STRING", "description": "Macro name"},
                "duration": {"type": "INTEGER", "description": "Recording duration in seconds (for record)"},
                "speed": {"type": "NUMBER", "description": "Playback speed multiplier (for play)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "run_backup",
        "description": "Runs a backup of a file or folder (copies to destination) or schedules it.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "run | schedule"},
                "source": {"type": "STRING", "description": "Source file or folder path"},
                "destination": {"type": "STRING", "description": "Destination path (optional)"},
                "interval_minutes": {"type": "INTEGER", "description": "Schedule interval (for schedule)"}
            },
            "required": ["action", "source"]
        }
    },
    # ================================================================
    # 11. HERRAMIENTAS DE PROCESAMIENTO DE TEXTO Y PORTAPAPELES
    # ================================================================
    {
        "name": "translate_text",
        "description": "Translates text to any language using Gemini.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text to translate"},
                "target_lang": {"type": "STRING", "description": "Target language (e.g., Spanish, English, French)"},
                "source_lang": {"type": "STRING", "description": "Source language (auto by default)"}
            },
            "required": ["text", "target_lang"]
        }
    },
    {
        "name": "correct_text",
        "description": "Corrects grammar and spelling errors in a text using pyspellchecker.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text to correct"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "summarize_text",
        "description": "Generates a summary of a text using Gemini.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text to summarize"},
                "max_sentences": {"type": "INTEGER", "description": "Maximum number of sentences in the summary"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "clipboard_process",
        "description": "Processes the current clipboard content (translate, summarize, explain, correct).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "translate | summarize | explain | correct"},
                "target_language": {"type": "STRING", "description": "Target language for translation"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "clipboard_history",
        "description": "Manages clipboard history: list, get, copy, clear.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | get_last | get_index | copy | clear"},
                "text": {"type": "STRING", "description": "Text to copy (for copy)"},
                "index": {"type": "INTEGER", "description": "Item index (for get_index)"}
            },
            "required": ["action"]
        }
    },
    # ================================================================
    # 12. HERRAMIENTAS DE INTEGRACIÓN Y SERVICIOS EXTERNOS
    # ================================================================
    {
        "name": "gdrive_upload",
        "description": "Uploads a file to Google Drive (OAuth required).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Local file path"},
                "folder_id": {"type": "STRING", "description": "Google Drive folder ID (optional)"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "web_scrape",
        "description": "Extracts the main text from a web page.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Web page URL"},
                "max_chars": {"type": "INTEGER", "description": "Maximum characters to extract"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "create_desktop_shortcut",
        "description": "Creates a desktop shortcut to an application or file.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Shortcut name"},
                "target": {"type": "STRING", "description": "Path to the executable or file"}
            },
            "required": ["name", "target"]
        }
    },
    {
        "name": "send_push_notification",
        "description": "Sends a Windows toast notification.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Notification title"},
                "message": {"type": "STRING", "description": "Notification message"},
                "duration": {"type": "INTEGER", "description": "Duration in seconds"}
            },
            "required": ["title", "message"]
        }
    },
    # ================================================================
    # 13. HERRAMIENTAS DE PERSONALIDAD Y AUTONOMÍA
    # ================================================================
    {
        "name": "switch_personality",
        "description": "Changes the assistant's personality (Jarvis, Agata, Tony, Friday, Apolo).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "personality": {"type": "STRING", "description": "jarvis | agata | tony | friday | apolo"}
            },
            "required": ["personality"]
        }
    },
    {
        "name": "plan_task",
        "description": "Plans and executes a complex multi-step task autonomously.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "STRING", "description": "Goal to accomplish"},
                "steps": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Optional steps (auto-generated if omitted)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "run_skill",
        "description": "Executes a built‑in skill from the catalog (morning_digest, deep_research, code_assistant, etc.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "morning_digest | deep_research | code_assistant | etc."},
                "params": {"type": "STRING", "description": "Optional JSON parameters"}
            },
            "required": ["skill_name"]
        }
    },
    {
        "name": "local_ai_chat",
        "description": "Sends a message to the local offline assistant (Vosk + Ollama).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Message for the local assistant"},
                "use_voice": {"type": "BOOLEAN", "description": "Whether to respond aloud"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "check_proactive",
        "description": "Performs a proactive check-in, offering timely suggestions or reminders based on context.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    # ================================================================
    # 14. HERRAMIENTAS DE BASE DE DATOS Y DOCUMENTOS
    # ================================================================
    {
        "name": "database_query",
        "description": "Executes a SQL query on SQLite or MySQL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "query | tables"},
                "type": {"type": "STRING", "description": "sqlite | mysql"},
                "query": {"type": "STRING", "description": "SQL query"},
                "file_path": {"type": "STRING", "description": "SQLite file path"},
                "host": {"type": "STRING", "description": "MySQL host"},
                "user": {"type": "STRING", "description": "MySQL user"},
                "password": {"type": "STRING", "description": "MySQL password"},
                "database": {"type": "STRING", "description": "MySQL database name"}
            },
            "required": []
        }
    },
    {
        "name": "generate_word_document",
        "description": "Generates a professional Word document (uses Agata creator).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Document title"},
                "content": {"type": "STRING", "description": "Document content"},
                "output_path": {"type": "STRING", "description": "Output path (optional)"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "generate_ppt_presentation",
        "description": "Generates a PowerPoint presentation with slides (uses Agata creator).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Presentation title"},
                "slides": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of slide content"},
                "output_path": {"type": "STRING", "description": "Output path (optional)"}
            },
            "required": ["title", "slides"]
        }
    },
    {
        "name": "extract_color_palette",
        "description": "Extracts a color palette from an image (uses colorthief).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Image path"},
                "num_colors": {"type": "INTEGER", "description": "Number of colors (default 5)"}
            },
            "required": ["image_path"]
        }
    },
    # ================================================================
    # 15. NUEVAS HERRAMIENTAS (AÑADIDAS)
    # ================================================================
    {
        "name": "detect_emotion",
        "description": "Detects the emotion in a voice audio (happy, sad, angry, neutral).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "audio_bytes": {"type": "STRING", "description": "Audio bytes in WAV format"}
            },
            "required": ["audio_bytes"]
        }
    },
    {
        "name": "toggle_aura_mode",
        "description": "Toggles the Aura mode for advanced AI reasoning and creativity.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "toggle | on | off"}
            },
            "required": []
        }
    },
    {
        "name": "toggle_continuous_listening",
        "description": "Toggles continuous listening mode (always listening without wake word).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "toggle | on | off"}
            },
            "required": []
        }
    },
    {
        "name": "manage_contacts",
        "description": "Manages contacts: add, list, remove.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | list | remove"},
                "name": {"type": "STRING", "description": "Contact name (for add)"},
                "phone": {"type": "STRING", "description": "Phone number (for add)"},
                "email": {"type": "STRING", "description": "Email (for add)"},
                "notes": {"type": "STRING", "description": "Notes (for add)"},
                "contact_id": {"type": "INTEGER", "description": "Contact ID (for remove)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "clipboard_proactive",
        "description": "Starts proactive clipboard monitoring with smart suggestions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "phone_control",
        "description": "Controls Android phone via ADB: list devices, get SMS, send SMS, make call, end call, get notifications.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list_devices | get_sms | send_sms | make_call | end_call | get_notifications"},
                "number": {"type": "STRING", "description": "Phone number for SMS/call"},
                "message": {"type": "STRING", "description": "SMS message content"},
                "limit": {"type": "INTEGER", "description": "Number of SMS/notifications to fetch"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "environment_control",
        "description": "Adjusts system settings based on context: power saver, performance, focus.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | set_mode"},
                "mode": {"type": "STRING", "description": "auto | power_saver | performance | focus | normal"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_analyzer",
        "description": "Analyzes and organizes files: find duplicates, organize by type, clean duplicates.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "find_duplicates | organize | clean_duplicates"},
                "directory": {"type": "STRING", "description": "Directory to analyze/organize"},
                "min_size": {"type": "INTEGER", "description": "Minimum file size in bytes for duplicate check"},
                "keep": {"type": "STRING", "description": "Which duplicate to keep: first | latest"}
            },
            "required": ["action"]
        }
    },
    # ================================================================
    # HERRAMIENTAS DE LIVEKIT Y APLAUSOS
    # ================================================================
    {
        "name": "android_connect",
        "description": "Conecta con la app Android vía LiveKit o WebSocket.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "connect | disconnect | status"},
                "url": {"type": "STRING", "description": "URL del servidor LiveKit (opcional)"},
                "token": {"type": "STRING", "description": "Token de autenticación (opcional)"}
            },
            "required": []
        }
    },
    {
        "name": "toggle_clap_detection",
        "description": "Activa o desactiva la detección de aplausos (doble clap).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "on | off | toggle"}
            },
            "required": []
        }
    },
    {
        "name": "get_proactive_suggestion",
        "description": "Obtiene una sugerencia proactiva basada en el contexto actual (hora, memoria, monitores).",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    # NOTA: La primera definición de multi_agent (en español) ha sido eliminada.
    # Solo se mantiene run_multi_agent (en inglés) que es más completa.
    {
        "name": "run_multi_agent",
        "description": "Executes multiple tasks in parallel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tasks": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"goal": {"type": "STRING"}}}, "description": "List of task goals"}
            },
            "required": ["tasks"]
        }
    },
    {
        "name": "generate_image",
        "description": "Generates an image from a text prompt using AI. Supports multiple providers and modes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Detailed image description"},
                "mode": {
                    "type": "STRING",
                    "description": "auto (default), all (generates 3 versions), hf, pollinations, replicate",
                    "enum": ["auto", "all", "hf", "pollinations", "replicate"]
                },
                "size": {"type": "STRING", "description": "512x512 or 1024x1024 (default: 512x512)"},
                "style": {"type": "STRING", "description": "Artistic style (optional)"}
            },
            "required": ["prompt"]
        }
    },
    # Única definición de gesture_control (completa, con set_panel)
    {
        "name": "gesture_control",
        "description": "Activa o desactiva el control por gestos con la mano usando la cámara. Permite mover el panel circular, hacer clic, arrastrar y desplazarse.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start | stop | toggle | status | set_panel"
                },
                "panel": {
                    "type": "OBJECT",
                    "description": "Widget del panel circular (solo para set_panel)"
                }
            },
            "required": ["action"]
        }
    }
]