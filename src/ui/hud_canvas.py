# src/ui/hud_canvas.py
# =============================================================================
# HUD CANVAS - PANEL PRINCIPAL DE VISUALIZACIÓN
# =============================================================================
# Este archivo controla la apariencia del centro de la interfaz:
# - Fondo espacial (estrellas, nebulosas, planetas)
# - Anillos holográficos
# - Nodos de energía (los círculos pequeños alrededor del nombre)
# - Escáneres y pulsos
# - Nombre del asistente y estado
# - Waveform de audio
# =============================================================================
# ÁREAS DE PERSONALIZACIÓN (busca los comentarios "OPCIÓN:" para ajustar):
# - Tamaño y brillo de los nodos de energía
# - Colores de los nodos (personalidades o personalizados)
# - Tamaño y brillo de las estrellas
# - Anillos de pulso (grosor y opacidad)
# - Escáneres y velocidad de rotación
# =============================================================================

import math
import random
import time
import threading
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QMetaObject, Q_ARG, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QBrush, QLinearGradient, QPainter, QPen, QPixmap,
    QRadialGradient, QConicalGradient, QFont, QPainterPath
)
from PyQt6.QtWidgets import QWidget, QSizePolicy
try:
    from src.config.personality import DEFAULT_PERSONALITY
except ImportError:  # compatibilidad con ejecución antigua desde src/
    from config.personality import DEFAULT_PERSONALITY
from src.ui.ui_utils import C, qcol

# =============================================================================
# 1. ESTRELLAS DE FONDO
# =============================================================================
class _Star:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'twinkle_speed', 'twinkle_phase', 'color', 'layer')
    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.layer = random.choice([0, 0, 0, 1, 1, 2])
        # OPCIÓN: Ajusta el tamaño de las estrellas modificando estos valores
        # [capa0, capa1, capa2] - capa2 es la más brillante y grande
        self.radius = [random.uniform(0.2, 0.9), random.uniform(0.6, 1.8), random.uniform(1.2, 3.0)][self.layer]
        self.alpha = random.uniform(20, [150, 200, 255][self.layer])
        self.twinkle_speed = random.uniform(0.008, 0.06)
        self.twinkle_phase = random.uniform(0, math.pi * 2)
        self.color = random.choice([C.STAR, C.PRI, C.WHITE, C.COSMIC, C.AURORA, C.ENERGY])

# =============================================================================
# 2. NEBULOSAS VOLUMÉTRICAS
# =============================================================================
class _NebulaBlob:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'drift_x', 'drift_y', 'color', 'pulse')
    def __init__(self, w, h):
        self.x = random.uniform(-w * 0.1, w * 1.1)
        self.y = random.uniform(-h * 0.1, h * 1.1)
        self.radius = random.uniform(80, 260)
        self.alpha = random.uniform(8, 30)
        self.drift_x = random.uniform(-0.08, 0.08)
        self.drift_y = random.uniform(-0.06, 0.06)
        self.pulse = random.uniform(0, math.pi * 2)
        self.color = random.choice([C.NEBULA, C.NEBULA2, C.COSMIC, C.AURORA, C.PRI_GHO])

# =============================================================================
# 3. PLANETAS DE FONDO (DECORATIVOS)
# =============================================================================
class _Planet:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'ring_tilt', 'color', 'ring_color')
    def __init__(self, w, h, idx):
        positions = [
            (w * random.uniform(0.05, 0.20), h * random.uniform(0.05, 0.25)),
            (w * random.uniform(0.80, 0.95), h * random.uniform(0.05, 0.25)),
            (w * random.uniform(0.05, 0.18), h * random.uniform(0.70, 0.92)),
            (w * random.uniform(0.82, 0.95), h * random.uniform(0.70, 0.92)),
        ]
        self.x, self.y = positions[idx % len(positions)]
        self.radius = random.uniform(28, 55)
        self.alpha = random.uniform(55, 100)
        self.ring_tilt = random.uniform(0.18, 0.38)
        pc = random.choice(['blue', 'pink', 'purple', 'teal'])
        if pc == 'blue':
            self.color = QColor(10, 30, 80, 180)
            self.ring_color = QColor(0, 120, 255, 90)
        elif pc == 'pink':
            self.color = QColor(60, 5, 50, 180)
            self.ring_color = QColor(220, 0, 160, 90)
        elif pc == 'purple':
            self.color = QColor(30, 5, 60, 180)
            self.ring_color = QColor(140, 0, 255, 90)
        else:
            self.color = QColor(0, 40, 50, 180)
            self.ring_color = QColor(0, 200, 180, 90)

