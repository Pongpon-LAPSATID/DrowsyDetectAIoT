# import libraries
from scipy.spatial import distance
from imutils import face_utils
import imutils
import dlib
import cv2
import os
import glob
from pygame import mixer
import rpc

mixer.init()
mixer.music.load("music.wav")

# compute eye ratio
# each eye is represented by 6 (x, y)-coordinates
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear

thresh = 0.25  # threshold
frame_check = 60  # max_count
detect = dlib.get_frontal_face_detector()  # face detection
predict = dlib.shape_predictor(
    "models/shape_predictor_68_face_landmarks.dat")  # .dat is a trained model

# extract the eye regions
(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["right_eye"]

cap = cv2.VideoCapture(0)  # webcam --> need change to esp32 cam
flag = 0  # count for alert

# connect to esp32
def connect_esp32(self):
        port = self.esp32_port.currentText()
        self.rpc_master = rpc.rpc_usb_vcp_master(port)

# **** detected by webcam ****
while True:
    ret, frame = cap.read()
    frame = imutils.resize(frame, width=450)  # set frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # convert from RGB to gray
    subjects = detect(gray, 0)
    for subject in subjects:
        shape = predict(gray, subject)
        shape = face_utils.shape_to_np(shape)  # convert to NumPy array
        leftEye = shape[lStart:lEnd]
        rightEye = shape[rStart:rEnd]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        # draw contours of eye region
        cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
        cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)
        # detect drowsiness logic
        if ear < thresh:
            flag += 1
            print(flag)
            # --> change to 1.(driver) sound alert 2.(owner) line notification
            if flag >= frame_check:
                cv2.putText(frame, "****************ALERT!****************", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(frame, "****************ALERT!****************", (10, 325),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                # print ("Drowsy")
                mixer.music.play()
        else:
            flag = 0
    cv2.imshow("Frame", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
cv2.destroyAllWindows()
cap.release()