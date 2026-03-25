import sys
import socket
import time
import json
import os
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QPoint, QEvent, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame

from qfluentwidgets import (
    LineEdit, SpinBox, DoubleSpinBox, PrimaryPushButton, 
    PushButton, TextEdit, SubtitleLabel, CaptionLabel, StrongBodyLabel,
    CardWidget, FluentIcon as FIF, setTheme, Theme, setFont, InfoBar, InfoBarPosition,
    setThemeColor, FluentWindow, SingleDirectionScrollArea, TitleLabel,
    PrimaryToolButton, ToolButton, TransparentToolButton, FlowLayout, CheckBox
)

CONFIG_FILE = "filters.json"

class ReceiverThread(QThread):
    packet_received = pyqtSignal(str, str, int, bytes)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, 'SO_REUSEPORT'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(('', self.port))
            sock.settimeout(0.5)
            while self.running:
                try:
                    data, addr = sock.recvfrom(65535)
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.packet_received.emit(timestamp, addr[0], addr[1], data)
                except socket.timeout:
                    continue
                except:
                    break
            sock.close()
        except:
            pass

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
    """ 带平滑展开/折叠动画的标签容器 """
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
        
        # 初始状态
        self.setFixedHeight(0)
        self.is_expanded = False

    def toggle(self, expand: bool):
        if self.is_expanded == expand: return
        self.is_expanded = expand
        
        # 计算目标高度 (标签行高度大约为 40px)
        # 这里简化处理，展开时给一个足够大的最大高度
        start = 0 if expand else 80
        end = 80 if expand else 0
        
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        
        if expand:
            self.setMinimumHeight(0)
            self.setMaximumHeight(0)
        
        self.animation.start()