# =============================================================================
# 4. NODOS DE ENERGÍA (¡LOS CÍRCULOS PEQUEÑOS ALREDEDOR DEL NOMBRE!)
# =============================================================================
class _EnergyNode:
    __slots__ = ('theta', 'phi', 'speed_t', 'speed_p', 'radius', 'trail', 'alpha', 'color_frac')
    def __init__(self):
        self.theta = random.uniform(0, math.pi * 2)
        self.phi = random.uniform(0, math.pi)
        self.speed_t = random.uniform(0.004, 0.018) * random.choice([-1, 1])
        self.speed_p = random.uniform(0.002, 0.010) * random.choice([-1, 1])
        # ===================================================================
        # OPCIÓN: Tamaño de los nodos (radio en píxeles)
        # - Valores originales: 1.5 - 4.0
        # - Para hacerlos más visibles: 4.0 - 8.0 o 5.0 - 9.0
        # - Descomenta la segunda línea y comenta la primera para activar
        # ===================================================================
        self.radius = random.uniform(1.5, 4.0)
        # self.radius = random.uniform(5.0, 9.0)  # <--- NODOS MÁS GRANDES
        self.trail = []
        # ===================================================================
        # OPCIÓN: Brillo de los nodos (alpha)
        # - Original: 140 - 255
        # - Para más brillo: 200 - 255
        # ===================================================================
        self.alpha = random.uniform(140, 255)
        # self.alpha = random.uniform(200, 255)  # <--- NODOS MÁS BRILLANTES
        # ===================================================================
        # OPCIÓN: Color de los nodos
        # - Actualmente usa color_frac para decidir entre C.ENERGY o C.PRI
        # - Puedes cambiarlo para usar colores de las personalidades
        # - Ver la función _draw_energy_nodes más abajo para más opciones
        # ===================================================================
        self.color_frac = random.random()

# =============================================================================
# 5. DATA STREAMS (TEXTO EN LOS BORDES)
# =============================================================================
class _DataStream:
    __slots__ = ('x', 'y', 'speed', 'chars', 'alpha', 'col')
    _GLYPHS = "01<>[]{}|/\\+=ΩΔΨΦΞΛabcdef0123456789JARVAGATA"
    def __init__(self, W, H):
        self.x = random.choice([random.uniform(8, W * 0.12), random.uniform(W * 0.88, W - 8)])
        self.y = random.uniform(-H, 0)
        self.speed = random.uniform(0.8, 2.5)
        self.chars = [random.choice(self._GLYPHS) for _ in range(random.randint(6, 20))]
        self.alpha = random.uniform(30, 100)
        self.col = random.choice([C.PRI, C.ENERGY, C.GREEN])

# =============================================================================
# 6. ESTRELLAS FUGACES
# =============================================================================
class _ShootingStar:
    __slots__ = ('x', 'y', 'length', 'angle', 'speed', 'alpha', 'width')
    def __init__(self, W, H):
        self.x = random.uniform(-W * 0.2, W * 1.2)
        self.y = random.uniform(-H * 0.1, H * 0.5)
        self.length = random.uniform(60, 200)
        self.angle = random.uniform(-0.4, 0.2)
        self.speed = random.uniform(8, 20)
        self.alpha = 1.0
        self.width = random.uniform(0.8, 2.2)
    def dead(self, W, H):
        return self.alpha <= 0 or self.x > W + 200 or self.y > H + 200 or self.x < -200 or self.y < -200

