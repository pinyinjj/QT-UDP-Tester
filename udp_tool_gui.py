import sys
import os

VERSION = "1.0.0"

# PyInstaller 环境下获取资源路径
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

import socket
import select
import time
import json
import sqlite3
import threading
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QPoint, QEvent, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QTableWidgetItem

from qfluentwidgets import (
    LineEdit, SpinBox, DoubleSpinBox, PrimaryPushButton, 
    PushButton, TextEdit, SubtitleLabel, CaptionLabel, StrongBodyLabel,
    CardWidget, FluentIcon as FIF, setTheme, Theme, setFont, InfoBar, InfoBarPosition,
    setThemeColor, FluentWindow, SingleDirectionScrollArea, TitleLabel,
    PrimaryToolButton, ToolButton, TransparentToolButton, FlowLayout, CheckBox,
    TableWidget, MessageBox, MessageBoxBase
)

class ProtocolEditDialog(MessageBoxBase):
    def __init__(self, title, name="", port=5005, data="", proto_type="send", freq=1.0, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title)
        
        self.nameInput = LineEdit()
        self.nameInput.setText(name)
        self.nameInput.setPlaceholderText("Protocol Name")
        
        self.type_choice = QHBoxLayout()
        self.send_radio = CheckBox("Send")
        self.recv_radio = CheckBox("Receive")
        self.send_radio.setChecked(proto_type == "send")
        self.recv_radio.setChecked(proto_type == "receive")
        self.send_radio.stateChanged.connect(lambda s: self.recv_radio.setChecked(not self.send_radio.isChecked()) if s == Qt.Checked else None)
        self.recv_radio.stateChanged.connect(lambda s: self.send_radio.setChecked(not self.recv_radio.isChecked()) if s == Qt.Checked else None)
        self.type_choice.addWidget(self.send_radio)
        self.type_choice.addWidget(self.recv_radio)

        self.portInput = SpinBox()
        self.portInput.setRange(1, 65535)
        self.portInput.setValue(port)
        
        self.freqInput = DoubleSpinBox()
        self.freqInput.setRange(0.01, 1000.0)
        self.freqInput.setValue(freq)
        self.freqInput.setSuffix(" Hz")
        
        self.dataInput = TextEdit()
        self.dataInput.setPlainText(data)
        self.dataInput.setPlaceholderText("Protocol Content")
        self.dataInput.setFixedHeight(150)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(CaptionLabel("Protocol Name"))
        self.viewLayout.addWidget(self.nameInput)
        self.viewLayout.addWidget(CaptionLabel("Type"))
        self.viewLayout.addLayout(self.type_choice)
        self.viewLayout.addWidget(CaptionLabel("Target/Listen Port"))
        self.viewLayout.addWidget(self.portInput)
        self.viewLayout.addWidget(CaptionLabel("Loop Frequency"))
        self.viewLayout.addWidget(self.freqInput)
        self.viewLayout.addWidget(CaptionLabel("Protocol Content"))
        self.viewLayout.addWidget(self.dataInput)
        
        self.widget.setMinimumWidth(450)
        self.nameInput.setFocus()

    def get_data(self):
        return {
            "name": self.nameInput.text().strip(),
            "port": self.portInput.value(),
            "data": self.dataInput.toPlainText().strip(),
            "type": "send" if self.send_radio.isChecked() else "receive",
            "freq": self.freqInput.value()
        }

CONFIG_DIR = os.path.expanduser("~/.qt-udp-tester")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DB_FILE = os.path.join(CONFIG_DIR, "protocols.db")