class FontAdjustableTextEdit(QWidget):
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
        self.btn_container = QWidget(self.text_edit)
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 5, 0)
        self.btn_layout.setSpacing(4)
        style = """
            TransparentToolButton { border: 1px solid #dcdcdc; border-radius: 4px; background-color: rgba(255, 255, 255, 0.8); }
            TransparentToolButton:hover { background-color: #f0f0f0; border: 1px solid #0078d4; }
        """
        self.zoom_out_btn = TransparentToolButton(FIF.REMOVE, self.btn_container)
        self.zoom_in_btn = TransparentToolButton(FIF.ADD, self.btn_container)
        for btn in [self.zoom_out_btn, self.zoom_in_btn]:
            btn.setFixedSize(28, 28)
            btn.setIconSize(QSize(14, 14))
            btn.setStyleSheet(style)
            self.btn_layout.addWidget(btn)
        self.zoom_in_btn.clicked.connect(lambda: self.adjust_font(1))
        self.zoom_out_btn.clicked.connect(lambda: self.adjust_font(-1))
        self.text_edit.installEventFilter(self)

    def adjust_font(self, delta):
        self.current_font_size = max(8, min(48, self.current_font_size + delta))
        setFont(self.text_edit, self.current_font_size, QFont.Monospace)

    def eventFilter(self, obj, event):
        if obj == self.text_edit and event.type() == QEvent.Resize:
            self.btn_container.move(self.text_edit.width() - self.btn_container.width() - 12, 8)
        return super().eventFilter(obj, event)

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
        self.load_filters()

    def setup_ui(self):
        self.vBoxLayout.setContentsMargins(36, 20, 36, 36)
        self.vBoxLayout.setSpacing(24)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        # --- SENDER ---
        self.sender_card = CardWidget(self.view)
        s_layout = QVBoxLayout(self.sender_card)
        s_layout.setContentsMargins(20, 16, 20, 16)
        s_layout.addWidget(SubtitleLabel("Transmission Configuration"))
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
        self.payload_container.setFixedHeight(140)
        s_layout.addWidget(self.payload_container)
        btn_layout = QHBoxLayout()
        self.send_once_btn = PushButton(FIF.SEND, "Send Now", self.sender_card)
        self.start_send_btn = PrimaryPushButton(FIF.PLAY, "Start Loop", self.sender_card)
        btn_layout.addStretch()
        btn_layout.addWidget(self.send_once_btn)
        btn_layout.addWidget(self.start_send_btn)
        s_layout.addLayout(btn_layout)
        self.vBoxLayout.addWidget(self.sender_card)

        # --- RECEIVER ---
        self.receiver_card = CardWidget(self.view)
        r_layout = QVBoxLayout(self.receiver_card)
        r_layout.setContentsMargins(20, 16, 20, 16)
        r_layout.setSpacing(12)
        r_layout.addWidget(SubtitleLabel("Real-time Monitor"))
        r_cfg = QHBoxLayout()
        self.listen_port = SpinBox(self.receiver_card)
        self.listen_port.setRange(1, 65535)
        self.listen_port.setValue(5005)
        self.start_recv_btn = PrimaryPushButton(FIF.WIFI, "Start Listening", self.receiver_card)
        r_cfg.addWidget(CaptionLabel("Listen Port"))
        r_cfg.addWidget(self.listen_port)
        r_cfg.addStretch()
        r_cfg.addWidget(self.start_recv_btn)
        r_layout.addLayout(r_cfg)

        filter_box = QHBoxLayout()
        self.filter_input = LineEdit(self.receiver_card)
        self.filter_input.setPlaceholderText("Add filter keyword...")
        self.add_filter_btn = PrimaryToolButton(FIF.ADD, self.receiver_card)
        self.add_filter_btn.clicked.connect(self.add_filter_tag)
        self.filter_input.returnPressed.connect(self.add_filter_tag)
        filter_box.addWidget(CaptionLabel("Filters"))
        filter_box.addWidget(self.filter_input)
        filter_box.addWidget(self.add_filter_btn)
        r_layout.addLayout(filter_box)
        
        # 使用动画容器
        self.tag_container = AnimatedTagContainer(self.receiver_card)
        r_layout.addWidget(self.tag_container)

        self.log_container = FontAdjustableTextEdit(self.receiver_card, is_readonly=True, placeholder="Logs will appear here...")
        self.log_container.setFixedHeight(350)
        r_layout.addWidget(self.log_container)
        
        r_ctrl = QHBoxLayout()
        self.clear_btn = PushButton(FIF.DELETE, "Clear Logs", self.receiver_card)
        r_ctrl.addStretch()
        r_ctrl.addWidget(self.clear_btn)
        r_layout.addLayout(r_ctrl)
        self.vBoxLayout.addWidget(self.receiver_card)

    def add_filter_tag(self, text=None):
        if text is None or isinstance(text, bool):
            text = self.filter_input.text().strip()
        if not text: return
        if any(tag.filter_text == text for tag in self.filter_tags): return
        
        tag = FilterTag(text, self.tag_container.tag_area)
        tag.deleted.connect(self.remove_filter_tag)
        self.tag_container.tag_layout.addWidget(tag)
        self.filter_tags.append(tag)
        self.filter_input.clear()
        
        # 平滑展开
        if len(self.filter_tags) == 1:
            self.tag_container.toggle(True)
        self.save_filters()

    def remove_filter_tag(self, text):
        for tag in self.filter_tags[:]:
            if tag.filter_text == text:
                self.tag_container.tag_layout.removeWidget(tag)
                tag.deleteLater()
                self.filter_tags.remove(tag)
                break
        
        # 平滑折叠
        if not self.filter_tags:
            self.tag_container.toggle(False)
        self.save_filters()

    def save_filters(self):
        filters = [tag.filter_text for tag in self.filter_tags]
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(filters, f)
        except: pass

    def load_filters(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    filters = json.load(f)
                    for text in filters:
                        self.add_filter_tag(text)
            except: pass

class UDPToolApp(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.LIGHT)
        setThemeColor('#0078d4')
        self.setWindowTitle("UDP Broadcaster Pro")
        self.resize(1150, 920)
        self.home_interface = HomeInterface(self)
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self.send_packet)
        self.recv_thread = None
        hi = self.home_interface
        hi.send_once_btn.clicked.connect(self.send_packet)
        hi.start_send_btn.clicked.connect(self.toggle_send_loop)
        hi.start_recv_btn.clicked.connect(self.toggle_receiver)
        hi.clear_btn.clicked.connect(hi.log_container.text_edit.clear)
        hi.send_freq.valueChanged.connect(self.update_live_timer)
        self.addSubInterface(self.home_interface, FIF.HOME, "Control Center")
        
    def send_packet(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            ip, port = self.home_interface.target_ip.text(), self.home_interface.target_port.value()
            data = self.home_interface.payload_container.text_edit.toPlainText().encode('utf-8')
            sock.sendto(data, (ip, port))
            sock.close()
            self.show_toast("Success", f"Packet Sent")
        except Exception as e:
            self.show_toast("Error", str(e), True)

    def show_toast(self, title, content, is_error=False):
        func = InfoBar.error if is_error else InfoBar.success
        func(title=title, content=content, orient=Qt.Horizontal, 
             isClosable=True, position=InfoBarPosition.TOP, duration=1500, parent=self)

    def update_live_timer(self):
        if self.send_timer.isActive():
            self.send_timer.start(int(1000 / self.home_interface.send_freq.value()))

    def toggle_send_loop(self):
        btn = self.home_interface.start_send_btn
        if self.send_timer.isActive():
            self.send_timer.stop()
            btn.setText("Start Loop")
            btn.setIcon(FIF.PLAY)
        else:
            self.send_timer.start(int(1000 / self.home_interface.send_freq.value()))
            btn.setText("Stop Loop")
            btn.setIcon(FIF.PAUSE)

    def toggle_receiver(self):
        btn = self.home_interface.start_recv_btn
        if self.recv_thread and self.recv_thread.isRunning():
            self.recv_thread.stop()
            btn.setText("Start Listening")
            btn.setIcon(FIF.WIFI)
        else:
            self.recv_thread = ReceiverThread(self.home_interface.listen_port.value())
            self.recv_thread.packet_received.connect(self.on_packet_received)
            self.recv_thread.start()
            btn.setText("Stop Listening")
            btn.setIcon(FIF.CLOSE)

    def on_packet_received(self, timestamp, ip, port, data):
        try: text = data.decode('utf-8', errors='replace')
        except: text = data.hex(' ')
        active_filters = [tag.filter_text for tag in self.home_interface.filter_tags if tag.isChecked()]
        if active_filters:
            match = False
            for f in active_filters:
                if f.lower() in text.lower():
                    match = True
                    break
            if not match: return
        self.home_interface.log_container.text_edit.insertPlainText(f"[{timestamp}] {ip}:{port} → {text}\n")
        self.home_interface.log_container.text_edit.moveCursor(QTextCursor.End)

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setWindowIcon(FIF.WIFI.icon())
    ex = UDPToolApp()
    ex.setObjectName("UDPBroadcasterPro")
    ex.show()
    sys.exit(app.exec_())
