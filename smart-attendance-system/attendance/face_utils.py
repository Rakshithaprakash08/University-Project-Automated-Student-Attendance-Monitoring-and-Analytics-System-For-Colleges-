import face_recognition
import cv2
import os
import numpy as np

KNOWN_ENCODINGS = []
KNOWN_NAMES = []

def load_known_faces():
    folder = "static/students"

    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        image = face_recognition.load_image_file(path)
        encodings = face_recognition.face_encodings(image)

        if encodings:
            KNOWN_ENCODINGS.append(encodings[0])
            KNOWN_NAMES.append(file.split(".")[0])

def recognize_face(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_encodings(rgb)

    for face in faces:
        matches = face_recognition.compare_faces(KNOWN_ENCODINGS, face)

        if True in matches:
            return KNOWN_NAMES[matches.index(True)]

    return None