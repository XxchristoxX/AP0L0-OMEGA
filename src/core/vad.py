# src/core/vad.py
"""
Voice Activity Detection (VAD) - Simple energy-based y Adaptive VAD con detección de fin de turno.
"""

import math
import struct
import numpy as np
from typing import List, Dict


class SimpleVAD:
    """
    A very simple energy-based VAD (Voice Activity Detection).
    """
    def __init__(self, sample_rate=16000, frame_duration_ms=30, threshold=500):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.threshold = threshold
        self.speech_frames = 0
        self.silence_frames = 0
        self.is_speech = False

    def is_speech_frame(self, frame: bytes) -> bool:
        count = len(frame) // 2
        if count == 0:
            return False
        shorts = struct.unpack(f"{count}h", frame)
        sum_squares = sum(s * s for s in shorts)
        rms = math.sqrt(sum_squares / count)
        return rms > self.threshold

    def process_chunk(self, chunk: bytes) -> bool:
        return self.is_speech_frame(chunk)


class AdaptiveVAD:
    """
    Detector de actividad de voz adaptativo con detección de fin de turno.
    Se adapta al ruido de fondo y detecta cuándo el usuario ha terminado de hablar.
    """
    
    def __init__(self, sample_rate=16000, frame_duration_ms=30):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.silence_threshold = 0.02
        self.speech_threshold = 0.05
        self.silence_counter = 0
        self.speech_counter = 0
        self.min_speech_frames = 10
        self.min_silence_frames = 20
        self.is_speaking = False
        self._energy_history = []
        
    def process_chunk(self, chunk: bytes) -> Dict:
        audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio**2))
        
        self._energy_history.append(rms)
        if len(self._energy_history) > 100:
            self._energy_history.pop(0)
            
        if len(self._energy_history) > 20:
            background_noise = np.percentile(self._energy_history, 20)
            dynamic_threshold = max(0.01, background_noise * 3)
        else:
            dynamic_threshold = self.speech_threshold
            
        if rms > dynamic_threshold:
            self.silence_counter = 0
            self.speech_counter += 1
            if self.speech_counter > self.min_speech_frames:
                self.is_speaking = True
        else:
            self.speech_counter = 0
            if self.is_speaking:
                self.silence_counter += 1
                if self.silence_counter > self.min_silence_frames:
                    self.is_speaking = False
                    self.silence_counter = 0
                    return {"is_speech": False, "is_end_of_turn": True, "energy": rms}
        
        return {"is_speech": self.is_speaking, "is_end_of_turn": False, "energy": rms}