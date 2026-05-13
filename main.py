"""
GridScope v4.0 — Industrial SCADA Dashboard
Dammam Substation A  |  IEC 61850  |  Open Source  |  MIT
"""

import sys, random, math, csv, os, json
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QGridLayout, QComboBox, QLineEdit,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QToolTip,
    QGraphicsObject, QSlider, QDialog, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject, QMargins
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
from PyQt6.QtCharts import QChart, QChartView, QValueAxis, QSplineSeries

# ── Event Bus ─────────────────────────────────────────────────────────────────
class EventBus(QObject):
    alarm_selected  = pyqtSignal(dict)
    replay_tick     = pyqtSignal(int)
BUS = EventBus()

# ── Theme ─────────────────────────────────────────────────────────────────────
DARK  = {"bg":"#090B10","surface":"#10131C","surface2":"#181D2B","surface3":"#1E2438",
         "border":"#252B40","border2":"#303860","accent":"#00E5B4","accent2":"#4DA6FF",
         "warn":"#FFB547","danger":"#FF4D4D","text":"#E8ECF4","text_dim":"#5A6380",
         "text_mid":"#8A94B0","highlight":"#00E5B418"}
T = dict(DARK)
def set_theme(dark): T.clear(); T.update(DARK)  # dark-only

# ── Data ──────────────────────────────────────────────────────────────────────
TAGS = {
    "FLOW_A": {"label":"Flow Rate",  "unit":"L/min","val":72.4,"min":0,"max":120,"hi":100,"lo":20, "icon":"⟳"},
    "PRES_B": {"label":"Pressure",   "unit":"bar",  "val":4.21,"min":0,"max":10, "hi":8,  "lo":0.5,"icon":"◈"},
    "TEMP_C": {"label":"Temperature","unit":"°C",   "val":82.5,"min":0,"max":150,"hi":120,"lo":10, "icon":"▲"},
    "VIB_D":  {"label":"Vibration",  "unit":"mm/s", "val":1.83,"min":0,"max":10, "hi":5,  "lo":0,  "icon":"≋"},
    "POWER_E":{"label":"Power Draw", "unit":"kW",   "val":45.2,"min":0,"max":100,"hi":90, "lo":0,  "icon":"⚡"},
    "LEVEL_F":{"label":"Tank Level", "unit":"%",    "val":61.0,"min":0,"max":100,"hi":90, "lo":10, "icon":"▣"},
}
IED_DEVICES = [
    {"id":"IED-PLC01","name":"Main PLC",      "type":"plc",   "status":"online", "ip":"10.0.1.10","protocol":"IEC 61850 MMS","bay":"Bay-1","firmware":"v3.2.1","cpu":42,"latency":2, "packets":102,"last_alarm":"09:22","x":340,"y":55, "parents":[]},
    {"id":"IED-RTU01","name":"RTU-01",         "type":"rtu",   "status":"online", "ip":"10.0.1.11","protocol":"Modbus TCP",  "bay":"Bay-2","firmware":"v1.9.4","cpu":18,"latency":4, "packets":64, "last_alarm":"08:55","x":140,"y":195,"parents":["IED-PLC01"]},
    {"id":"IED-HMI01","name":"HMI Station",    "type":"hmi",   "status":"online", "ip":"10.0.1.12","protocol":"OPC-UA",     "bay":"Bay-1","firmware":"v4.1.0","cpu":31,"latency":1, "packets":88, "last_alarm":"08:44","x":540,"y":195,"parents":["IED-PLC01"]},
    {"id":"IED-PMP01","name":"Feed Pump A",    "type":"pump",  "status":"online", "ip":"10.0.1.20","protocol":"GOOSE",      "bay":"Bay-2","firmware":"v2.0.3","cpu":12,"latency":3, "packets":47, "last_alarm":"07:30","x":80, "y":330,"parents":["IED-RTU01"]},
    {"id":"IED-PMP02","name":"Feed Pump B",    "type":"pump",  "status":"warning","ip":"10.0.1.21","protocol":"GOOSE",      "bay":"Bay-2","firmware":"v2.0.3","cpu":67,"latency":8, "packets":39, "last_alarm":"09:38","x":260,"y":330,"parents":["IED-RTU01"]},
    {"id":"IED-SEN01","name":"Flow Sensor",    "type":"sensor","status":"online", "ip":"10.0.1.30","protocol":"IEC 61850",  "bay":"Bay-3","firmware":"v1.3.0","cpu":5, "latency":2, "packets":120,"last_alarm":"07:00","x":80, "y":460,"parents":["IED-PMP01"]},
    {"id":"IED-SEN02","name":"Pressure Sensor","type":"sensor","status":"fault",  "ip":"10.0.1.31","protocol":"IEC 61850",  "bay":"Bay-3","firmware":"v1.3.0","cpu":0, "latency":99,"packets":0,  "last_alarm":"09:41","x":260,"y":460,"parents":["IED-PMP02"]},
    {"id":"IED-SEN03","name":"Temp Sensor",    "type":"sensor","status":"online", "ip":"10.0.1.32","protocol":"IEC 61850",  "bay":"Bay-4","firmware":"v1.3.0","cpu":4, "latency":2, "packets":110,"last_alarm":"Never","x":460,"y":460,"parents":["IED-HMI01"]},
    {"id":"IED-VLV01","name":"Control Valve",  "type":"valve", "status":"online", "ip":"10.0.1.40","protocol":"Modbus RTU", "bay":"Bay-4","firmware":"v1.1.2","cpu":8, "latency":5, "packets":33, "last_alarm":"08:55","x":620,"y":460,"parents":["IED-HMI01"]},
]
CORRELATION_MAP = {
    "IED-SEN02":["IED-SEN02","IED-PMP02","IED-RTU01","IED-PLC01"],
    "IED-PMP02":["IED-PMP02","IED-RTU01","IED-PLC01"],
    "IED-PLC01":["IED-PLC01","IED-HMI01"],
    "IED-VLV01":["IED-VLV01","IED-HMI01"],
    "IED-HMI01":["IED-HMI01","IED-PLC01"],
    "IED-PMP01":["IED-PMP01","IED-SEN01","IED-RTU01"],
    "IED-SEN01":["IED-SEN01","IED-PMP01"],
}
ALARM_DATA = [
    {"id":1,"time":"09:41:22","tag":"IED-SEN02","msg":"Pressure sensor fault — GOOSE timeout","sev":"fault",  "ack":False,"bay":"Bay-3"},
    {"id":2,"time":"09:38:05","tag":"IED-PMP02","msg":"Vibration threshold exceeded (4.8 mm/s)","sev":"warning","ack":False,"bay":"Bay-2"},
    {"id":3,"time":"09:22:14","tag":"IED-PLC01","msg":"MMS scan cycle overrun >200ms",          "sev":"warning","ack":True, "bay":"Bay-1"},
    {"id":4,"time":"08:55:00","tag":"IED-VLV01","msg":"Actuator response delay >500ms",         "sev":"warning","ack":True, "bay":"Bay-4"},
    {"id":5,"time":"08:44:30","tag":"IED-HMI01","msg":"OPC-UA session timeout recovered",       "sev":"info",   "ack":True, "bay":"Bay-1"},
    {"id":6,"time":"08:11:10","tag":"IED-PMP01","msg":"Motor start sequence completed OK",      "sev":"info",   "ack":True, "bay":"Bay-2"},
    {"id":7,"time":"07:55:01","tag":"IED-SEN01","msg":"Flow low limit reached (18 L/min)",      "sev":"warning","ack":True, "bay":"Bay-3"},
    {"id":8,"time":"07:30:44","tag":"IED-PLC01","msg":"Watchdog timer reset — Bay-1",           "sev":"fault",  "ack":True, "bay":"Bay-1"},
]
AUDIT_DATA = [
    {"time":"09:41:00","user":"operator1","role":"Operator","action":"Acknowledged alarm on IED-SEN02",        "ip":"10.0.1.14","sev":"warning","tag":"IED-SEN02"},
    {"time":"09:35:12","user":"engineer1","role":"Engineer","action":"Changed setpoint on IED-PLC01 to 85%",   "ip":"10.0.1.22","sev":"info",   "tag":"IED-PLC01"},
    {"time":"09:20:00","user":"operator2","role":"Operator","action":"Opened IED-VLV01 (GOOSE command sent)",  "ip":"10.0.1.31","sev":"info",   "tag":"IED-VLV01"},
    {"time":"09:05:44","user":"admin",    "role":"Admin",   "action":"Granted write access to engineer1",      "ip":"10.0.0.1", "sev":"warning","tag":""},
    {"time":"08:50:15","user":"operator1","role":"Operator","action":"Emergency stop triggered — Bay-2 cleared","ip":"10.0.1.14","sev":"fault",  "tag":"IED-PMP02"},
    {"time":"08:30:00","user":"engineer2","role":"Engineer","action":"Firmware v1.3.0 pushed to IED-SEN02",    "ip":"10.0.1.9", "sev":"info",   "tag":"IED-SEN02"},
    {"time":"08:10:00","user":"operator1","role":"Operator","action":"Login — session started",                "ip":"10.0.1.14","sev":"info",   "tag":""},
    {"time":"07:59:00","user":"admin",    "role":"Admin",   "action":"System config backup created (rev 44)",  "ip":"10.0.0.1", "sev":"info",   "tag":""},
]
REPLAY_EVENTS = [
    {"step":0,"label":"T+0:00  Normal operation",   "statuses":{"IED-SEN02":"online","IED-PMP02":"online"}, "alarm_id":None},
    {"step":1,"label":"T+0:30  GOOSE latency spike","statuses":{"IED-SEN02":"warning","IED-PMP02":"online"},"alarm_id":None},
    {"step":2,"label":"T+1:00  Sensor timeout",     "statuses":{"IED-SEN02":"fault","IED-PMP02":"online"},  "alarm_id":1},
    {"step":3,"label":"T+1:30  Vibration rises",    "statuses":{"IED-SEN02":"fault","IED-PMP02":"warning"}, "alarm_id":2},
    {"step":4,"label":"T+2:00  Alarms generated",   "statuses":{"IED-SEN02":"fault","IED-PMP02":"warning"}, "alarm_id":2},
    {"step":5,"label":"T+2:30  Operator responds",  "statuses":{"IED-SEN02":"fault","IED-PMP02":"warning"}, "alarm_id":1},
    {"step":6,"label":"T+3:00  Fault isolated",     "statuses":{"IED-SEN02":"fault","IED-PMP02":"online"},  "alarm_id":None},
]

