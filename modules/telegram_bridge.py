"""
telegram_bridge.py - Puente para Telegram
Permite controlar AP0LO desde Telegram
Basado en Chi-K1ng/Chi-King-J.A.R.V.I.S
"""

import os
import json
import asyncio
import threading
from datetime import datetime

# Instalar: pip install python-telegram-bot
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[Telegram] ⚠️ python-telegram-bot no instalado. Instala: pip install python-telegram-bot")

class TelegramBridge:
    def __init__(self, token=None, allowed_user_id=None):
        if not TELEGRAM_AVAILABLE:
            raise ImportError("python-telegram-bot no instalado")
        
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.allowed_user_id = allowed_user_id or os.getenv("TELEGRAM_ALLOWED_USER_ID")
        self.app = None
        self._on_message_callback = None
        self._running = False

    def set_message_callback(self, callback):
        """Callback que recibe (user_id, text) y debe devolver la respuesta"""
        self._on_message_callback = callback

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.allowed_user_id and user_id != self.allowed_user_id:
            await update.message.reply_text("⛔ No autorizado.")
            return
        await update.message.reply_text(
            "🤖 AP0LO conectado a Telegram.\n"
            "Envía cualquier mensaje y te responderé.\n"
            "Comandos disponibles:\n"
            "/status - Estado del sistema\n"
            "/help - Esta ayuda"
        )

    async def _status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.allowed_user_id and user_id != self.allowed_user_id:
            await update.message.reply_text("⛔ No autorizado.")
            return
        await update.message.reply_text(
            f"📊 **Estado de AP0LO**\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"✅ Sistema operativo: {os.name}\n"
            f"📡 Conectado a Telegram: ✅"
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if self.allowed_user_id and user_id != self.allowed_user_id:
            await update.message.reply_text("⛔ No autorizado.")
            return
        
        text = update.message.text
        if not text:
            return
        
        if self._on_message_callback:
            try:
                # Ejecutar el callback en un hilo separado para no bloquear
                response = await asyncio.to_thread(self._on_message_callback, user_id, text)
                if response:
                    # Dividir mensajes largos
                    if len(response) > 4000:
                        for i in range(0, len(response), 4000):
                            await update.message.reply_text(response[i:i+4000])
                    else:
                        await update.message.reply_text(response)
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

    def start(self):
        """Inicia el bot de Telegram en un hilo separado"""
        if not self.token:
            print("[Telegram] ⚠️ No se proporcionó token de Telegram")
            return
        
        self.app = Application.builder().token(self.token).build()
        
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("status", self._status))
        self.app.add_handler(CommandHandler("help", self._start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        def run_polling():
            self._running = True
            print("[Telegram] 🤖 Bot iniciado. Esperando mensajes...")
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        
        thread = threading.Thread(target=run_polling, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False
        if self.app:
            self.app.stop()
            self.app = None

# ============================================================
# EJEMPLO DE USO
# ============================================================
if __name__ == "__main__":
    # Configurar desde variables de entorno o archivo .env
    # TELEGRAM_BOT_TOKEN=tu_token
    # TELEGRAM_ALLOWED_USER_ID=tu_user_id
    
    bridge = TelegramBridge()
    
    def on_message(user_id, text):
        return f"Recibí tu mensaje: '{text}'. (Simulado)"
    
    bridge.set_message_callback(on_message)
    bridge.start()
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()