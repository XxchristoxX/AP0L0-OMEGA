# src/ui/audio_devices_dialog.py
# ============================================================================
# SELECTOR DE DISPOSITIVOS DE AUDIO - Configurar micrófono y altavoces
# ============================================================================

import sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QPushButton, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class AudioDevicesDialog(QDialog):
    """Diálogo para seleccionar dispositivos de audio."""
    
    devices_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎧 Dispositivos de Audio")
        self.setMinimumSize(450, 280)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a1a;
                color: #c0c0c0;
            }
            QGroupBox {
                border: 1px solid #1a3a4a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                color: #00d4ff;
                font-weight: bold;
                font-family: 'Courier New', monospace;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QComboBox {
                background-color: #111122;
                border: 1px solid #1a3a4a;
                border-radius: 4px;
                padding: 6px 10px;
                color: #c0c0c0;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #2a5a6a;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #00d4ff;
                margin-right: 6px;
            }
            QPushButton {
                background-color: #1a2a3a;
                color: #00d4ff;
                border: 1px solid #2a4a5a;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-family: 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: #2a4a5a;
                border-color: #00d4ff;
            }
            QPushButton#cancel {
                color: #667788;
                border-color: #445566;
            }
            QPushButton#cancel:hover {
                background-color: #223344;
            }
            QLabel#info {
                color: #667788;
                font-size: 10px;
                font-family: 'Courier New', monospace;
            }
            QLabel#status {
                color: #00ff88;
                font-size: 11px;
                font-family: 'Courier New', monospace;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Título
        title = QLabel("🎧 CONFIGURACIÓN DE AUDIO")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00d4ff; font-family: 'Courier New';")
        layout.addWidget(title)
        
        # Micrófono
        mic_group = QGroupBox("🎤 MICRÓFONO")
        mic_layout = QVBoxLayout(mic_group)
        mic_layout.setSpacing(4)
        
        mic_hint = QLabel("Selecciona el dispositivo de entrada (micrófono)")
        mic_hint.setStyleSheet("color: #667788; font-size: 10px; font-family: 'Courier New';")
        mic_layout.addWidget(mic_hint)
        
        self.mic_combo = QComboBox()
        self.mic_combo.addItem("🔘 (Por defecto del sistema)", "")
        self._populate_devices(self.mic_combo, "input")
        mic_layout.addWidget(self.mic_combo)
        layout.addWidget(mic_group)
        
        # Altavoces
        speaker_group = QGroupBox("🔊 ALTAVOCES")
        speaker_layout = QVBoxLayout(speaker_group)
        speaker_layout.setSpacing(4)
        
        speaker_hint = QLabel("Selecciona el dispositivo de salida (altavoces/auriculares)")
        speaker_hint.setStyleSheet("color: #667788; font-size: 10px; font-family: 'Courier New';")
        speaker_layout.addWidget(speaker_hint)
        
        self.speaker_combo = QComboBox()
        self.speaker_combo.addItem("🔘 (Por defecto del sistema)", "")
        self._populate_devices(self.speaker_combo, "output")
        speaker_layout.addWidget(self.speaker_combo)
        layout.addWidget(speaker_group)
        
        # Estado
        status_layout = QHBoxLayout()
        status_label = QLabel("📌 Estado:")
        status_label.setStyleSheet("color: #667788; font-size: 10px; font-family: 'Courier New';")
        status_layout.addWidget(status_label)
        
        self.status_value = QLabel("Listo")
        self.status_value.setObjectName("status")
        status_layout.addWidget(self.status_value)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Info
        info_label = QLabel("ℹ️ Los cambios se aplicarán al reiniciar el asistente.")
        info_label.setObjectName("info")
        layout.addWidget(info_label)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        test_btn = QPushButton("🔊 PROBAR")
        test_btn.clicked.connect(self._test_audio)
        btn_layout.addWidget(test_btn)
        
        save_btn = QPushButton("💾 GUARDAR")
        save_btn.clicked.connect(self.save_devices)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("✕ CANCELAR")
        cancel_btn.setObjectName("cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self._load_saved_devices()
    
    def _populate_devices(self, combo, direction):
        """Llena el combo con los dispositivos disponibles."""
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                name = dev.get("name", f"Dispositivo {i}")
                if direction == "input" and dev.get("max_input_channels", 0) > 0:
                    combo.addItem(f"🎤 {name}", i)
                elif direction == "output" and dev.get("max_output_channels", 0) > 0:
                    combo.addItem(f"🔊 {name}", i)
        except Exception as e:
            print(f"[AudioDevices] Error al obtener dispositivos: {e}")
            self.status_value.setText("⚠️ Error al leer dispositivos")
            self.status_value.setStyleSheet("color: #ff4466; font-size: 11px;")
    
    def _load_saved_devices(self):
        """Carga los dispositivos guardados desde la configuración."""
        try:
            from src.core.config import _get_config
            config = _get_config()
            
            mic = config.get("mic_device", "")
            speakers = config.get("speaker_device", "")
            
            if mic:
                for i in range(self.mic_combo.count()):
                    if self.mic_combo.itemText(i) == mic:
                        self.mic_combo.setCurrentIndex(i)
                        break
            
            if speakers:
                for i in range(self.speaker_combo.count()):
                    if self.speaker_combo.itemText(i) == speakers:
                        self.speaker_combo.setCurrentIndex(i)
                        break
            
            if mic or speakers:
                self.status_value.setText("✅ Dispositivos cargados")
                self.status_value.setStyleSheet("color: #00ff88; font-size: 11px;")
        except Exception as e:
            print(f"[AudioDevices] Error cargando dispositivos: {e}")
    
    def _test_audio(self):
        """Prueba el audio con un sonido de prueba."""
        try:
            import numpy as np
            # Generar un tono de prueba
            duration = 0.5  # segundos
            frequency = 440  # Hz (La)
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration))
            wave = 0.5 * np.sin(2 * np.pi * frequency * t)
            
            # Reproducir
            sd.play(wave, sample_rate)
            sd.wait()
            
            self.status_value.setText("✅ Prueba de audio completada")
            self.status_value.setStyleSheet("color: #00ff88; font-size: 11px;")
        except Exception as e:
            self.status_value.setText(f"⚠️ Error en prueba: {str(e)[:50]}")
            self.status_value.setStyleSheet("color: #ff8844; font-size: 11px;")
    
    def save_devices(self):
        """Guarda los dispositivos seleccionados."""
        try:
            from src.core.config import _get_config, _save_config
            
            mic_text = self.mic_combo.currentText()
            speaker_text = self.speaker_combo.currentText()
            
            config = _get_config()
            
            # Guardar micrófono
            if mic_text and mic_text != "🔘 (Por defecto del sistema)":
                config["mic_device"] = mic_text
            else:
                config.pop("mic_device", None)
            
            # Guardar altavoces
            if speaker_text and speaker_text != "🔘 (Por defecto del sistema)":
                config["speaker_device"] = speaker_text
            else:
                config.pop("speaker_device", None)
            
            _save_config(config)
            
            self.status_value.setText("✅ Configuración guardada")
            self.status_value.setStyleSheet("color: #00ff88; font-size: 11px;")
            
            self.devices_changed.emit()
            
            QMessageBox.information(
                self,
                "Éxito",
                "Dispositivos de audio guardados correctamente.\n\nLos cambios se aplicarán al reiniciar el asistente."
            )
            
            self.accept()
            
        except Exception as e:
            self.status_value.setText(f"⚠️ Error: {str(e)[:50]}")
            self.status_value.setStyleSheet("color: #ff4466; font-size: 11px;")
            QMessageBox.warning(self, "Error", f"No se pudieron guardar los dispositivos:\n{str(e)}")