# ── Data Engine ───────────────────────────────────────────────────────────────
class DataEngine(QObject):
    updated = pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self._tags = {k: dict(v) for k,v in TAGS.items()}
        self._hist  = {k: [v["val"]]*100 for k,v in TAGS.items()}
        t = QTimer(); t.timeout.connect(self._tick); t.start(1000)
    def _tick(self):
        for k,d in self._tags.items():
            # Visible drift — 5% range per second
            drift = (random.random()-0.48) * (d["max"]-d["min"]) * 0.05
            d["val"] = max(d["min"], min(d["max"], d["val"] + drift))
            self._hist[k].append(round(d["val"],2))
            if len(self._hist[k])>200: self._hist[k].pop(0)
        self.updated.emit(self.snapshot())
    def snapshot(self):
        return {k:{**d,"history":list(self._hist[k])} for k,d in self._tags.items()}

# ── UI Primitives ─────────────────────────────────────────────────────────────
STATUS_COLORS = {"online":"#00E5B4","warning":"#FFB547","fault":"#FF4D4D","offline":"#5A6380"}
TYPE_LABELS   = {"plc":"PLC","rtu":"RTU","hmi":"HMI","pump":"PMP","sensor":"SEN","valve":"VLV","breaker":"BRK"}

def lbl(text, size=11, bold=False, color=None):
    w = QLabel(text)
    w.setFont(QFont("Consolas", max(8, size), QFont.Weight.Bold if bold else QFont.Weight.Normal))
    w.setStyleSheet(f"color:{color or T['text']};")
    return w

def hdivider():
    f = QFrame(); f.setFixedHeight(1); f.setStyleSheet(f"background:{T['border']};"); return f

def ghost_btn(text, color=None):
    col = color or T["accent"]
    b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QPushButton{{background:transparent;color:{col};border:1px solid {col}55;"
                    f"border-radius:6px;font-family:Consolas;font-size:10px;padding:5px 14px;}}"
                    f"QPushButton:hover{{background:{col}18;border-color:{col};}}")
    return b

def solid_btn(text, color=None):
    col = color or T["accent"]
    b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QPushButton{{background:{col}22;color:{col};border:1px solid {col};"
                    f"border-radius:6px;font-family:Consolas;font-size:10px;font-weight:bold;padding:5px 14px;}}"
                    f"QPushButton:hover{{background:{col}44;}}")
    return b

def table_style():
    return (f"QTableWidget{{background:{T['surface']};color:{T['text']};gridline-color:{T['border']};"
            f"border:none;font-family:Consolas;font-size:12px;}}"
            f"QHeaderView::section{{background:{T['surface2']};color:{T['text_dim']};border:none;"
            f"padding:9px 8px;font-family:Consolas;font-size:10px;letter-spacing:1px;}}"
            f"QTableWidget::item{{padding:9px 8px;}}"
            f"QTableWidget::item:alternate{{background:{T['surface2']};}}"
            f"QTableWidget::item:selected{{background:{T['highlight']};color:{T['accent']};}}")

class Card(QFrame):
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T["border"]),1)); p.setBrush(QBrush(QColor(T["surface"])))
        p.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),10,10)

