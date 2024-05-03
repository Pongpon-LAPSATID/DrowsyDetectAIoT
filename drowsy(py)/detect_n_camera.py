import sys
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QPixmap
import cv2
import numpy as np
import serial.tools.list_ports
import dlib
from imutils import face_utils
from scipy.spatial import distance
from pygame import mixer
import rpc

mixer.init()
mixer.music.load("music.wav")

# Constants for drowsiness detection
thresh = 0.25  # Threshold for eye aspect ratio
frame_check = 60  # Number of frames to check for drowsiness

# Load face detection model
detector = dlib.get_frontal_face_detector()
predict = dlib.shape_predictor("models/shape_predictor_68_face_landmarks.dat")  # Update with the path to your model file

class ImgLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        self.status = 'CLICKED'
        self.pos_1st = ev.position()
        self.clicked.emit()
        return super().mousePressEvent(ev)
    
    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        self.status = 'RELEASED'
        self.pos_2nd = ev.position()
        self.clicked.emit()
        return super().mouseReleaseEvent(ev)

class EspCamWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.rpc_master = None
        self.capture_timer = None
        self.drowsy_counter = 0
        self.music_playing = False  # Flag to indicate if music is playing
        self.populate_ui()

    def populate_ui(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.populate_ui_image()
        self.populate_ui_ctrl()
        self.main_layout.addLayout(self.image_layout)
        self.main_layout.addLayout(self.ctrl_layout)

    def populate_ui_image(self):
        self.image_layout = QtWidgets.QVBoxLayout()
        self.image_layout.setAlignment(QtCore.Qt.AlignTop)
        self.preview_img = QtWidgets.QLabel("Preview Image")
        self.preview_img.resize(320, 240)
        self.image_layout.addWidget(self.preview_img)

    def populate_ui_ctrl(self):
        self.ctrl_layout = QtWidgets.QFormLayout() 
        self.ctrl_layout.setAlignment(QtCore.Qt.AlignTop)
        
        self.esp32_port = QtWidgets.QComboBox()
        self.esp32_port.addItems([port for (port, desc, hwid) in serial.tools.list_ports.comports()])
        self.ctrl_layout.addRow("ESP32 Port", self.esp32_port)

        self.esp32_button = QtWidgets.QPushButton("Connect")
        self.esp32_button.clicked.connect(self.connect_esp32)
        self.ctrl_layout.addRow(self.esp32_button)

        self.stop_music_button = QtWidgets.QPushButton("Stop Music")
        self.stop_music_button.setEnabled(False)
        self.stop_music_button.clicked.connect(self.stop_music)
        self.ctrl_layout.addRow(self.stop_music_button)

    def connect_esp32(self):
        port = self.esp32_port.currentText()
        try:
            self.rpc_master = rpc.rpc_usb_vcp_master(port)
            self.esp32_button.setText("Connected")
            self.esp32_button.setEnabled(False)
            self.start_capture_timer()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def start_capture_timer(self):
        self.capture_timer = QtCore.QTimer(self)
        self.capture_timer.timeout.connect(self.capture_photo)
        self.capture_timer.start(1000)  # Capture every 1 second

    def capture_photo(self):
        if self.rpc_master is None:
            return

        try:
            result = self.rpc_master.call("jpeg_image_snapshot", recv_timeout=1000)
            if result is not None:
                jpg_sz = int.from_bytes(result.tobytes(), "little")
                buf = bytearray(b'\x00' * jpg_sz)
                result = self.rpc_master.call("jpeg_image_read", recv_timeout=1000)
                self.rpc_master.get_bytes(buf, jpg_sz)
                img = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
                drowsy = self.detect_drowsiness(img)
                if drowsy:
                    print(1) #if detected close eyes print result 1
                    self.drowsy_counter += 1
                    if self.drowsy_counter >= 3 and not self.music_playing:  # Start music if not already playing
                        mixer.music.play(-1)  # -1 loops the music indefinitely
                        self.music_playing = True
                        self.stop_music_button.setEnabled(True)
                else:
                    print(0) #if detected open eyes print result 0
                    self.drowsy_counter = 0

                self.update_image(img.copy())
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "Failed to capture photo.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def detect_drowsiness(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        subjects = detector(gray, 0)
        for subject in subjects:
            shape = predict(gray, subject)
            shape = face_utils.shape_to_np(shape)
            left_eye = shape[42:48]
            right_eye = shape[36:42]
            left_ear = self.eye_aspect_ratio(left_eye)
            right_ear = self.eye_aspect_ratio(right_eye)
            ear = (left_ear + right_ear) / 2.0
            if ear < thresh:
                return True
        return False

    def eye_aspect_ratio(self, eye):
        A = distance.euclidean(eye[1], eye[5])
        B = distance.euclidean(eye[2], eye[4])
        C = distance.euclidean(eye[0], eye[3])
        ear = (A + B) / (2.0 * C)
        return ear

    def update_image(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = img.shape
        img = QtGui.QImage(img.data, w, h, QtGui.QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self.preview_img.setPixmap(pixmap.scaled(320, 240, QtCore.Qt.KeepAspectRatio))

    def stop_music(self): #press button to stop music
        if self.music_playing:
            mixer.music.stop()
            self.music_playing = False
            self.stop_music_button.setEnabled(False)

    def closeEvent(self, event): # press X to close window and stop music
        if self.rpc_master is not None:
            self.rpc_master.close()
        if self.music_playing:
            mixer.music.stop()

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = EspCamWidget()
    widget.resize(640, 480)
    widget.show()
    sys.exit(app.exec())
