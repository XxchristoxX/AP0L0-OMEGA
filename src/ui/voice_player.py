# src/ui/voice_player.py
import os
import io
import random
import threading
import asyncio
import edge_tts
import sounddevice as sd
import soundfile as sf
from PIL import Image, ImageTk
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import re
from typing import Optional

def normalize_punctuation(text: str) -> str:
    text = re.sub(r'\.\s+', ', ', text)
    text = re.sub(r'!\s+', ', ', text)
    text = re.sub(r'\?\s+', ', ', text)

    if text.endswith("."):
        text = text[:-1]

    return text.strip()

class VoiceImagePlayer:
    def __init__(self, face_path, size=(760, 760)):
        self.root = tk.Tk()
        self.root.title("F.A.I.T.H")
        self.root.resizable(False, False)
        self.root.geometry("760x900")

        self.fixed_size = size

        self.face_original = Image.open(face_path).resize(self.fixed_size, Image.LANCZOS)
        self.face_label = tk.Label(self.root, bg="#001f4d", borderwidth=0, highlightthickness=0)
        self.face_label.place(relx=0.5, rely=0.4, anchor="center")

        self.scale = 1.0
        self.playing = False

        self.text_box = ScrolledText(
            self.root,
            fg="#00ffff",
            bg="#001f4d",
            insertbackground="#00ffff",
            height=12,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            padx=10,
            pady=10
        )
        
        self.text_box.place(relx=0.5, rely=0.85, anchor="center")

        self.animate()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def on_close(self):
        os._exit(0)

    def write_log(self, text):
        self.text_box.configure(state="normal")
        self.text_box.insert(tk.END, text + "\n")
        self.text_box.see(tk.END)
        self.text_box.configure(state="disabled")

    def start_animation(self):
        self.playing = True

    def stop_animation(self):
        self.playing = False

    def animate(self):
        if self.playing:
            self.scale += random.uniform(-0.015, 0.02)
            self.scale = min(max(self.scale, 1.02), 1.10)
        else:
            if abs(self.scale - 1.0) < 0.003:
                self.scale = 1.0
            elif self.scale > 1.0:
                self.scale -= 0.009
            else:
                self.scale += 0.005

        base_w, base_h = self.fixed_size
        new_size = (int(base_w * self.scale), int(base_h * self.scale))
        resized = self.face_original.resize(new_size, Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        self.face_label.configure(image=tk_img)
        self.face_label.image = tk_img

        self.root.after(50, self.animate)

VOICE = "en-GB-OllieMultilingualNeural"

def edge_speak(text: str, img_player: Optional[VoiceImagePlayer] = None, voice: str = VOICE):
    """
    Reproduce texto usando Edge TTS. Si se proporciona un img_player, activa la animación.
    """
    if not text.strip():
        return

    optimized_text = normalize_punctuation(text)

    def _thread_target():
        async def _speak():
            communicate = edge_tts.Communicate(
                optimized_text,
                voice,
                pitch="+2Hz",
                rate="+8%"
            )

            audio_buffer = bytearray()
            first_audio_received = False

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
                    if not first_audio_received:
                        first_audio_received = True
                        if img_player:
                            img_player.start_animation()

            wav_bytes = io.BytesIO(audio_buffer)

            try:
                data, samplerate = sf.read(wav_bytes, dtype="float32")
            except Exception as e:
                print("Decode error:", e)
                return

            sd.play(data, samplerate)
            sd.wait()
            if img_player:
                img_player.stop_animation()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_speak())
        loop.close()

    threading.Thread(target=_thread_target, daemon=True).start()