class MiniSpark(QWidget):
    def __init__(self,hist,color="#00E5B4",h=32):
        super().__init__(); self.hist=hist; self.color=color; self.setFixedHeight(h)
    def set(self,h): self.hist=h; self.update()
    def paintEvent(self,e):
        if len(self.hist)<2: return
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); data=self.hist[-50:]
        mn,mx=min(data),max(data); rng=max(mx-mn,0.001); path=QPainterPath()
        for i,v in enumerate(data):
            x=i/(len(data)-1)*w; y=h-(v-mn)/rng*(h-4)-2
            path.moveTo(x,y) if i==0 else path.lineTo(x,y)
        p.setPen(QPen(QColor(self.color),1.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)

class GaugeRing(QWidget):
    def __init__(self,tag,data):
        super().__init__(); self.tag=tag; self.data=data; self.setFixedSize(138,138)
    def set(self,d): self.data=d; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); cx,cy=w//2,h//2; r=min(w,h)//2-10
        d=self.data; pct=(d["val"]-d["min"])/max(1,d["max"]-d["min"])
        hi_pct=(d["hi"]-d["min"])/max(1,d["max"]-d["min"])
        p.setPen(QPen(QColor(T["surface3"]),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(cx-r,cy-r,r*2,r*2,225*16,-270*16)
        col=QColor(T["danger"] if pct>=hi_pct else T["warn"] if pct>=hi_pct*0.82 else T["accent"])
        p.setPen(QPen(col,9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(cx-r,cy-r,r*2,r*2,225*16,int(-270*16*pct))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col)); p.drawEllipse(cx-3,cy-3,6,6)
        p.setFont(QFont("Consolas",15,QFont.Weight.Bold)); p.setPen(QColor(T["text"]))
        p.drawText(QRectF(cx-38,cy-14,76,22),Qt.AlignmentFlag.AlignCenter,f"{d['val']:.1f}")
        p.setFont(QFont("Consolas",9)); p.setPen(QColor(T["text_dim"]))
        p.drawText(QRectF(cx-38,cy+6,76,14),Qt.AlignmentFlag.AlignCenter,d["unit"])
        p.setFont(QFont("Consolas",8,QFont.Weight.Bold)); p.setPen(QColor(T["text_mid"]))
        p.drawText(QRectF(0,h-16,w,14),Qt.AlignmentFlag.AlignCenter,f"{d.get('icon','')}  {self.tag}")

# ── Side Panel (right-aligned tool window) ────────────────────────────────────
class SlidePanel(QDialog):
    """Right-side detail panel as a frameless tool window docked to parent."""
    def __init__(self, title, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self._open = False
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"QDialog{{background:{T['surface2']};border-left:2px solid {T['border2']};}}")
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        # Header
        hdr = QWidget(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{T['surface3']};border-bottom:1px solid {T['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,12,0)
        tl = QLabel(title); tl.setFont(QFont("Consolas",11,QFont.Weight.Bold))
        tl.setStyleSheet(f"color:{T['text']};"); hl.addWidget(tl); hl.addStretch()
        close = QPushButton("✕ Close"); close.setFixedHeight(28)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T['text_dim']};border:1px solid {T['border']};"
            f"border-radius:5px;font-family:Consolas;font-size:9px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{T['danger']};border-color:{T['danger']};}}")
        close.clicked.connect(self.hide_panel); hl.addWidget(close); root.addWidget(hdr)
        # Scrollable body
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{T['surface2']};}}"
            f"QScrollBar:vertical{{background:{T['surface2']};width:4px;border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{T['border']};border-radius:2px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        self._content = QWidget(); self._content.setStyleSheet(f"background:{T['surface2']};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(18,16,18,16); self._content_layout.setSpacing(12)
        scroll.setWidget(self._content); root.addWidget(scroll)

    def content_layout(self): return self._content_layout

    def _reposition(self):
        p = self.parent()
        if not p: return
        geo = p.frameGeometry()
        x = geo.x() + geo.width() - self.width()
        y = geo.y() + p.frameGeometry().height() - p.geometry().height() + 52
        h = p.geometry().height() - 52 - 24
        self.setFixedHeight(max(h, 200))
        self.move(x, y)

    def show_panel(self):
        if not self._open:
            self._open = True; self._reposition(); self.show(); self.raise_()

    def hide_panel(self):
        self._open = False; self.hide()

    def toggle(self):
        self.hide_panel() if self._open else self.show_panel()

# ── Replay Modal ──────────────────────────────────────────────────────────────
class ReplayModal(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0; self._playing = False
        self.setWindowTitle("Event Replay — IED-SEN02 GOOSE Timeout")
        self.setFixedSize(560, 520)
        self.setStyleSheet(f"QDialog{{background:{T['bg']};border:1px solid {T['border2']};}}")
        root = QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(16)

        # Title
        trow = QHBoxLayout()
        trow.addWidget(lbl("EVENT REPLAY",13,bold=True))
        trow.addStretch()
        badge = QLabel("  Bay-3 / Bay-2 Cascade  ")
        badge.setStyleSheet(f"QLabel{{background:{T['danger']}22;color:{T['danger']};border:1px solid {T['danger']}55;"
                            f"border-radius:6px;font-family:Consolas;font-size:9px;font-weight:bold;}}")
        trow.addWidget(badge); root.addLayout(trow)
        root.addWidget(lbl("09:38 – 09:41  ·  IED-SEN02 → IED-PMP02 → IED-RTU01",9,color=T["text_dim"]))
        root.addWidget(hdivider())

        # Step list
        self._step_labels = []
        for ev in REPLAY_EVENTS:
            row = QHBoxLayout(); row.setSpacing(12)
            dot = QLabel("○"); dot.setFixedWidth(14); dot.setFont(QFont("Consolas",11))
            dot.setStyleSheet(f"color:{T['text_dim']};"); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt = QLabel(ev["label"]); txt.setFont(QFont("Consolas",10))
            txt.setStyleSheet(f"color:{T['text_dim']};")
            row.addWidget(dot); row.addWidget(txt); row.addStretch()
            self._step_labels.append((dot,txt)); root.addLayout(row)

        root.addWidget(hdivider())

        # Scrubber
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0,len(REPLAY_EVENTS)-1); self._slider.setValue(0)
        self._slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{T['border']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{background:{T['accent']};border:none;width:14px;height:14px;margin:-5px 0;border-radius:7px;}}"
            f"QSlider::sub-page:horizontal{{background:{T['accent']};border-radius:2px;}}")
        self._slider.valueChanged.connect(self._scrub); root.addWidget(self._slider)

        # Current event label
        self._ev_lbl = QLabel("")
        self._ev_lbl.setFont(QFont("Consolas",10,QFont.Weight.Bold))
        self._ev_lbl.setStyleSheet(f"color:{T['warn']};"); root.addWidget(self._ev_lbl)

        # Controls
        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        self._play_btn = solid_btn("▶  Play", T["accent"])
        self._play_btn.setFixedWidth(110); self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)
        rst = ghost_btn("↺ Reset", T["text_dim"]); rst.setFixedWidth(80)
        rst.clicked.connect(self._reset); ctrl.addWidget(rst)
        ctrl.addStretch()
        self._step_lbl = lbl("Step 0 / 6",9,color=T["text_dim"]); ctrl.addWidget(self._step_lbl)
        root.addLayout(ctrl)

        self._timer = QTimer(); self._timer.timeout.connect(self._auto_step); self._timer.setInterval(1800)
        self._update_ui()

    def _scrub(self,v): self._step=v; BUS.replay_tick.emit(v); self._update_ui()
    def _toggle_play(self):
        self._playing = not self._playing
        self._play_btn.setText("⏸  Pause" if self._playing else "▶  Play")
        self._timer.start() if self._playing else self._timer.stop()
    def _auto_step(self):
        if self._step >= len(REPLAY_EVENTS)-1:
            self._playing=False; self._play_btn.setText("▶  Play"); self._timer.stop(); return
        self._step+=1; self._slider.setValue(self._step); BUS.replay_tick.emit(self._step); self._update_ui()
    def _reset(self):
        self._playing=False; self._play_btn.setText("▶  Play"); self._timer.stop()
        self._step=0; self._slider.setValue(0); BUS.replay_tick.emit(0); self._update_ui()
    def _update_ui(self):
        self._step_lbl.setText(f"Step {self._step} / {len(REPLAY_EVENTS)-1}")
        ev = REPLAY_EVENTS[self._step]
        self._ev_lbl.setText(f"→  {ev['label']}")
        for i,(dot,txt) in enumerate(self._step_labels):
            if i<self._step:   dot.setText("●"); dot.setStyleSheet(f"color:{T['accent']};"); txt.setStyleSheet(f"color:{T['text']};font-family:Consolas;font-size:10px;")
            elif i==self._step: dot.setText("◉"); dot.setStyleSheet(f"color:{T['warn']};font-size:13px;"); txt.setStyleSheet(f"color:{T['warn']};font-family:Consolas;font-size:10px;font-weight:bold;")
            else:               dot.setText("○"); dot.setStyleSheet(f"color:{T['text_dim']};"); txt.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:10px;")
    def closeEvent(self,e): self._timer.stop(); super().closeEvent(e)

# ── Top Bar ───────────────────────────────────────────────────────────────────
class TopBar(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedHeight(52)
        r=QHBoxLayout(self); r.setContentsMargins(20,0,20,0); r.setSpacing(0)
        logo=QLabel("GRID<span style='color:#00E5B4'>SCOPE</span>")
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setFont(QFont("Consolas",16,QFont.Weight.Bold)); logo.setStyleSheet(f"color:{T['text']};")
        r.addWidget(logo)
        sep=QLabel("  |  "); sep.setStyleSheet(f"color:{T['border2']};font-family:Consolas;font-size:14px;")
        r.addWidget(sep)
        site=QLabel("Dammam Substation A"); site.setFont(QFont("Consolas",11))
        site.setStyleSheet(f"color:{T['text_mid']};"); r.addWidget(site)
        r.addSpacing(28)
        self._conn=QLabel("● CONNECTED"); self._conn.setFont(QFont("Consolas",9))
        self._conn.setStyleSheet(f"color:{T['accent']}; letter-spacing:1px;"); r.addWidget(self._conn)
        r.addSpacing(20)
        self._alarm_badge=QLabel(); self._set_alarm(2); r.addWidget(self._alarm_badge)
        r.addStretch()

        self._clock=QLabel(); self._clock.setFont(QFont("Consolas",12,QFont.Weight.Bold))
        self._clock.setStyleSheet(f"color:{T['text']};"); r.addWidget(self._clock)
        r.addSpacing(20)
        user=QLabel("operator1"); user.setFont(QFont("Consolas",9))
        user.setStyleSheet(f"color:{T['text_mid']};"); r.addWidget(user)

        t=QTimer(self); t.timeout.connect(self._tick); t.start(1000); self._tick()
        # Heartbeat blink every 2s
        ht=QTimer(self); ht.timeout.connect(self._heartbeat); ht.start(2000)
        self._conn_bright = True
    def _tick(self): self._clock.setText(datetime.now().strftime("%H:%M:%S"))
    def _heartbeat(self):
        self._conn_bright = not self._conn_bright
        col = T["accent"] if self._conn_bright else T["border2"]
        self._conn.setStyleSheet(f"color:{col}; letter-spacing:1px;")

    def _set_alarm(self,n):
        col=T["danger"] if n>0 else T["text_dim"]
        label = f"{n} ACTIVE" if n>0 else "NO ALARMS"
        self._alarm_badge.setText(label)
        self._alarm_badge.setFont(QFont("Consolas",9,QFont.Weight.Bold))
        self._alarm_badge.setStyleSheet(f"color:{col};background:{col}18;border:1px solid {col}44;border-radius:6px;padding:4px 12px;letter-spacing:1px;")


    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(T["bg"]))
        p.setPen(QPen(QColor(T["border"]),1)); p.drawLine(0,self.height()-1,self.width(),self.height()-1)