class DatabaseManager:
    def __init__(self, db_name=DB_FILE):
        self.db_name = db_name
        self._lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS protocols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    port INTEGER NOT NULL DEFAULT 5005,
                    data TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'send',
                    freq REAL NOT NULL DEFAULT 1.0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 尝试为旧数据库添加列
            cols = [
                ('port', 'INTEGER NOT NULL DEFAULT 5005'),
                ('type', "TEXT NOT NULL DEFAULT 'send'"),
                ('freq', 'REAL NOT NULL DEFAULT 1.0')
            ]
            for col_name, col_def in cols:
                try:
                    cursor.execute(f'ALTER TABLE protocols ADD COLUMN {col_name} {col_def}')
                except: pass
            conn.commit()
            conn.close()

    def get_all_protocols(self):
        with self._lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT name, data, port, type, freq FROM protocols ORDER BY updated_at DESC')
            rows = cursor.fetchall()
            conn.close()
            return [{"name": r[0], "data": r[1], "port": r[2], "type": r[3], "freq": r[4]} for r in rows]

    def save_protocol(self, name, data, port=5005, proto_type='send', freq=1.0):
        with self._lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO protocols (name, data, port, type, freq, updated_at) 
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            ''', (name, data, port, proto_type, freq))
            conn.commit()
            conn.close()

    def update_name(self, old_name, new_name):
        with self._lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('UPDATE protocols SET name = ?, updated_at = datetime("now") WHERE name = ?', (new_name, old_name))
            conn.commit()
            conn.close()

    def delete_protocol(self, name):
        with self._lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM protocols WHERE name = ?', (name,))
            conn.commit()
            conn.close()

class ReceiverThread(QThread):
    packets_received = pyqtSignal(list) # List of (timestamp, ip, remote_port, local_port, data)
    error_occurred = pyqtSignal(str)

    def __init__(self, ports):
        super().__init__()
        self.ports = ports
        self.running = True
        self.batch_interval = 0.05 # 50ms
        self.max_batch_size = 20

    def run(self):
        sockets = []
        try:
            for port in self.ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if hasattr(socket, 'SO_REUSEPORT'):
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.bind(('', port))
                    sock.setblocking(False)
                    sockets.append(sock)
                except OSError as e:
                    self.error_occurred.emit(f"Failed to bind port {port}: {str(e)}")
                    return 
            
            packet_buffer = []
            last_emit_time = time.time()

            while self.running:
                readable, _, _ = select.select(sockets, [], [], 0.1) # Reduced timeout
                for s in readable:
                    try:
                        data, addr = s.recvfrom(65535)
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        local_port = s.getsockname()[1]
                        packet_buffer.append((timestamp, addr[0], addr[1], local_port, data))
                    except:
                        continue
                
                # Check if we should emit the batch
                current_time = time.time()
                if packet_buffer and (len(packet_buffer) >= self.max_batch_size or (current_time - last_emit_time) >= self.batch_interval):
                    self.packets_received.emit(packet_buffer)
                    packet_buffer = []
                    last_emit_time = current_time

        except Exception as e:
            self.error_occurred.emit(f"Receiver error: {str(e)}")
        finally:
            for s in sockets:
                s.close()

    def stop(self):
        self.running = False
        self.wait()

class FilterTag(CardWidget):
    toggled = pyqtSignal(bool)
    deleted = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(parent=parent)
        self.filter_text = text
        self.setFixedHeight(32)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 0, 4, 0)
        self.layout.setSpacing(6)
        self.checkbox = CheckBox(text, self)
        self.checkbox.stateChanged.connect(lambda s: self.toggled.emit(s == Qt.Checked))
        self.layout.addWidget(self.checkbox)
        self.delete_btn = TransparentToolButton(FIF.CLOSE, self)
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setIconSize(QSize(10, 10))
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(lambda: self.deleted.emit(self.filter_text))
        self.layout.addWidget(self.delete_btn)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self.delete_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.delete_btn.setVisible(False)
        super().leaveEvent(event)

    def isChecked(self):
        return self.checkbox.isChecked()

class AnimatedTagContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.tag_area = QWidget(self)
        self.tag_layout = FlowLayout(self.tag_area, needAni=True)
        self.tag_layout.setContentsMargins(0, 5, 0, 5)
        self.layout.addWidget(self.tag_area)
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.setFixedHeight(0)
        self.is_expanded = False

    def toggle(self, expand: bool):
        if self.is_expanded == expand: return
        self.is_expanded = expand
        start = 0 if expand else 80
        end = 80 if expand else 0
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        if expand:
            self.setMinimumHeight(0)
            self.setMaximumHeight(0)
        self.animation.start()

class FontAdjustableTableWidget(QWidget):
    fontSizeChanged = pyqtSignal(int)
    def __init__(self, parent=None, show_zoom=True):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.table = TableWidget(self)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.current_font_size = 13
        setFont(self.table, self.current_font_size, QFont.Monospace)
        self.layout.addWidget(self.table)
        self.btn_container = QWidget(self)
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(2)
        style = "TransparentToolButton { border: 1px solid #dcdcdc; border-radius: 4px; background-color: rgba(255, 255, 255, 0.9); } TransparentToolButton:hover { background-color: #f0f0f0; border: 1px solid #0078d4; }"
        self.zoom_in_btn = TransparentToolButton(FIF.ADD, self.btn_container)
        self.zoom_out_btn = TransparentToolButton(FIF.REMOVE, self.btn_container)
        for btn in [self.zoom_in_btn, self.zoom_out_btn]:
            btn.setFixedSize(26, 26)
            btn.setIconSize(QSize(12, 12))
            btn.setStyleSheet(style)
            self.btn_layout.addWidget(btn)
        self.btn_container.setFixedSize(54, 26)
        self.zoom_in_btn.clicked.connect(lambda: self.adjust_font(1))
        self.zoom_out_btn.clicked.connect(lambda: self.adjust_font(-1))
        if not show_zoom: self.btn_container.hide()

    def adjust_font(self, delta):
        self.current_font_size = max(8, min(48, self.current_font_size + delta))
        setFont(self.table, self.current_font_size, QFont.Monospace)
        self.table.verticalHeader().setDefaultSectionSize(int(self.current_font_size * 1.8))
        self.fontSizeChanged.emit(self.current_font_size)

    def set_font_size(self, size):
        self.current_font_size = max(8, min(48, size))
        setFont(self.table, self.current_font_size, QFont.Monospace)
        self.table.verticalHeader().setDefaultSectionSize(int(self.current_font_size * 1.8))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.btn_container.move(self.width() - self.btn_container.width() - 20, 5)
        self.btn_container.raise_()

class FontAdjustableTextEdit(QWidget):
    fontSizeChanged = pyqtSignal(int)
    def __init__(self, parent=None, is_readonly=False, placeholder=""):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.text_edit = TextEdit(self)
        self.text_edit.setReadOnly(is_readonly)
        self.text_edit.setPlaceholderText(placeholder)
        self.current_font_size = 13
        setFont(self.text_edit, self.current_font_size, QFont.Monospace)
        self.layout.addWidget(self.text_edit)
        self.btn_container = QWidget(self)
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(2)
        style = "TransparentToolButton { border: 1px solid #dcdcdc; border-radius: 4px; background-color: rgba(255, 255, 255, 0.9); } TransparentToolButton:hover { background-color: #f0f0f0; border: 1px solid #0078d4; }"
        self.zoom_in_btn = TransparentToolButton(FIF.ADD, self.btn_container)
        self.zoom_out_btn = TransparentToolButton(FIF.REMOVE, self.btn_container)
        for btn in [self.zoom_in_btn, self.zoom_out_btn]:
            btn.setFixedSize(26, 26)
            btn.setIconSize(QSize(12, 12))
            btn.setStyleSheet(style)
            self.btn_layout.addWidget(btn)
        self.btn_container.setFixedSize(54, 26)
        self.zoom_in_btn.clicked.connect(lambda: self.adjust_font(1))
        self.zoom_out_btn.clicked.connect(lambda: self.adjust_font(-1))

    def adjust_font(self, delta):
        self.current_font_size = max(8, min(48, self.current_font_size + delta))
        setFont(self.text_edit, self.current_font_size, QFont.Monospace)
        self.fontSizeChanged.emit(self.current_font_size)

    def set_font_size(self, size):
        self.current_font_size = max(8, min(48, size))
        setFont(self.text_edit, self.current_font_size, QFont.Monospace)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.btn_container.move(self.width() - self.btn_container.width() - 2, 2)
        self.btn_container.raise_()

class HeightResizer(QFrame):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target
        self.setCursor(Qt.SizeVerCursor)
        self.setFixedHeight(4)
        self.setStyleSheet("HeightResizer { background: transparent; border-radius: 2px; } HeightResizer:hover { background: #0078d4; }")
        self.pressing = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressing = True
            self.startY = event.globalY()
            self.startH = self.target.height()

    def mouseMoveEvent(self, event):
        if self.pressing:
            delta = event.globalY() - self.startY
            self.target.setMinimumHeight(max(100, self.startH + delta))

    def mouseReleaseEvent(self, event):
        self.pressing = False

class HomeInterface(SingleDirectionScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.filter_tags = []
        self.setup_ui()
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("homeInterface")
        self.view.setObjectName("view")
        self.setStyleSheet("#view, #homeInterface { background-color: transparent; border: none; }")
        self.payload_container.fontSizeChanged.connect(self.save_config)
        self.log_container.fontSizeChanged.connect(self.save_config)
        self.load_config()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_add_btn_pos()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_add_btn_pos()

    def _update_add_btn_pos(self):
        if hasattr(self, 'add_filter_btn') and hasattr(self, 'filter_input'):
            x = self.filter_input.width() - self.add_filter_btn.width() - 4
            y = (self.filter_input.height() - self.add_filter_btn.height()) // 2
            self.add_filter_btn.move(x, y)

    def setup_ui(self):
        self.vBoxLayout.setContentsMargins(36, 20, 36, 36)
        self.vBoxLayout.setSpacing(24)
        self.sender_card = CardWidget(self.view)
        s_layout = QVBoxLayout(self.sender_card)
        s_layout.setContentsMargins(20, 16, 20, 16)
        s_layout.addWidget(SubtitleLabel("Sender"))
        cfg_layout = QHBoxLayout()
        self.target_ip = LineEdit(self.sender_card)
        self.target_ip.setText("255.255.255.255")
        self.target_port = SpinBox(self.sender_card)
        self.target_port.setRange(1, 65535)
        self.target_port.setValue(5005)
        self.send_freq = DoubleSpinBox(self.sender_card)
        self.send_freq.setRange(0.1, 1000.0)
        self.send_freq.setValue(1.0)
        self.send_freq.setSuffix(" Hz")
        cfg_layout.addWidget(CaptionLabel("IP"))
        cfg_layout.addWidget(self.target_ip, 3)
        cfg_layout.addWidget(CaptionLabel("Port"))
        cfg_layout.addWidget(self.target_port, 1)
        cfg_layout.addWidget(CaptionLabel("Freq"))
        cfg_layout.addWidget(self.send_freq, 1)
        s_layout.addLayout(cfg_layout)
        s_layout.addWidget(StrongBodyLabel("Message Payload"))
        self.payload_container = FontAdjustableTextEdit(self.sender_card)
        self.payload_container.text_edit.setPlainText(r'{"cmd":"ping","data":0}')
        self.payload_container.setMinimumHeight(140)
        s_layout.addWidget(self.payload_container)
        s_layout.setStretchFactor(self.payload_container, 1)
        self.resizer = HeightResizer(self.payload_container, self.sender_card)
        s_layout.addWidget(self.resizer)
        btn_layout = QHBoxLayout()
        self.save_btn = PushButton(FIF.SAVE, "Save to Library", self.sender_card)
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.format_btn = PushButton(FIF.CODE, "Format JSON", self.sender_card)
        self.format_btn.clicked.connect(self.toggle_payload_format)
        self.send_once_btn = PushButton(FIF.SEND, "Send Now", self.sender_card)
        self.start_send_btn = PrimaryPushButton(FIF.PLAY, "Start Loop", self.sender_card)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.format_btn)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.send_once_btn)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.start_send_btn)
        s_layout.addLayout(btn_layout)
        self.vBoxLayout.addWidget(self.sender_card)
        self.vBoxLayout.setStretchFactor(self.sender_card, 1)
        self.receiver_card = CardWidget(self.view)
        r_layout = QVBoxLayout(self.receiver_card)
        r_layout.setContentsMargins(20, 16, 20, 16)
        r_layout.setSpacing(12)
        r_layout.addWidget(SubtitleLabel("Receiver"))
        r_cfg = QHBoxLayout()
        self.listen_port = LineEdit(self.receiver_card)
        self.listen_port.setPlaceholderText("e.g. 5005, 5006")
        self.listen_port.setText("5005")
        self.listen_port.setFixedWidth(150)
        self.filter_input = LineEdit(self.receiver_card)
        self.filter_input.setPlaceholderText("Add filter keyword...")
        self.add_filter_btn = TransparentToolButton(FIF.ADD, self.filter_input)
        self.add_filter_btn.setFixedSize(30, 30)
        self.add_filter_btn.setCursor(Qt.PointingHandCursor)
        self.add_filter_btn.clicked.connect(self.add_filter_tag)
        self.filter_input.returnPressed.connect(self.add_filter_tag)
        self.filter_input.setTextMargins(0, 0, 30, 0)
        self.start_recv_btn = PrimaryPushButton(FIF.WIFI, "Start Listening", self.receiver_card)
        self.start_recv_btn.setFixedWidth(160)
        r_cfg.addWidget(CaptionLabel("Listen Port"))
        r_cfg.addWidget(self.listen_port)
        r_cfg.addSpacing(20)
        r_cfg.addWidget(CaptionLabel("Filters"))
        r_cfg.addWidget(self.filter_input, 1)
        r_cfg.addSpacing(15)
        r_cfg.addWidget(self.start_recv_btn)
        r_layout.addLayout(r_cfg)
        self.tag_container = AnimatedTagContainer(self.receiver_card)
        r_layout.addWidget(self.tag_container)
        self.log_container = FontAdjustableTableWidget(self.receiver_card)
        self.log_container.setMinimumHeight(350)
        r_layout.addWidget(self.log_container)
        r_layout.setStretchFactor(self.log_container, 1)
        self.log_container.table.setColumnCount(4)
        self.log_container.table.setHorizontalHeaderLabels(["Time", "Source", "Port", "Payload"])
        self.log_container.table.horizontalHeader().setStretchLastSection(True)
        self.log_container.table.setEditTriggers(TableWidget.NoEditTriggers)
        self.log_container.table.setAlternatingRowColors(True)
        self.log_container.table.setColumnWidth(0, 140)
        self.log_container.table.setColumnWidth(1, 140)
        self.log_container.table.setColumnWidth(2, 120)
        self.log_container.table.itemClicked.connect(self.on_log_item_clicked)
        r_ctrl = QHBoxLayout()
        self.clear_btn = PushButton(FIF.DELETE, "Clear Logs", self.receiver_card)
        self.clear_btn.clicked.connect(lambda: self.log_container.table.setRowCount(0))
        r_ctrl.addStretch()
        r_ctrl.addWidget(self.clear_btn)
        r_layout.addLayout(r_ctrl)
        self.vBoxLayout.addWidget(self.receiver_card)
        self.vBoxLayout.setStretchFactor(self.receiver_card, 2)

    def on_log_item_clicked(self, item):
        if item.column() == 3:
            original_text = item.data(Qt.UserRole)
            if original_text:
                QApplication.clipboard().setText(original_text)
                self.window().show_toast("Copied", "Payload copied to clipboard")

    def toggle_payload_format(self):
        text = self.payload_container.text_edit.toPlainText().strip()
        if not text: return
        try:
            obj = json.loads(text)
            if '\n' in text: new_text = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
            else: new_text = json.dumps(obj, indent=4, ensure_ascii=False)
            self.payload_container.text_edit.setPlainText(new_text)
        except Exception as e:
            w = MessageBox("Format Error", f"Invalid JSON format. Problematic text:\n\n{text}", self.window())
            w.cancelButton.hide()
            w.exec()

    def on_save_clicked(self):
        current_port = self.target_port.value()
        current_payload = self.payload_container.text_edit.toPlainText()
        w = ProtocolEditDialog("Save to Library", port=current_port, data=current_payload, parent=self.window())
        if w.exec():
            res = w.get_data()
            if res['name']: self.window().save_protocol(res['name'], res['data'], res['port'], res['type'], res['freq'])

    def add_filter_tag(self, text=None, save=True):
        if text is None or isinstance(text, bool): text = self.filter_input.text().strip()
        if not text: return
        if any(tag.filter_text == text for tag in self.filter_tags): return
        tag = FilterTag(text, self.tag_container.tag_area)
        tag.deleted.connect(self.remove_filter_tag)
        tag.toggled.connect(self.apply_log_filters)
        self.tag_container.tag_layout.addWidget(tag)
        self.filter_tags.append(tag)
        self.filter_input.clear()
        if len(self.filter_tags) == 1: self.tag_container.toggle(True)
        self.apply_log_filters()
        if save: self.save_config()

    def remove_filter_tag(self, text):
        for tag in self.filter_tags[:]:
            if tag.filter_text == text:
                self.tag_container.tag_layout.removeWidget(tag)
                tag.deleteLater()
                self.filter_tags.remove(tag)
                break
        if not self.filter_tags: self.tag_container.toggle(False)
        self.apply_log_filters()
        self.save_config()

    def apply_log_filters(self):
        table = self.log_container.table
        active_filters = [tag.filter_text.lower() for tag in self.filter_tags if tag.checkbox.isChecked()]
        for i in range(table.rowCount()):
            if not active_filters: table.setRowHidden(i, False); continue
            item = table.item(i, 3)
            if not item: continue
            text = item.data(Qt.UserRole).lower()
            match = any(f in text for f in active_filters)
            table.setRowHidden(i, not match)

    def save_config(self):
        config = {"filters": [tag.filter_text for tag in self.filter_tags], "payload_font_size": self.payload_container.current_font_size, "log_font_size": self.log_container.current_font_size}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(config, f)
        except: pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    filters = config.get("filters", [])
                    payload_font_size = config.get("payload_font_size", 13)
                    log_font_size = config.get("log_font_size", 13)
                    for text in filters: self.add_filter_tag(text, save=False)
                    self.payload_container.set_font_size(payload_font_size)
                    self.log_container.set_font_size(log_font_size)
                    protocols = self.window().db.get_all_protocols()
                    self.window().protocol_interface.load_protocols(protocols)
            except: pass

class ProtocolInterface(SingleDirectionScrollArea):
    protocol_selected = pyqtSignal(str)
    start_loop_send = pyqtSignal(str, int, float)
    stop_loop_send = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.setup_ui()
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("protocolInterface")
        self.view.setObjectName("view")
        self.setStyleSheet("#view, #protocolInterface { background-color: transparent; border: none; }")

    def setup_ui(self):
        self.vBoxLayout.setContentsMargins(36, 20, 36, 36)
        self.vBoxLayout.setSpacing(24)
        self.vBoxLayout.setAlignment(Qt.AlignTop)
        self.card = CardWidget(self.view)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(20, 16, 20, 16)
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("Protocol Library"))
        header.addStretch()
        self.add_btn = PrimaryPushButton(FIF.ADD, "New Protocol", self.card)
        self.add_btn.clicked.connect(self.on_add_clicked)
        header.addWidget(self.add_btn)
        layout.addLayout(header)
        self.table_container = FontAdjustableTableWidget(self.card, show_zoom=False)
        self.table = self.table_container.table
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Port", "Freq", "Payload Preview", "Actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 300)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table_container)
        self.vBoxLayout.addWidget(self.card)

    def load_protocols(self, protocols):
        self.table.setRowCount(0)
        for p in protocols: self._add_row(p['name'], p['data'], p.get('port', 5005), p.get('type', 'send'), p.get('freq', 1.0))

    def _add_row(self, name, data, port, proto_type, freq):
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(name); name_item.setTextAlignment(Qt.AlignCenter); self.table.setItem(row, 0, name_item)
        type_item = QTableWidgetItem(proto_type.upper()); type_item.setTextAlignment(Qt.AlignCenter)
        if proto_type == 'receive': type_item.setForeground(QColor("#009e73"))
        else: type_item.setForeground(QColor("#0078d4"))
        self.table.setItem(row, 1, type_item)
        port_item = QTableWidgetItem(str(port)); port_item.setTextAlignment(Qt.AlignCenter); self.table.setItem(row, 2, port_item)
        status_item = QTableWidgetItem(f"{freq} Hz"); status_item.setTextAlignment(Qt.AlignCenter); self.table.setItem(row, 3, status_item)
        preview = data.replace('\n', ' ')[:50] + ("..." if len(data) > 50 else "")
        preview_item = QTableWidgetItem(preview); preview_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft); self.table.setItem(row, 4, preview_item)
        btn_widget = QWidget(); btn_layout = QHBoxLayout(btn_widget); btn_layout.setContentsMargins(10, 5, 10, 5); btn_layout.setSpacing(8); btn_layout.setAlignment(Qt.AlignCenter)
        action_btn = ToolButton(FIF.SYNC, btn_widget); action_btn.setCheckable(True); action_btn.setToolTip("Start Loop Sending")
        def on_action_toggled(checked):
            if checked: action_btn.setIcon(FIF.PAUSE); self.start_loop_send.emit(name, port, freq)
            else: action_btn.setIcon(FIF.SYNC); self.stop_loop_send.emit(name)
        action_btn.clicked.connect(lambda: on_action_toggled(action_btn.isChecked()))
        send_btn = ToolButton(FIF.SEND, btn_widget); send_btn.setToolTip(f"Send Once to Port {port}"); send_btn.clicked.connect(lambda: self.window().send_custom_data(data, port))
        use_btn = ToolButton(FIF.PLAY, btn_widget); use_btn.setToolTip("Apply to Sender"); use_btn.clicked.connect(lambda: self.protocol_selected.emit(data))
        edit_btn = ToolButton(FIF.EDIT, btn_widget); edit_btn.setToolTip("Edit Protocol"); edit_btn.clicked.connect(lambda: self.on_edit_clicked(row, name, port, data, proto_type, freq))
        del_btn = ToolButton(FIF.DELETE, btn_widget); del_btn.setToolTip("Delete"); del_btn.clicked.connect(lambda: self.on_delete_clicked(name))
        btn_layout.addWidget(action_btn); btn_layout.addWidget(send_btn); btn_layout.addWidget(use_btn); btn_layout.addWidget(edit_btn); btn_layout.addWidget(del_btn)
        self.table.setCellWidget(row, 5, btn_widget)

    def on_add_clicked(self):
        current_port = self.window().home_interface.target_port.value()
        current_payload = self.window().home_interface.payload_container.text_edit.toPlainText()
        w = ProtocolEditDialog("New Protocol", port=current_port, data=current_payload, parent=self.window())
        if w.exec():
            res = w.get_data()
            if res['name']: self.window().save_protocol(res['name'], res['data'], res['port'], res['type'], res['freq'])

    def on_edit_clicked(self, row, old_name, old_port, old_data, old_type, old_freq):
        w = ProtocolEditDialog("Edit Protocol", name=old_name, port=old_port, data=old_data, proto_type=old_type, freq=old_freq, parent=self.window())
        if w.exec():
            res = w.get_data()
            if res['name']:
                if res['name'] != old_name: self.window().db.delete_protocol(old_name)
                self.window().save_protocol(res['name'], res['data'], res['port'], res['type'], res['freq'])

    def on_delete_clicked(self, name):
        w = MessageBox("Confirm Delete", f"Delete protocol '{name}'?", self.window())
        if w.exec(): self.window().delete_protocol(name)

class UDPToolApp(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.LIGHT)
        setThemeColor('#0078d4')
        self.setWindowTitle(f"QT-UDP-Tester v{VERSION}")
        self.resize(1150, 920)
        self.loop_timers = {}
        self.db = DatabaseManager()
        self.home_interface = HomeInterface(self)
        self.protocol_interface = ProtocolInterface(self)
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self.send_packet)
        self.recv_thread = None
        self._shared_send_socket = None # Persistent socket
        self.MAX_LOG_ROWS = 1000

        hi = self.home_interface
        hi.send_once_btn.clicked.connect(self.send_packet)
        hi.start_send_btn.clicked.connect(self.toggle_send_loop)
        hi.start_recv_btn.clicked.connect(self.toggle_receiver)
        hi.send_freq.valueChanged.connect(self.update_live_timer)
        self.protocol_interface.protocol_selected.connect(self.apply_protocol)
        self.protocol_interface.start_loop_send.connect(self.start_protocol_loop)
        self.protocol_interface.stop_loop_send.connect(self.stop_protocol_loop)
        self.addSubInterface(self.home_interface, FIF.HOME, "Control Center")
        self.addSubInterface(self.protocol_interface, QIcon(resource_path("icons/database.svg")), "Protocol Library")
        self.refresh_protocols()

    def _get_send_socket(self):
        if self._shared_send_socket is None:
            try:
                self._shared_send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._shared_send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                self._shared_send_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            except Exception as e:
                self.show_toast("Socket Error", str(e), True)
        return self._shared_send_socket

    def start_protocol_loop(self, name, port, freq):
        if name in self.loop_timers: self.loop_timers[name].stop()
        timer = QTimer(self)
        protocols = self.db.get_all_protocols()
        data = next((p['data'] for p in protocols if p['name'] == name), "")
        timer.timeout.connect(lambda: self.send_custom_data(data, port))
        timer.start(int(1000 / freq))
        self.loop_timers[name] = timer
        self.show_toast("Loop Started", f"Sending '{name}' at {freq}Hz")

    def stop_protocol_loop(self, name):
        if name in self.loop_timers: self.loop_timers[name].stop(); del self.loop_timers[name]; self.show_toast("Loop Stopped", f"Stopped sending '{name}'")

    def apply_protocol(self, data): self.home_interface.payload_container.text_edit.setPlainText(data); self.switchTo(self.home_interface); self.show_toast("Applied", "Protocol content loaded")
    def save_protocol(self, name, data, port=5005, proto_type='send', freq=1.0): self.db.save_protocol(name, data, port, proto_type, freq); self.refresh_protocols(); self.show_toast("Saved", f"Protocol '{name}' saved to library")
    def update_protocol(self, old_name, new_name): self.db.update_name(old_name, new_name); self.refresh_protocols(); self.show_toast("Updated", f"Protocol renamed to '{new_name}'")
    def delete_protocol(self, name): self.db.delete_protocol(name); self.refresh_protocols(); self.show_toast("Deleted", f"Protocol '{name}' removed")
    def refresh_protocols(self): protocols = self.db.get_all_protocols(); self.protocol_interface.load_protocols(protocols)
    def send_packet(self): data = self.home_interface.payload_container.text_edit.toPlainText(); self.send_custom_data(data)
    
    def send_custom_data(self, data_str, target_port=None):
        try:
            sock = self._get_send_socket()
            if not sock: return
            if target_port is None: target_port = self.home_interface.target_port.value()
            ip = self.home_interface.target_ip.text()
            data = data_str.encode('utf-8')
            sock.sendto(data, (ip, target_port))
            self.show_toast("Success", f"Sent to port {target_port}")
        except Exception as e: self.show_toast("Error", str(e), True)

    def show_toast(self, title, content, is_error=False):
        func = InfoBar.error if is_error else InfoBar.success
        func(title=title, content=content, orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP_RIGHT, duration=1500, parent=self)

    def update_live_timer(self):
        if self.send_timer.isActive(): self.send_timer.start(int(1000 / self.home_interface.send_freq.value()))

    def toggle_send_loop(self):
        btn = self.home_interface.start_send_btn
        if self.send_timer.isActive(): self.send_timer.stop(); btn.setText("Start Loop"); btn.setIcon(FIF.PLAY)
        else: self.send_timer.start(int(1000 / self.home_interface.send_freq.value())); btn.setText("Stop Loop"); btn.setIcon(FIF.PAUSE)

    def toggle_receiver(self):
        btn = self.home_interface.start_recv_btn
        if self.recv_thread and self.recv_thread.isRunning(): self.recv_thread.stop(); btn.setText("Start Listening"); btn.setIcon(FIF.WIFI)
        else:
            port_text = self.home_interface.listen_port.text().strip()
            if not port_text: self.show_toast("Error", "Please enter at least one port", True); return
            ports = []
            try:
                for p in port_text.replace(' ', '').split(','):
                    if p:
                        port = int(p)
                        if 1 <= port <= 65535: ports.append(port)
                        else: raise ValueError(f"Invalid port: {p}")
            except ValueError as e: self.show_toast("Error", str(e), True); return
            if not ports: self.show_toast("Error", "No valid ports found", True); return
            self.recv_thread = ReceiverThread(ports)
            self.recv_thread.packets_received.connect(self.on_packets_received) # Updated signal
            self.recv_thread.error_occurred.connect(self.on_receiver_error)
            self.recv_thread.start()
            btn.setText("Stop Listening"); btn.setIcon(FIF.CLOSE)

    def on_receiver_error(self, error_msg): self.show_toast("Receiver Error", error_msg, is_error=True); btn = self.home_interface.start_recv_btn; btn.setText("Start Listening"); btn.setIcon(FIF.WIFI)

    def on_packets_received(self, packets):
        table = self.home_interface.log_container.table
        active_filters = [tag.filter_text.lower() for tag in self.home_interface.filter_tags if tag.checkbox.isChecked()]
        
        # Turn off updates to prevent flickering
        table.setUpdatesEnabled(False)
        try:
            for timestamp, ip, port, local_port, data in packets:
                try: text = data.decode('utf-8', errors='replace').strip()
                except: text = data.hex(' ')
                
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(timestamp))
                table.setItem(row, 1, QTableWidgetItem(ip))
                table.setItem(row, 2, QTableWidgetItem(f"{local_port} ← {port}"))
                
                display_text = text.replace('\n', ' ')
                payload_item = QTableWidgetItem(display_text)
                payload_item.setData(Qt.UserRole, text)
                table.setItem(row, 3, payload_item)
                
                if active_filters:
                    match = any(f in text.lower() for f in active_filters)
                    table.setRowHidden(row, not match)
                
                # Maintain MAX_LOG_ROWS
                if table.rowCount() > self.MAX_LOG_ROWS:
                    table.removeRow(0)
            
            table.scrollToBottom()
        finally:
            table.setUpdatesEnabled(True)

    def closeEvent(self, event):
        if self._shared_send_socket:
            self._shared_send_socket.close()
        super().closeEvent(event)

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/icon.svg")))
    ex = UDPToolApp(); ex.setObjectName("UDPBroadcasterPro"); ex.show()
    sys.exit(app.exec_())