# =============================================================================
# 7. CANVAS PRINCIPAL (HudCanvas)
# =============================================================================
class HudCanvas(QWidget):
    def __init__(self, face_path: str, assistant_name: str = "APOLO", personality: str = DEFAULT_PERSONALITY, parent=None):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("HudCanvas debe crearse en el hilo principal")
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self.persona  = personality
        self._assistant_name = assistant_name
        self._face_path = face_path

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._energy     = 55.0
        self._tgt_energy = 55.0
        self._last_t     = time.time()

        self._ring_angles = [0.0, 72.0, 144.0, 216.0, 288.0]
        self._ring_speeds = [0.45, -0.30, 0.70, -0.55, 0.25]
        self._ring_tilts  = [0.0, 0.35, 0.60, -0.25, 0.80]

        self._scan   = 0.0
        self._scan2  = 180.0
        self._scan3  = 90.0

        self._pulses = [0.0, 60.0, 120.0]
        self._blink      = True
        self._blink_tick = 0
        self._burst = []
        self._face_px = None
        self._load_face(face_path)

        self._stars = []
        self._blobs = []
        self._planets = []
        self._nodes = []
        self._streams = []
        self._shooting = []
        self._shoot_cd = 0
        self._stream_cd = 0
        self._init_space(1200, 900)

        self._hex_phase = 0.0
        self._name_glow = 0.0
        self._name_glow_dir = 1.0

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def reload_face(self, path: str):
        self._face_path = path
        self._load_face(path)
        self.update()

    def _init_space(self, w, h):
        self._stars   = [_Star(w, h) for _ in range(400)]
        self._blobs   = [_NebulaBlob(w, h) for _ in range(14)]
        self._planets = [_Planet(w, h, i) for i in range(4)]
        # ===================================================================
        # OPCIÓN: Número de nodos de energía
        # - Original: 30 nodos
        # - Para más densidad: 50 o 60
        # ===================================================================
        self._nodes   = [_EnergyNode() for _ in range(30)]
        # self._nodes   = [_EnergyNode() for _ in range(50)]  # <--- MÁS NODOS
        self._streams = []
        self._shooting = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._init_space(event.size().width(), event.size().height())

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    @pyqtSlot(bool)
    def _set_animations_enabled_impl(self, enabled: bool):
        if enabled:
            self._tmr.start(16)
        else:
            self._tmr.stop()

    def set_animations_enabled(self, enabled: bool):
        if threading.current_thread() is threading.main_thread():
            self._set_animations_enabled_impl(enabled)
        else:
            QMetaObject.invokeMethod(
                self,
                "_set_animations_enabled_impl",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(bool, enabled)
            )

    def _step(self):
        self._tick += 1
        now = time.time()
        W, H = self.width(), self.height()

        # ===================================================================
        # OPCIÓN: Sensibilidad de la animación al hablar
        # - Los valores de _tgt_scale y _tgt_energy controlan la amplitud
        # - Aumentar los rangos para más movimiento al hablar
        # ===================================================================
        if now - self._last_t > (0.10 if self.speaking else 0.45):
            if self.speaking:
                self._tgt_scale  = random.uniform(1.04, 1.12)
                self._tgt_energy = random.uniform(180, 255)
            elif self.muted:
                self._tgt_scale  = random.uniform(0.998, 1.002)
                self._tgt_energy = random.uniform(12, 24)
            else:
                self._tgt_scale  = random.uniform(1.002, 1.010)
                self._tgt_energy = random.uniform(60, 100)
            self._last_t = now

        sp = 0.40 if self.speaking else 0.12
        self._scale  += (self._tgt_scale  - self._scale)  * sp
        self._energy += (self._tgt_energy - self._energy) * sp

        spk_mult = 2.8 if self.speaking else 1.0
        for i in range(len(self._ring_angles)):
            self._ring_angles[i] = (self._ring_angles[i] + self._ring_speeds[i] * spk_mult) % 360

        sc_spd = 2.8 if self.speaking else 1.1
        self._scan  = (self._scan  + sc_spd) % 360
        self._scan2 = (self._scan2 - sc_spd * 0.7) % 360
        self._scan3 = (self._scan3 + sc_spd * 1.4) % 360

        fw = min(W, H)
        lim = fw * 0.80
        ps  = 3.5 if self.speaking else 1.6
        self._pulses = [r + ps for r in self._pulses if r + ps < lim]
        if len(self._pulses) < 4 and random.random() < (0.10 if self.speaking else 0.030):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.32:
            cx2, cy2 = W / 2, H / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.26
            spd = random.uniform(1.2, 3.0)
            self._burst.append([
                cx2 + math.cos(ang) * r_s, cy2 + math.sin(ang) * r_s,
                math.cos(ang) * spd, math.sin(ang) * spd - 0.3, 1.0, random.random(),
            ])
        self._burst = [
            [b[0]+b[2], b[1]+b[3], b[2]*0.96, b[3]*0.96, b[4]-0.025, b[5]]
            for b in self._burst if b[4] > 0
        ]

        spk_n = 3.0 if self.speaking else 1.0
        for nd in self._nodes:
            nd.theta = (nd.theta + nd.speed_t * spk_n) % (math.pi * 2)
            nd.phi   = (nd.phi   + nd.speed_p * spk_n) % math.pi
            nd.trail.append((nd.theta, nd.phi))
            if len(nd.trail) > 12:
                nd.trail.pop(0)

        for blob in self._blobs:
            blob.x += blob.drift_x
            blob.y += blob.drift_y
            blob.pulse = (blob.pulse + 0.008) % (math.pi * 2)
            if blob.x < -300: blob.x = W + 300
            elif blob.x > W + 300: blob.x = -300
            if blob.y < -300: blob.y = H + 300
            elif blob.y > H + 300: blob.y = -300

        self._shoot_cd -= 1
        if self._shoot_cd <= 0 and random.random() < (0.030 if self.speaking else 0.010):
            self._shooting.append(_ShootingStar(W, H))
            self._shoot_cd = random.randint(30, 140)
        for s in self._shooting:
            s.x += s.speed * math.cos(s.angle)
            s.y += s.speed * math.sin(s.angle)
            s.alpha -= 0.018
        self._shooting = [s for s in self._shooting if not s.dead(W, H)]

        self._stream_cd -= 1
        if self._stream_cd <= 0 and len(self._streams) < 12:
            self._streams.append(_DataStream(W, H))
            self._stream_cd = random.randint(20, 80)
        for st in self._streams:
            st.y += st.speed
        self._streams = [st for st in self._streams if st.y < H + 200]

        self._hex_phase = (self._hex_phase + 0.012 * (2.0 if self.speaking else 1.0)) % (math.pi * 2)

        self._name_glow += 0.04 * self._name_glow_dir
        if self._name_glow > 1.0: self._name_glow_dir = -1.0
        elif self._name_glow < 0.0: self._name_glow_dir = 1.0

        self._blink_tick += 1
        if self._blink_tick >= 35:
            self._blink = not self._blink
            self._blink_tick = 0

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # 1. Deep space background
        bg_grad = QRadialGradient(QPointF(cx, cy), fw * 0.9)
        bg_grad.setColorAt(0.0, QColor(C.BG_DEEP))
        bg_grad.setColorAt(0.5, QColor(C.BG))
        bg_grad.setColorAt(1.0, QColor(C.BG_DEEP))
        p.fillRect(self.rect(), QBrush(bg_grad))

        # 2. Volumetric nebulae
        for blob in self._blobs:
            pulse_a = blob.alpha * (0.75 + 0.25 * math.sin(blob.pulse))
            g = QRadialGradient(QPointF(blob.x, blob.y), blob.radius)
            col = QColor(blob.color); col.setAlpha(int(pulse_a))
            g.setColorAt(0.0, col)
            mid = QColor(blob.color); mid.setAlpha(int(pulse_a * 0.4))
            g.setColorAt(0.5, mid)
            g.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(blob.x - blob.radius, blob.y - blob.radius, blob.radius * 2, blob.radius * 2))

        # 3. Background planets with rings
        for planet in self._planets:
            pg = QRadialGradient(QPointF(planet.x - planet.radius * 0.28, planet.y - planet.radius * 0.28), planet.radius)
            lc = QColor(planet.color); lc.setAlpha(int(planet.alpha * 1.4))
            dc = QColor(planet.color); dc.setAlpha(int(planet.alpha * 0.6))
            pg.setColorAt(0.0, lc); pg.setColorAt(0.7, planet.color); pg.setColorAt(1.0, dc)
            p.setBrush(QBrush(pg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(planet.x - planet.radius, planet.y - planet.radius, planet.radius * 2, planet.radius * 2))
            rw = planet.radius * 2.2; rh = planet.radius * planet.ring_tilt
            p.setPen(QPen(planet.ring_color, planet.radius * 0.22)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(planet.x - rw / 2, planet.y - rh / 2, rw, rh))
            atm = QRadialGradient(QPointF(planet.x, planet.y), planet.radius * 1.35)
            ac = QColor(planet.ring_color); ac.setAlpha(30)
            atm.setColorAt(0.6, QColor(0, 0, 0, 0)); atm.setColorAt(1.0, ac)
            p.setBrush(QBrush(atm)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(planet.x - planet.radius * 1.35, planet.y - planet.radius * 1.35, planet.radius * 2.7, planet.radius * 2.7))

        # 4. Multi-layer stars
        # ===================================================================
        # OPCIÓN: Brillo de las estrellas
        # - La línea comentada multiplica el brillo por 1.5 para hacerlas más visibles
        # ===================================================================
        for star in self._stars:
            flicker = 0.50 + 0.50 * math.sin(self._tick * star.twinkle_speed + star.twinkle_phase)
            a = max(8, min(255, int(star.alpha * flicker)))
            # a = max(8, min(255, int(star.alpha * flicker * 1.5)))  # <--- ESTRELLAS MÁS BRILLANTES
            if star.layer == 2 and a > 160:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(star.color, a // 3)))
                p.drawEllipse(QPointF(star.x, star.y), star.radius * 2.5, star.radius * 2.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(star.color, a)))
            p.drawEllipse(QPointF(star.x, star.y), star.radius, star.radius)

        # 5. Shooting stars
        for s in self._shooting:
            a = int(s.alpha * 220)
            if a <= 0: continue
            ex, ey = s.x, s.y
            sx2 = ex - math.cos(s.angle) * s.length
            sy2 = ey - math.sin(s.angle) * s.length
            grad = QLinearGradient(QPointF(ex, ey), QPointF(sx2, sy2))
            grad.setColorAt(0.0, QColor(220, 240, 255, a))
            grad.setColorAt(0.3, qcol(C.PRI, a // 2))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(QPen(QBrush(grad), s.width))
            p.drawLine(QPointF(ex, ey), QPointF(sx2, sy2))

        # 6. Data streams on edges
        font_ds = QFont("Courier New", 7)
        p.setFont(font_ds)
        for st in self._streams:
            for ci, ch in enumerate(st.chars):
                fade = max(0, 1.0 - ci / len(st.chars))
                a = int(st.alpha * fade * (0.5 + 0.5 * math.sin(self._tick * 0.05 + ci)))
                p.setPen(QPen(qcol(st.col, a), 1))
                p.drawText(QPointF(st.x, st.y - ci * 11), ch)

        # 7. Central glow cloud
        r_orb = fw * 0.28
        for i in range(10, 0, -1):
            r = r_orb * (2.2 - i * 0.15)
            frc = i / 10
            a = max(0, min(255, int(self._energy * 0.22 * frc)))
            if self.persona == "agata":
                nc = QColor(int(50 * frc), 0, int(40 * frc), a)
            else:
                nc = QColor(0, int(12 * frc), int(50 * frc), a)
            p.setBrush(QBrush(nc)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # 8. Hex grid on orb
        self._draw_hex_grid(p, cx, cy, r_orb * 0.92)

        # 9. Holographic orbital rings (5 rings)
        # ===================================================================
        # OPCIÓN: Anillos orbitales
        # - ring_cfgs: (radio_relativo, grosor, longitud_arco, espacio)
        # - Aumentar grosor (w_r) o longitud de arco (arc_l) para más visibilidad
        # ===================================================================
        ring_cfgs = [
            (0.52, 4.2, 100, 60),
            (0.44, 2.8,  75, 50),
            (0.36, 2.0,  55, 38),
            (0.60, 1.4,  40, 80),
            (0.28, 1.2,  35, 28),
        ]
        ring_cols = [C.PRI, C.ENERGY, C.PRI_DIM, C.COSMIC, C.RING1]
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(ring_cfgs):
            ring_r = fw * r_frac
            base   = self._ring_angles[idx]
            tilt   = self._ring_tilts[idx]
            a_val  = max(0, min(255, int(self._energy * (1.0 - idx * 0.12))))
            col_h  = C.MUTED_C if self.muted else ring_cols[idx]
            col    = qcol(col_h, a_val)
            p.save()
            p.translate(cx, cy)
            p.scale(1.0, 0.30 + 0.25 * abs(math.sin(tilt + self._tick * 0.003)))
            p.translate(-cx, -cy)
            p.setPen(QPen(col, w_r, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            angle = base
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap
            p.restore()

        # 10. Energy nodes on orb surface
        # ===================================================================
        # OPCIÓN: Nodos de energía (los círculos pequeños)
        # - Ver la función _draw_energy_nodes para ajustar colores y tamaños
        # ===================================================================
        self._draw_energy_nodes(p, cx, cy, r_orb)

        # 11. Radial pulse rings
        # ===================================================================
        # OPCIÓN: Anillos de pulso (los que se expanden desde el centro)
        # - w_pr: grosor del anillo (3.0 original, 6.0 para más grueso)
        # - a: opacidad (200 original, 255 para más brillante)
        # - Descomenta las líneas comentadas para activar los valores mejorados
        # ===================================================================
        for pr in self._pulses:
            frac = pr / (fw * 0.80)
            a = max(0, int(200 * (1.0 - frac)))
            w_pr = max(0.5, 3.0 * (1.0 - frac))
            # a = max(0, int(255 * (1.0 - frac)))   # <--- PULSOS MÁS BRILLANTES
            # w_pr = max(1.0, 6.0 * (1.0 - frac))   # <--- PULSOS MÁS GRUESOS
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, w_pr)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # 12. Scanners
        sr = fw * 0.56
        sa = min(255, int(self._energy * 1.8))
        ex_arc = 90 if self.speaking else 52
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 3.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(srect, int(self._scan * 16), int(ex_arc * 16))
        s2c = QColor(C.COSMIC); s2c.setAlpha(sa // 2)
        p.setPen(QPen(s2c, 2.0)); p.drawArc(srect, int(self._scan2 * 16), int(ex_arc * 16))
        s3c = QColor(C.ENERGY); s3c.setAlpha(sa // 3)
        p.setPen(QPen(s3c, 1.5)); p.drawArc(srect, int(self._scan3 * 16), int(ex_arc * 16))

        # 13. Tick dial
        t_out, t_in = fw * 0.535, fw * 0.510
        for deg in range(0, 360, 3):
            rad = math.radians(deg)
            major = (deg % 30 == 0)
            inn = t_in if major else t_in + (t_out - t_in) * 0.55
            p.setPen(QPen(qcol(C.PRI if major else C.STAR, 230 if major else 55), 1.5 if major else 0.7))
            p.drawLine(QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                       QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)))

        # 14. Crosshair
        ch_r, gap_h = fw * 0.56, fw * 0.20
        p.setPen(QPen(qcol(C.PRI, int(self._energy * 0.55)), 1.2))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # 15. Corner brackets
        bl = 38
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        for bx, by, dx, dy in [(hl, ht, 1, 1), (hr, ht, -1, 1), (hl, hb, 1, -1), (hr, hb, -1, -1)]:
            p.setPen(QPen(qcol(C.PRI, 240), 2.8))
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))
            inner = int(bl * 0.38)
            p.setPen(QPen(qcol(C.ENERGY, 110), 1.2))
            p.drawLine(QPointF(bx + dx * (bl - inner), by + dy * (bl - inner)),
                       QPointF(bx + dx * bl, by + dy * (bl - inner)))
            p.drawLine(QPointF(bx + dx * (bl - inner), by + dy * (bl - inner)),
                       QPointF(bx + dx * (bl - inner), by + dy * bl))

        # 16. Orb core (rostro o núcleo energético)
        # ===================================================================
        # OPCIÓN: Núcleo central
        # - Si tienes face.png, se muestra la imagen
        # - Si no, se dibuja el núcleo energético (ahora comentado)
        # - Para ocultar el núcleo por completo, comenta también el bloque if
        # ===================================================================
        if self._face_px:
            fsz = int(fw * 0.58 * self._scale)
            scaled = self._face_px.scaled(fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        # else:
        #     self._draw_energy_core(p, cx, cy, fw)  # <--- Comentado para ocultar el círculo de energía

        # 17. Burst particles
        for pt in self._burst:
            a = max(0, min(255, int(pt[4] * 255)))
            col_b = C.ENERGY if pt[5] > 0.5 else C.PRI
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(col_b, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 3.0, 3.0)

        # 18. AI name with glow
        display_name = self._assistant_name.upper()
        glow_a = int(80 + 120 * self._name_glow)
        for gi in range(4, 0, -1):
            gc = qcol(C.PRI, glow_a // (gi + 1))
            p.setFont(QFont("Courier New", 16 + gi, QFont.Weight.Bold))
            p.setPen(QPen(gc, 1))
            p.drawText(QRectF(cx - 100 - gi, cy - 16 - gi, 200 + gi * 2, 32 + gi * 2),
                       Qt.AlignmentFlag.AlignCenter, display_name)
        p.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE, min(255, int(self._energy * 2.2))), 1))
        p.drawText(QRectF(cx - 100, cy - 16, 200, 32), Qt.AlignmentFlag.AlignCenter, display_name)

        # 19. Status
        sy = cy + fw * 0.40
        if self.muted:            txt, col_s = "[ X ]  SILENCIADO",  qcol(C.MUTED_C)
        elif self.speaking:       txt, col_s = "[ O ]  HABLANDO",    qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "<>" if self._blink else "><"
            txt, col_s = f"{sym}  PENSANDO",    qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = ">>" if self._blink else "<<"
            txt, col_s = f"{sym}  PROCESANDO",  qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "[*]" if self._blink else "[ ]"
            txt, col_s = f"{sym}  ESCUCHANDO",  qcol(C.GREEN)
        else:
            sym = "[-]" if self._blink else "[=]"
            txt, col_s = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col_s, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # 20. Waveform
        wy = sy + 34
        N, bw = 54, 6
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C, 120)
            elif self.speaking:
                hgt = random.randint(2, 30)
                frac = hgt / 30
                cl = qcol(C.ENERGY if frac > 0.65 else C.PRI, 160 + int(95 * frac))
            else:
                hgt = int(3 + 4 * math.sin(self._tick * 0.07 + i * 0.55))
                cl = qcol(C.BORDER_B, 140)
            p.fillRect(QRectF(wx0 + i * bw, wy + 22 - hgt, bw - 2, hgt), cl)

    # =========================================================================
    # FUNCIÓN: DIBUJAR HEXÁGONOS (FONDO DEL NÚCLEO)
    # =========================================================================
    def _draw_hex_grid(self, p: QPainter, cx: float, cy: float, orb_r: float):
        hex_size = orb_r * 0.14
        cols = int(orb_r / hex_size) * 2 + 2
        for row in range(-cols, cols + 1):
            for col in range(-cols, cols + 1):
                hx = col * hex_size * 1.732
                hy = row * hex_size * 1.5 + (col % 2) * hex_size * 0.75
                dist = math.sqrt(hx * hx + hy * hy)
                if dist > orb_r * 0.95: continue
                depth_frac = 1.0 - dist / orb_r
                pulse = 0.5 + 0.5 * math.sin(self._hex_phase + dist * 0.04)
                a = int(depth_frac * pulse * 45)
                if a < 4: continue
                p.setPen(QPen(qcol(C.PRI, a), 0.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                pts = [QPointF(cx + hx + hex_size * 0.45 * math.cos(math.radians(60 * k - 30)),
                               cy + hy + hex_size * 0.45 * math.sin(math.radians(60 * k - 30)))
                       for k in range(6)]
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]: path.lineTo(pt)
                path.closeSubpath()
                p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)

    # =========================================================================
    # FUNCIÓN: DIBUJAR NODOS DE ENERGÍA (CÍRCULOS PEQUEÑOS ALREDEDOR DEL NOMBRE)
    # =========================================================================
    def _draw_energy_nodes(self, p: QPainter, cx: float, cy: float, orb_r: float):
        for nd in self._nodes:
            sin_phi = math.sin(nd.phi)
            nx = cx + orb_r * sin_phi * math.cos(nd.theta)
            ny = cy + orb_r * sin_phi * math.sin(nd.theta) * 0.40
            depth = math.cos(nd.phi)
            if depth < -0.1: continue
            frac = (depth + 1) / 2
            a_nd = int(nd.alpha * frac)

            # =================================================================
            # OPCIÓN: COLOR DE LOS NODOS
            # - Actual: usa C.ENERGY o C.PRI según color_frac
            # - Para usar colores de las 5 personalidades, reemplaza con:
            #   personality_colors = ["#00d4ff", "#ff6b9d", "#ff6b00", "#9b59b6", "#00ff88"]
            #   idx = int(nd.color_frac * len(personality_colors)) % len(personality_colors)
            #   col_nd = personality_colors[idx]
            # - O puedes usar colores fijos como "#FFD700" (dorado)
            # =================================================================
            col_nd = C.ENERGY if nd.color_frac > 0.5 else C.PRI
            # col_nd = "#FF6B6B" if nd.color_frac > 0.5 else "#4ECDC4"  # <--- EJEMPLO: ROJO/VERDE

            # =================================================================
            # OPCIÓN: TRAIL (RASTRO) DE LOS NODOS
            # - Multiplicador 0.6 (original) o 0.9 (más largo)
            # - Descomenta la segunda línea para un rastro más largo
            # =================================================================
            for ti, (tt, tp) in enumerate(nd.trail[:-1]):
                trail_frac = ti / max(1, len(nd.trail))
                ta = int(a_nd * trail_frac * 0.5)
                if ta < 5: continue
                tx = cx + orb_r * math.sin(tp) * math.cos(tt)
                ty = cy + orb_r * math.sin(tp) * math.sin(tt) * 0.40
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(col_nd, ta)))
                p.drawEllipse(QPointF(tx, ty), nd.radius * trail_frac * 0.6, nd.radius * trail_frac * 0.6)
                # p.drawEllipse(QPointF(tx, ty), nd.radius * trail_frac * 0.9, nd.radius * trail_frac * 0.9)  # <--- RASTRO MÁS LARGO

            # =================================================================
            # OPCIÓN: TAMAÑO DEL NODO PRINCIPAL
            # - Actual: nd.radius * 1.0 (original) o * 1.8 (más grande)
            # - El resplandor exterior usa nd.radius * 2.5
            # - Aumenta estos valores para nodos más grandes
            # =================================================================
            p.setPen(Qt.PenStyle.NoPen)
            # Resplandor exterior
            p.setBrush(QBrush(qcol(col_nd, min(255, a_nd // 3))))
            p.drawEllipse(QPointF(nx, ny), nd.radius * 2.5, nd.radius * 2.5)
            # Nodo principal
            p.setBrush(QBrush(qcol(col_nd, a_nd)))
            p.drawEllipse(QPointF(nx, ny), nd.radius, nd.radius)
            # Si quieres nodos más grandes, reemplaza la línea de arriba con:
            # p.drawEllipse(QPointF(nx, ny), nd.radius * 1.8, nd.radius * 1.8)

    # =========================================================================
    # FUNCIÓN: DIBUJAR NÚCLEO DE ENERGÍA (CUANDO NO HAY ROSTRO)
    # =========================================================================
    def _draw_energy_core(self, p: QPainter, cx: float, cy: float, fw: float):
        r_core = int(fw * 0.24 * self._scale)
        for i in range(12, 0, -1):
            r2 = int(r_core * i / 12); frc = i / 12
            a = max(0, min(255, int(self._energy * 1.2 * frc)))
            color_outer = QColor(C.PRI)
            color_outer.setAlpha(a)
            p.setBrush(QBrush(color_outer))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
        ig = QRadialGradient(QPointF(cx, cy), r_core * 0.5)
        color_inner = QColor(C.WHITE)
        color_inner.setAlpha(min(255, int(self._energy * 2)))
        ig.setColorAt(0.0, color_inner)
        color_mid = QColor(C.PRI)
        color_mid.setAlpha(int(self._energy))
        ig.setColorAt(0.4, color_mid)
        ig.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(ig)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - r_core * 0.5, cy - r_core * 0.5, r_core, r_core))