# ── OVERVIEW TAB ──────────────────────────────────────────────────────────────
class OverviewTab(QWidget):
    def __init__(self,engine):
        super().__init__(); self.engine=engine; self._build(); engine.updated.connect(self._on_update)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(14)
        snap=self.engine.snapshot()
        # KPI row — clean, 6 cards
        krow=QHBoxLayout(); krow.setSpacing(10); self._kpis={}
        for lt,val,col in [("OEE","87.4%",T["accent"]),("Uptime","99.1%",T["accent"]),
                            ("Active Alarms","2",T["danger"]),
                            ("Avg Temp",f"{snap['TEMP_C']['val']:.1f}°C",T["warn"]),
                            ("Total Flow",f"{snap['FLOW_A']['val']:.1f} L/min",T["accent2"]),
                            ("Power",f"{snap['POWER_E']['val']:.0f} kW",T["text_mid"])]:
            c=Card(); c.setFixedHeight(84)
            cl=QVBoxLayout(c); cl.setContentsMargins(16,12,16,12); cl.setSpacing(4)
            cl.addWidget(lbl(lt.upper(),9,color=T["text_dim"]))
            v=QLabel(val)
            v.setFont(QFont("Consolas",22,QFont.Weight.Bold)); v.setStyleSheet(f"color:{col};")
            cl.addWidget(v); self._kpis[lt]=v; krow.addWidget(c)
        root.addLayout(krow)
        # Gauges + trend — two column
        mid=QHBoxLayout(); mid.setSpacing(14)
        gc=Card(); gc.setFixedWidth(310); gl=QVBoxLayout(gc); gl.setContentsMargins(14,14,14,14); gl.setSpacing(10)
        gl.addWidget(lbl("PROCESS VALUES",9,bold=True,color=T["text_dim"]))
        gg=QGridLayout(); gg.setSpacing(4); self._gauges={}
        for i,(tag,d) in enumerate(snap.items()):
            g=GaugeRing(tag,d); self._gauges[tag]=g; gg.addWidget(g,i//2,i%2)
        gl.addLayout(gg); mid.addWidget(gc)
        tc=Card(); cl2=QVBoxLayout(tc); cl2.setContentsMargins(14,14,14,14); cl2.setSpacing(10)
        hdr=QHBoxLayout(); hdr.addWidget(lbl("TREND",9,bold=True,color=T["text_dim"])); hdr.addStretch()
        self._combo=QComboBox(); self._combo.addItems(list(snap.keys())); self._combo.setFixedWidth(110)
        self._combo.setStyleSheet(f"QComboBox{{background:{T['surface2']};color:{T['text']};border:1px solid {T['border']};"
            f"border-radius:6px;padding:4px 8px;font-family:Consolas;font-size:10px;}}"
            f"QComboBox::drop-down{{border:none;}}QComboBox QAbstractItemView{{"
            f"background:{T['surface2']};color:{T['text']};selection-background-color:{T['highlight']};}}")
        self._combo.currentTextChanged.connect(self._rebuild_chart); hdr.addWidget(self._combo); cl2.addLayout(hdr)
        self._chart=QChart(); self._chart.setBackgroundBrush(QBrush(QColor(T["surface"])))
        self._chart.setMargins(QMargins(4,4,4,4)); self._chart.legend().hide()
        self._series=QSplineSeries(); self._series.setPen(QPen(QColor(T["accent"]),2))
        self._ax=QValueAxis(); self._ax.setLabelsVisible(False)
        self._ax.setGridLineColor(QColor(T["border"])); self._ax.setLinePenColor(QColor(T["border"]))
        self._ay=QValueAxis(); self._ay.setLabelFormat("%.1f"); self._ay.setLabelsColor(QColor(T["text_mid"]))
        self._ay.setGridLineColor(QColor(T["border"])); self._ay.setLinePenColor(QColor(T["border"]))
        self._chart.addSeries(self._series); self._chart.addAxis(self._ax,Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._ay,Qt.AlignmentFlag.AlignLeft)
        self._series.attachAxis(self._ax); self._series.attachAxis(self._ay)
        cv=QChartView(self._chart); cv.setRenderHint(QPainter.RenderHint.Antialiasing)
        cv.setMinimumHeight(280); cl2.addWidget(cv)
        mid.addWidget(tc,1); root.addLayout(mid)
        self._rebuild_chart(list(snap.keys())[0])
    def _rebuild_chart(self,tag):
        snap=self.engine.snapshot()
        if tag not in snap: return
        hist=snap[tag]["history"][-80:]; self._series.clear()
        for i,v in enumerate(hist): self._series.append(i,v)
        mn,mx=min(hist),max(hist); pad=(mx-mn)*0.1 or 1
        self._ay.setRange(mn-pad,mx+pad); self._ax.setRange(0,len(hist)-1)
    def _on_update(self,snap):
        for tag,g in self._gauges.items():
            if tag in snap: g.set(snap[tag])
        self._rebuild_chart(self._combo.currentText())
        kv={
            "Avg Temp":  ("{:.1f}°C".format(snap["TEMP_C"]["val"]),   T["warn"]),
            "Total Flow":("{:.1f} L/min".format(snap["FLOW_A"]["val"]),T["accent2"]),
            "Power":     ("{:.0f} kW".format(snap["POWER_E"]["val"]),  T["text_mid"]),
        }
        for k,(val,col) in kv.items():
            if k in self._kpis:
                w = self._kpis[k]
                if w.text() != val:
                    w.setText(val)
                    w.setStyleSheet("color:#FFFFFF;")
                    QTimer.singleShot(130, lambda w=w,c=col: w.setStyleSheet("color:{};".format(c)))

# ── ALARMS TAB ────────────────────────────────────────────────────────────────
class AlarmTimeline(QWidget):
    def __init__(self,alarms):
        super().__init__(); self.alarms=alarms; self._sel=None; self.setFixedHeight(80)
        t=QTimer(self); t.timeout.connect(self.update); t.start(5000)  # repaints every 5s
    def set_selected(self,aid): self._sel=aid; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=self.width(),self.height(); p.fillRect(self.rect(),QColor(T["surface2"]))
        p.setPen(QPen(QColor(T["border2"]),1)); p.drawLine(24,h//2,w-24,h//2)
        now=datetime.now(); p.setFont(QFont("Consolas",7)); p.setPen(QColor(T["text_dim"]))
        for i in range(5):
            t=now-timedelta(hours=4-i); x=24+(w-48)*i//4; p.drawText(x-18,h-4,t.strftime("%H:%M"))
        SEV={"fault":T["danger"],"warning":T["warn"],"info":T["accent2"]}
        for a in self.alarms:
            try:
                t=datetime.strptime(a["time"],"%H:%M:%S").replace(year=now.year,month=now.month,day=now.day)
                ref=now.replace(hour=6,minute=0,second=0)
                ratio=max(0,min(1,(t-ref).total_seconds()/max((now-ref).total_seconds(),1)))
                x=int(24+(w-48)*ratio); col=QColor(SEV.get(a["sev"],T["text_dim"]))
                if a["ack"]: col.setAlpha(70)
                size=13 if a["sev"]=="fault" else 9 if a["sev"]=="warning" else 7
                if self._sel and a.get("id")==self._sel:
                    ring=QColor(col); ring.setAlpha(50)
                    p.setBrush(QBrush(ring)); p.setPen(QPen(col,1.5)); p.drawEllipse(x-size-5,h//2-size-5,size*2+10,size*2+10)
                p.setBrush(QBrush(col)); p.setPen(QPen(QColor(T["bg"]),1))
                p.drawEllipse(x-size//2,h//2-size//2,size,size)
            except Exception: pass
        # NOW marker — thin vertical line at right edge
        now_x = w - 26
        p.setPen(QPen(QColor(T["accent"]), 1, Qt.PenStyle.SolidLine))
        p.drawLine(now_x, 8, now_x, h-16)
        p.setFont(QFont("Consolas",7)); p.setPen(QColor(T["accent"]))
        p.drawText(now_x-10, h-4, "NOW")

class AlarmsTab(QWidget):
    def __init__(self, main_win):
        super().__init__(); self._alarms=[dict(a) for a in ALARM_DATA]
        self._main_win = main_win; self._build()
        BUS.replay_tick.connect(self._on_replay)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(14)
        # Header — minimal
        hdr=QHBoxLayout()
        faults=sum(1 for a in self._alarms if a["sev"]=="fault" and not a["ack"])
        warns=sum(1 for a in self._alarms if a["sev"]=="warning" and not a["ack"])
        for txt,col in [(f"⚡ {faults} Fault{'s' if faults!=1 else ''}",T["danger"]),
                        (f"▲ {warns} Warning{'s' if warns!=1 else ''}",T["warn"])]:
            pl=QLabel(f"  {txt}  ")
            pl.setStyleSheet(f"QLabel{{background:{col}18;color:{col};border:1px solid {col}44;"
                             f"border-radius:8px;padding:4px 12px;font-family:Consolas;font-size:10px;font-weight:bold;}}")
            hdr.addWidget(pl)
        hdr.addStretch()
        for sev,col in [("FAULT",T["danger"]),("WARNING",T["warn"]),("ALL",T["text_dim"])]:
            b=ghost_btn(sev,col); b.setFixedSize(76,28)
            b.clicked.connect(lambda _,s=sev.lower(): self._filter(s)); hdr.addWidget(b)
        ack_all=solid_btn("✓ Ack All",T["accent"]); ack_all.setFixedSize(82,28)
        ack_all.clicked.connect(self._ack_all); hdr.addWidget(ack_all)
        # Replay button
        replay_btn=ghost_btn("⏵ Replay Event",T["accent2"]); replay_btn.setFixedHeight(28)
        replay_btn.clicked.connect(self._open_replay); hdr.addWidget(replay_btn)
        root.addLayout(hdr)
        # Timeline
        tl_c=Card(); tll=QVBoxLayout(tl_c); tll.setContentsMargins(14,10,14,10); tll.setSpacing(4)
        tll.addWidget(lbl("TIMELINE  (last 4 hours)",8,color=T["text_dim"]))
        self._timeline=AlarmTimeline(self._alarms); tll.addWidget(self._timeline)
        root.addWidget(tl_c)
        # Hint
        hint=lbl("Select alarm → highlights correlated IEDs on Topology  ·  Double-click to acknowledge",8,color=T["text_dim"])
        root.addWidget(hint)
        # Table
        self._table=QTableWidget(len(self._alarms),5)
        self._table.setHorizontalHeaderLabels(["Time","Device","Severity","Message","Status"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True); self._table.setStyleSheet(table_style())
        self._table.cellClicked.connect(self._on_click); self._table.cellDoubleClicked.connect(self._ack_row)
        self._populate(self._alarms); root.addWidget(self._table,1)
    def _populate(self,data,hl_id=None):
        SEV={"fault":T["danger"],"warning":T["warn"],"info":T["accent2"]}
        self._table.setRowCount(len(data))
        for row,a in enumerate(data):
            col=SEV.get(a["sev"],T["text"]); dim=a["ack"]; is_sel=hl_id and a.get("id")==hl_id
            for c,val in enumerate([a["time"],a["tag"],a["sev"].upper(),a["msg"],"✓ ACK" if a["ack"] else "⚡ ACTIVE"]):
                item=QTableWidgetItem(val)
                if is_sel: item.setBackground(QColor(T["highlight"])); item.setForeground(QColor(T["accent"]))
                elif c==2: item.setForeground(QColor(col))
                elif c==4 and not a["ack"]: item.setForeground(QColor(T["danger"]))
                else: item.setForeground(QColor(T["text_dim"] if dim else T["text"]))
                self._table.setItem(row,c,item)
            self._table.setRowHeight(row,48)
    def _on_click(self,row,_):
        if row<len(self._alarms):
            a=self._alarms[row]; self._timeline.set_selected(a.get("id"))
            self._populate(self._alarms,hl_id=a.get("id")); BUS.alarm_selected.emit(a)
    def _on_replay(self,step):
        ev=REPLAY_EVENTS[step]
        if ev["alarm_id"]: self._populate(self._alarms,hl_id=ev["alarm_id"]); self._timeline.set_selected(ev["alarm_id"])
    def _open_replay(self):
        dlg=ReplayModal(self._main_win); dlg.exec()
    def _filter(self,sev):
        data=self._alarms if sev=="all" else [a for a in self._alarms if a["sev"]==sev]; self._populate(data)
    def _ack_all(self):
        for a in self._alarms: a["ack"]=True; self._populate(self._alarms)
    def _ack_row(self,row,_):
        if row<len(self._alarms): self._alarms[row]["ack"]=True; self._populate(self._alarms)

# ── TOPOLOGY TAB ──────────────────────────────────────────────────────────────
class DeviceNode(QGraphicsObject):
    clicked_sig=pyqtSignal(dict)
    def __init__(self,dev):
        super().__init__(); self.dev=dict(dev); self._blink=True; self._hl=False
        self._cpu=dev["cpu"]; self._pkt=dev["packets"]
        self.setPos(dev["x"],dev["y"]); self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        if dev["status"] in ("fault","warning"):
            t=QTimer(); t.timeout.connect(self._do_blink)
            t.start(500 if dev["status"]=="fault" else 1100); self._bt=t
    def _do_blink(self): self._blink=not self._blink; self.update()
    def set_highlight(self,on): self._hl=on; self.update()
    def set_status(self,s): self.dev["status"]=s; self.update()
    def tick(self):
        self._cpu=max(0,min(100,self._cpu+random.randint(-3,3)))
        self._pkt=max(0,self._pkt+random.randint(-5,5))
        self.update()
    def boundingRect(self): return QRectF(-60,-32,120,64)
    def paint(self,p,option,widget):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col=QColor(STATUS_COLORS[self.dev["status"]])
        if not self._blink: col.setAlpha(55)
        if self._hl:
            g=QColor(T["accent"]); g.setAlpha(40)
            p.setPen(QPen(QColor(T["accent"]),2)); p.setBrush(QBrush(g)); p.drawRoundedRect(-66,-38,132,76,12,12)
        elif self.dev["status"]=="fault":
            g=QColor(col); g.setAlpha(28); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawRoundedRect(-64,-36,128,72,12,12)
        p.setBrush(QBrush(QColor(T["surface2"]))); p.setPen(QPen(col,2 if self.dev["status"]!="online" or self._hl else 1))
        p.drawRoundedRect(-56,-28,112,56,8,8)
        p.setFont(QFont("Consolas",8,QFont.Weight.Bold)); p.setPen(col)
        p.drawText(QRectF(-56,-28,38,14),Qt.AlignmentFlag.AlignCenter,TYPE_LABELS.get(self.dev["type"],"DEV"))
        p.setFont(QFont("Consolas",9,QFont.Weight.Bold)); p.setPen(QColor(T["text"]))
        p.drawText(QRectF(-56,-14,112,14),Qt.AlignmentFlag.AlignCenter,self.dev["name"])
        p.setFont(QFont("Consolas",8)); p.setPen(QColor(T["text_dim"]))
        p.drawText(QRectF(-56,1,112,11),Qt.AlignmentFlag.AlignCenter,self.dev["id"])
        cpu_col=T["danger"] if self._cpu>80 else T["warn"] if self._cpu>60 else T["accent"]
        p.setPen(QColor(cpu_col)); p.setFont(QFont("Consolas",7))
        p.drawText(QRectF(-56,13,112,11),Qt.AlignmentFlag.AlignCenter,f"CPU {self._cpu}%  ·  {self.dev['latency']}ms")
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(44,-26,7,7)
    def hoverEnterEvent(self,e):
        self.setZValue(10)
        QToolTip.showText(e.screenPos(),
            f"<b style='font-family:Consolas'>{self.dev['name']}</b><br>"
            f"<span style='font-family:Consolas;font-size:10px'>"
            f"ID: {self.dev['id']}<br>IP: {self.dev['ip']}<br>Protocol: {self.dev['protocol']}<br>"
            f"Bay: {self.dev['bay']}<br>Firmware: {self.dev['firmware']}<br>"
            f"Latency: {self.dev['latency']}ms  ·  Last Alarm: {self.dev['last_alarm']}</span>")
    def hoverLeaveEvent(self,e): self.setZValue(0)
    def mousePressEvent(self,e): self.clicked_sig.emit(self.dev); super().mousePressEvent(e)

class FlowLine(QGraphicsItem):
    def __init__(self,p1,p2,active=True):
        super().__init__(); self.p1=p1; self.p2=p2; self.active=active; self._phase=0; self.setZValue(-1)
    def boundingRect(self):
        x1,y1=min(self.p1.x(),self.p2.x()),min(self.p1.y(),self.p2.y())
        x2,y2=max(self.p1.x(),self.p2.x()),max(self.p1.y(),self.p2.y())
        return QRectF(x1-6,y1-6,x2-x1+12,y2-y1+12)
    def advance(self,ph): self._phase=ph; self.update()
    def paint(self,p,option,widget):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col=QColor(T["accent"] if self.active else T["border"]); col.setAlpha(130 if self.active else 50)
        pen=QPen(col,1.5,Qt.PenStyle.DashLine); pen.setDashOffset(self._phase); p.setPen(pen); p.drawLine(self.p1,self.p2)
        dx=self.p2.x()-self.p1.x(); dy=self.p2.y()-self.p1.y(); length=math.hypot(dx,dy)
        if length<1: return
        ux,uy=dx/length,dy/length; mx,my=self.p1.x()+dx*0.58,self.p1.y()+dy*0.58
        arrow=QPolygonF([QPointF(mx+ux*7-uy*3.5,my+uy*7+ux*3.5),QPointF(mx,my),QPointF(mx+ux*7+uy*3.5,my+uy*7-ux*3.5)])
        p.setPen(QPen(col,1)); p.setBrush(QBrush(col)); p.drawPolygon(arrow)

class TopologyTab(QWidget):
    def __init__(self, main_win):
        super().__init__(); self._phase=0; self._main_win=main_win; self._build()
        BUS.alarm_selected.connect(self._on_alarm_selected)
        BUS.replay_tick.connect(self._on_replay)
        t=QTimer(self); t.timeout.connect(self._animate); t.start(55)
        t2=QTimer(self); t2.timeout.connect(self._live_tick); t2.start(900)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(12)
        hdr=QHBoxLayout(); hdr.addWidget(lbl("DEVICE TOPOLOGY",13,bold=True)); hdr.addStretch()
        for s,col in [("Online",T["accent"]),("Warning",T["warn"]),("Fault",T["danger"])]:
            l=QLabel(f"● {s}"); l.setStyleSheet(f"color:{col};font-family:Consolas;font-size:10px;"); hdr.addWidget(l)
        hdr.addSpacing(16)
        detail_btn = ghost_btn("IED Details →", T["accent2"]); detail_btn.setFixedHeight(28)
        detail_btn.clicked.connect(lambda: self._panel.toggle()); hdr.addWidget(detail_btn)
        root.addLayout(hdr)
        self._scene=QGraphicsScene(); self._scene.setBackgroundBrush(QBrush(QColor(T["surface"])))
        self._view=QGraphicsView(self._scene); self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setStyleSheet(f"border:1px solid {T['border']};border-radius:10px;background:{T['surface']};")
        root.addWidget(self._view,1)
        self._build_graph()
        # Slide panel for device details
        self._panel = SlidePanel("Device Details", self._main_win)
        self._panel_layout = self._panel.content_layout()
        self._panel_placeholder = lbl("Select an IED on the topology\nto view its details.",10,color=T["text_dim"])
        self._panel_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._panel_layout.addWidget(self._panel_placeholder)
        self._panel_layout.addStretch()
    def _build_graph(self):
        self._scene.clear(); self._nodes={}; self._flow_lines=[]
        for dev in IED_DEVICES:
            node=DeviceNode(dev); node.clicked_sig.connect(self._on_node_click)
            self._scene.addItem(node); self._nodes[dev["id"]]=node
        for dev in IED_DEVICES:
            for pid in dev["parents"]:
                if pid in self._nodes:
                    p1=self._nodes[pid].pos()+QPointF(0,32); p2=self._nodes[dev["id"]].pos()+QPointF(0,-32)
                    fl=FlowLine(p1,p2,dev["status"]!="offline"); self._scene.addItem(fl); self._flow_lines.append(fl)
    def _on_node_click(self,dev):
        self._fill_panel(dev); self._panel.show_panel()
    def _fill_panel(self,dev):
        while self._panel_layout.count():
            item=self._panel_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        col=STATUS_COLORS.get(dev["status"],T["text_dim"])
        self._panel_layout.addWidget(lbl(dev["name"],12,bold=True))
        pill=QLabel(f"  ● {dev['status'].upper()}  ")
        pill.setStyleSheet(f"QLabel{{background:{col}22;color:{col};border:1px solid {col}66;"
                           f"border-radius:8px;padding:3px 10px;font-family:Consolas;font-size:9px;font-weight:bold;}}")
        self._panel_layout.addWidget(pill); self._panel_layout.addWidget(hdivider())
        for k,v in [("ID",dev["id"]),("IP Address",dev["ip"]),("Protocol",dev["protocol"]),
                    ("Bay",dev["bay"]),("Firmware",dev["firmware"]),("CPU Load",f"{dev['cpu']}%"),
                    ("Latency",f"{dev['latency']}ms"),("Packets/sec",str(dev.get("packets","—"))),
                    ("Last Alarm",dev["last_alarm"])]:
            row=QHBoxLayout(); row.setSpacing(8)
            kl=QLabel(k); kl.setFixedWidth(90); kl.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:10px;")
            vl=QLabel(v); vl.setWordWrap(True); vl.setStyleSheet(f"color:{T['text']};font-family:Consolas;font-size:10px;font-weight:bold;")
            row.addWidget(kl); row.addWidget(vl,1); self._panel_layout.addLayout(row)
        self._panel_layout.addWidget(hdivider())
        self._panel_layout.addWidget(lbl("ALARM HISTORY",8,bold=True,color=T["text_dim"]))
        SEV={"fault":T["danger"],"warning":T["warn"],"info":T["accent2"]}
        corr=[a for a in ALARM_DATA if a["tag"]==dev["id"]]
        if corr:
            for a in corr[:4]:
                al=QLabel(f"● {a['time']}  {a['msg']}")
                al.setWordWrap(True); al.setStyleSheet(f"color:{SEV.get(a['sev'],T['text_dim'])};font-family:Consolas;font-size:9px;")
                self._panel_layout.addWidget(al)
        else: self._panel_layout.addWidget(lbl("No alarms recorded",9,color=T["text_dim"]))
        self._panel_layout.addStretch()
    def _on_alarm_selected(self,alarm):
        for node in self._nodes.values(): node.set_highlight(False)
        tag=alarm.get("tag","")
        for dev_id in CORRELATION_MAP.get(tag,[tag]):
            if dev_id in self._nodes: self._nodes[dev_id].set_highlight(True)
        dev_map={d["id"]:d for d in IED_DEVICES}
        if tag in dev_map: self._fill_panel(dev_map[tag]); self._panel.show_panel()
    def _on_replay(self,step):
        ev=REPLAY_EVENTS[step]
        for dev_id,status in ev["statuses"].items():
            if dev_id in self._nodes: self._nodes[dev_id].set_status(status)
    def _animate(self):
        self._phase=(self._phase+1)%20
        for fl in self._flow_lines: fl.advance(self._phase)
    def _live_tick(self):
        for node in self._nodes.values(): node.tick()

# ── ANALYTICS TAB ─────────────────────────────────────────────────────────────
class AnalyticsTab(QWidget):
    def __init__(self,engine,main_win):
        super().__init__(); self.engine=engine; self._main_win=main_win
        self._build(); engine.updated.connect(self._on_update)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(14)
        hdr=QHBoxLayout(); hdr.addWidget(lbl("ANALYTICS",13,bold=True)); hdr.addStretch()
        diag_btn=ghost_btn("Protocol & Diagnostics →",T["accent2"]); diag_btn.setFixedHeight(28)
        diag_btn.clicked.connect(lambda: self._diag_panel.toggle()); hdr.addWidget(diag_btn)
        root.addLayout(hdr)
        # 4 trend charts — clean, no clutter
        snap=self.engine.snapshot()
        TAG_CHART=[("FLOW_A","Flow Rate",T["accent"]),("PRES_B","Pressure",T["accent2"]),
                   ("TEMP_C","Temperature",T["warn"]),("VIB_D","Vibration",T["danger"])]
        grid=QGridLayout(); grid.setSpacing(12); self._cseries=[]
        for i,(tag,lab,col) in enumerate(TAG_CHART):
            card=Card(); cl=QVBoxLayout(card); cl.setContentsMargins(12,12,12,12); cl.setSpacing(6)
            h=QHBoxLayout(); h.addWidget(lbl(lab.upper(),8,bold=True,color=T["text_dim"])); h.addStretch()
            d=snap.get(tag,{}); vl=QLabel(f"{d.get('val',0):.1f} {d.get('unit','')}")
            vl.setFont(QFont("Consolas",12,QFont.Weight.Bold)); vl.setStyleSheet(f"color:{col};"); h.addWidget(vl); cl.addLayout(h)
            chart=QChart(); chart.setBackgroundBrush(QBrush(QColor(T["surface"]))); chart.setMargins(QMargins(2,2,2,2)); chart.legend().hide()
            series=QSplineSeries(); series.setPen(QPen(QColor(col),1.5))
            hist=snap[tag]["history"][-60:] if tag in snap else [0]*60
            for j,v in enumerate(hist): series.append(j,v)
            ax=QValueAxis(); ax.setLabelsVisible(False); ax.setGridLineColor(QColor(T["border"])); ax.setLinePenColor(QColor(T["border"]))
            ay=QValueAxis(); ay.setLabelFormat("%.1f"); ay.setLabelsColor(QColor(T["text_mid"]))
            ay.setGridLineColor(QColor(T["border"])); ay.setLinePenColor(QColor(T["border"]))
            mn,mx=min(hist),max(hist); pad=(mx-mn)*0.1 or 0.5; ay.setRange(mn-pad,mx+pad)
            chart.addSeries(series); chart.addAxis(ax,Qt.AlignmentFlag.AlignBottom); chart.addAxis(ay,Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(ax); series.attachAxis(ay)
            cv=QChartView(chart); cv.setRenderHint(QPainter.RenderHint.Antialiasing); cv.setMinimumHeight(180); cl.addWidget(cv)
            self._cseries.append((tag,series,ax,ay,vl,d.get("unit",""),col)); grid.addWidget(card,i//2,i%2)
        root.addLayout(grid,1)
        # Bottom: 2 insight warnings only (not the full list)
        irow=QHBoxLayout(); irow.setSpacing(10)
        for col,msg in [(T["danger"],"IED-SEN02 offline — no GOOSE response"),(T["warn"],"IED-PMP02 vibration +14% over 30 min — inspect")]:
            ic=Card(); il=QHBoxLayout(ic); il.setContentsMargins(14,10,14,10); il.setSpacing(10)
            il.addWidget(lbl("●",14,color=col))
            il.addWidget(lbl(msg,9,color=T["text_mid"]))
            il.addStretch(); irow.addWidget(ic)
        root.addLayout(irow)
        # Diagnostics slide panel
        self._diag_panel = SlidePanel("Advanced Diagnostics", self._main_win)
        dl = self._diag_panel.content_layout()
        dl.addWidget(lbl("AI INSIGHTS",9,bold=True,color=T["text_dim"])); dl.addWidget(hdivider())
        for sev,msg in [("danger","IED-SEN02 offline — no GOOSE response"),("danger","Vibration IED-PMP02 rising +14%"),
                        ("warn","Pressure instability — Bay-3"),("warn","IED-PMP02 — inspect within 48h"),
                        ("info","MMS sessions nominal: 3 active"),("info","GOOSE latency nominal Bay-1, Bay-4")]:
            col={"danger":T["danger"],"warn":T["warn"],"info":T["accent2"]}[sev]
            icon={"danger":"●","warn":"▲","info":"ℹ"}[sev]
            row=QHBoxLayout(); row.setSpacing(8)
            d=QLabel(icon); d.setFixedWidth(12); d.setStyleSheet(f"color:{col};font-size:11px;")
            tx=QLabel(msg); tx.setWordWrap(True); tx.setStyleSheet(f"color:{T['text_mid']};font-family:Consolas;font-size:9px;")
            row.addWidget(d); row.addWidget(tx,1); dl.addLayout(row)
        dl.addSpacing(10); dl.addWidget(lbl("IEC 61850 PROTOCOL",9,bold=True,color=T["text_dim"])); dl.addWidget(hdivider())
        for k,v,col in [("GOOSE Subscribers","12",T["accent"]),("MMS Sessions","3",T["accent"]),
                        ("SV Streams","2",T["accent2"]),("RCB Health","OK",T["accent"]),
                        ("Report Blocks","4/4",T["accent"]),("GOOSE Timeout","IED-SEN02",T["danger"]),
                        ("Last MMS Poll","0.3s ago",T["text_mid"]),("OPC-UA Sessions","3",T["accent2"])]:
            row=QHBoxLayout(); row.setSpacing(6)
            kl=QLabel(k+":"); kl.setFixedWidth(130); kl.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:9px;")
            vl=QLabel(v); vl.setStyleSheet(f"color:{col};font-family:Consolas;font-size:9px;font-weight:bold;")
            row.addWidget(kl); row.addWidget(vl,1); dl.addLayout(row)
        dl.addSpacing(10); dl.addWidget(lbl("SYSTEM HEALTH",9,bold=True,color=T["text_dim"])); dl.addWidget(hdivider())
        for k,v,col in [("System Load","42%",T["accent"]),("Net Latency","2ms",T["accent"]),
                        ("Alarm Rate","0.3/hr",T["warn"]),("MTBF Estimate","847 hrs",T["accent2"]),
                        ("GOOSE Pkt/s","102",T["accent"])]:
            row=QHBoxLayout(); row.setSpacing(6)
            kl=QLabel(k+":"); kl.setFixedWidth(130); kl.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:9px;")
            vl=QLabel(v); vl.setStyleSheet(f"color:{col};font-family:Consolas;font-size:9px;font-weight:bold;")
            row.addWidget(kl); row.addWidget(vl,1); dl.addLayout(row)
        dl.addStretch()
    def _on_update(self,snap):
        for tag,series,ax,ay,vl,unit,col in self._cseries:
            if tag not in snap: continue
            hist=snap[tag]["history"][-60:]; series.clear()
            for j,v in enumerate(hist): series.append(j,v)
            mn,mx=min(hist),max(hist); pad=(mx-mn)*0.1 or 0.5
            ay.setRange(mn-pad,mx+pad); ax.setRange(0,len(hist)-1)
            new_val = "{:.1f} {}".format(snap[tag]["val"], unit)
            old_val = vl.text()
            vl.setText(new_val)
            if old_val != new_val:
                vl.setStyleSheet("color:#FFFFFF;font-family:Consolas;font-size:12px;font-weight:bold;")
                QTimer.singleShot(140, lambda w=vl,c=col: w.setStyleSheet(
                    "color:{};font-family:Consolas;font-size:12px;font-weight:bold;".format(c)))

# ── AUDIT TAB ─────────────────────────────────────────────────────────────────
class AuditTab(QWidget):
    _LIVE_EVENTS = [
        {"user":"operator1","role":"Operator","action":"Polled IED-PLC01 — status OK",       "ip":"10.0.1.14","sev":"info","tag":"IED-PLC01"},
        {"user":"engineer1","role":"Engineer","action":"Read IED-SEN02 diagnostics report",  "ip":"10.0.1.22","sev":"info","tag":"IED-SEN02"},
        {"user":"operator2","role":"Operator","action":"Verified Bay-2 breaker state",       "ip":"10.0.1.31","sev":"info","tag":""},
        {"user":"operator1","role":"Operator","action":"Acknowledged IED-PMP02 warning",     "ip":"10.0.1.14","sev":"warning","tag":"IED-PMP02"},
        {"user":"engineer2","role":"Engineer","action":"Reviewed IED-SEN02 GOOSE log",       "ip":"10.0.1.9", "sev":"info","tag":"IED-SEN02"},
    ]
    def __init__(self):
        super().__init__(); self._data=[dict(a) for a in AUDIT_DATA]; self._filter_tag=None
        self._build(); BUS.alarm_selected.connect(self._on_alarm_selected)
        t=QTimer(self); t.timeout.connect(self._inject_event); t.start(28000)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(14)
        hdr=QHBoxLayout(); hdr.addWidget(lbl("AUDIT LOG",13,bold=True)); hdr.addStretch()
        self._corr_lbl=QLabel("All events")
        self._corr_lbl.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:9px;"); hdr.addWidget(self._corr_lbl)
        clr=ghost_btn("✕ Clear",T["text_dim"]); clr.setFixedSize(72,28); clr.clicked.connect(self._clear_filter); hdr.addWidget(clr)
        self._search=QLineEdit(); self._search.setPlaceholderText("Search…"); self._search.setFixedWidth(180)
        self._search.setStyleSheet(f"QLineEdit{{background:{T['surface2']};color:{T['text']};border:1px solid {T['border']};"
            f"border-radius:6px;padding:4px 10px;font-family:Consolas;}}QLineEdit:focus{{border-color:{T['accent']};}}")
        self._search.textChanged.connect(lambda _: self._populate(self._current_data())); hdr.addWidget(self._search)
        for fmt in ["CSV","JSON"]:
            b=ghost_btn(f"↓ {fmt}",T["accent"]); b.setFixedSize(68,28)
            b.clicked.connect(lambda _,f=fmt: self._export(f)); hdr.addWidget(b)
        root.addLayout(hdr)
        stats=QHBoxLayout(); stats.setSpacing(10)
        for l2,v,col in [("Entries",str(len(self._data)),T["accent"]),
                          ("Users",str(len({a["user"] for a in self._data})),T["accent2"]),
                          ("Today",str(len(self._data)),T["text_mid"]),
                          ("Critical","2",T["danger"])]:
            c=Card(); c.setFixedHeight(70); cl=QVBoxLayout(c); cl.setContentsMargins(14,8,14,8); cl.setSpacing(2)
            vw=QLabel(v); vw.setFont(QFont("Consolas",20,QFont.Weight.Bold)); vw.setStyleSheet(f"color:{col};")
            lw=QLabel(l2.upper()); lw.setFont(QFont("Consolas",7)); lw.setStyleSheet(f"color:{T['text_dim']};letter-spacing:1px;")
            cl.addWidget(vw); cl.addWidget(lw); stats.addWidget(c)
        root.addLayout(stats)
        self._table=QTableWidget(len(self._data),5)
        self._table.setHorizontalHeaderLabels(["Timestamp","User","Role","Action","Source IP"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True); self._table.setStyleSheet(table_style())
        self._populate(self._data); root.addWidget(self._table,1)
    def _current_data(self):
        txt=self._search.text().lower()
        base=self._data if not self._filter_tag else [a for a in self._data if a.get("tag")==self._filter_tag or self._filter_tag in a["action"]]
        return [a for a in base if txt in a["action"].lower() or txt in a["user"].lower()] if txt else base
    def _populate(self,data,hl_tag=None):
        ROLE_C={"Admin":T["danger"],"Engineer":T["accent2"],"Operator":T["accent"]}
        SEV_C={"fault":T["danger"],"warning":T["warn"],"info":T["accent2"]}
        self._table.setRowCount(len(data))
        for row,a in enumerate(data):
            is_hl=hl_tag and a.get("tag")==hl_tag
            for c,val in enumerate([a["time"],a["user"],a["role"],a["action"],a["ip"]]):
                item=QTableWidgetItem(val)
                if is_hl: item.setBackground(QColor(T["highlight"])); item.setForeground(QColor(T["accent"]))
                elif c==1 or c==2: item.setForeground(QColor(ROLE_C.get(a["role"],T["text"])))
                else: item.setForeground(QColor(T["text"]))
                self._table.setItem(row,c,item)
            self._table.setRowHeight(row,48)
    def _on_alarm_selected(self,alarm):
        tag=alarm.get("tag","")
        if tag:
            self._filter_tag=tag; self._corr_lbl.setText(f"Filtered: {tag}")
            self._corr_lbl.setStyleSheet(f"color:{T['accent']};font-family:Consolas;font-size:9px;font-weight:bold;")
            self._populate(self._current_data(),hl_tag=tag)
    def _inject_event(self):
        ev = random.choice(AuditTab._LIVE_EVENTS).copy()
        ev["time"] = datetime.now().strftime("%H:%M:%S")
        self._data.insert(0, ev)
        if len(self._data) > 40: self._data.pop()
        if not self._filter_tag:
            self._populate(self._data)
    def _clear_filter(self):
        self._filter_tag=None; self._corr_lbl.setText("All events")
        self._corr_lbl.setStyleSheet(f"color:{T['text_dim']};font-family:Consolas;font-size:9px;"); self._populate(self._data)
    def _export(self,fmt):
        path=os.path.expanduser(f"~/gridscope_audit.{fmt.lower()}")
        if fmt=="CSV":
            with open(path,"w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["time","user","role","sev","action","ip","tag"]); w.writeheader(); w.writerows(self._data)
        else:
            with open(path,"w") as f: json.dump(self._data,f,indent=2)
        QToolTip.showText(self.mapToGlobal(self.rect().center()),f"Exported → {path}",self)

# ── STATUS BAR ────────────────────────────────────────────────────────────────
class StatusBar(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedHeight(28)
        self._pkt_count = 102; self._latency = 2
        r=QHBoxLayout(self); r.setContentsMargins(20,0,20,0); r.setSpacing(0)
        # Static items
        for txt,col in [("● IEC 61850 MMS",T["accent"]),("9 IEDs",T["text_dim"]),
                        ("Bay-1 · Bay-2 · Bay-3 · Bay-4",T["text_dim"])]:
            l=QLabel(txt); l.setFont(QFont("Consolas",9))
            l.setStyleSheet(f"color:{col}; padding:0 16px 0 0;"); r.addWidget(l)
        # Live GOOSE latency
        self._goose_lbl=QLabel("● GOOSE  2ms"); self._goose_lbl.setFont(QFont("Consolas",9))
        self._goose_lbl.setStyleSheet(f"color:{T['accent']}; padding:0 16px 0 0;"); r.addWidget(self._goose_lbl)
        # Live packet counter
        self._pkt_lbl=QLabel("102 pkt/s"); self._pkt_lbl.setFont(QFont("Consolas",9))
        self._pkt_lbl.setStyleSheet(f"color:{T['text_dim']}; padding:0 16px 0 0;"); r.addWidget(self._pkt_lbl)
        r.addStretch()
        ver=QLabel("GridScope v4.0.0  ·  Dammam Substation A  ·  MIT")
        ver.setFont(QFont("Consolas",9)); ver.setStyleSheet(f"color:{T['text_dim']}; padding-right:4px;"); r.addWidget(ver)
        t=QTimer(self); t.timeout.connect(self._tick); t.start(1800)
    def _tick(self):
        self._latency = max(1, min(12, self._latency + random.randint(-1,2)))
        self._pkt_count = max(80, min(140, self._pkt_count + random.randint(-4,4)))
        col = T["accent"] if self._latency<=4 else T["warn"] if self._latency<=8 else T["danger"]
        self._goose_lbl.setText(f"● GOOSE  {self._latency}ms")
        self._goose_lbl.setStyleSheet(f"color:{col}; padding:0 16px 0 0;")
        self._pkt_lbl.setText(f"{self._pkt_count} pkt/s")
    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(T["bg"]))
        p.setPen(QPen(QColor(T["border"]),1)); p.drawLine(0,0,self.width(),0)

# ── MAIN WINDOW ───────────────────────────────────────────────────────────────
class GridScope(QMainWindow):
    def __init__(self):
        super().__init__(); set_theme(True)
        self.setWindowTitle("GridScope — Dammam Substation A")
        self.resize(1400,880); self.setMinimumSize(1100,700)
        self._engine=DataEngine(); self._build(); self._apply_theme()
    def _build(self):
        central=QWidget(); self.setCentralWidget(central)
        root=QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self._topbar=TopBar(); root.addWidget(self._topbar)
        self._tabs=QTabWidget(); self._tabs.setDocumentMode(True); self._tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_list=[
            (OverviewTab(self._engine),          "  Overview  "),
            (AlarmsTab(self),                    "  Alarms  "),
            (TopologyTab(self),                  "  Topology  "),
            (AnalyticsTab(self._engine, self),   "  Analytics  "),
            (AuditTab(),                         "  Audit Log  "),
        ]
        for w,l in self._tab_list: self._tabs.addTab(w,l)
        root.addWidget(self._tabs,1)
        self._status_bar=StatusBar(); root.addWidget(self._status_bar)
    def _apply_theme(self):
        self.setStyleSheet(
            f"QMainWindow,QWidget{{background:{T['bg']};}}"
            f"QTabWidget::pane{{border:none;border-top:1px solid {T['border']};background:{T['bg']};}}"
            f"QTabBar::tab{{background:transparent;color:{T['text_dim']};padding:11px 24px;"
            f"font-family:Consolas;font-size:12px;border-bottom:2px solid transparent;}}"
            f"QTabBar::tab:selected{{color:{T['accent']};border-bottom:2px solid {T['accent']};}}"
            f"QTabBar::tab:hover{{color:{T['text']};}}"
            f"QScrollBar:vertical{{background:{T['surface2']};width:5px;border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{T['border']};border-radius:2px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
            f"QToolTip{{background:{T['surface3']};color:{T['text']};border:1px solid {T['border2']};"
            f"font-family:Consolas;font-size:10px;padding:8px;}}"
            f"QSlider{{background:transparent;}}"
            f"QDialog{{background:{T['bg']};}}")


def main():
    app=QApplication(sys.argv); app.setApplicationName("GridScope"); app.setFont(QFont("Consolas",11))
    w=GridScope(); w.show(); sys.exit(app.exec())

if __name__=="__main__": main()