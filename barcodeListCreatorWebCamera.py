import cv2 #this is OpenCV
import numpy as np
from pyzbar.pyzbar import decode #this runs on top of OpenCv to decode the barcodes

def enhance(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(gray) #boosts contrasts to see in uneven lighting
    blur = cv2.GaussianBlur(clahe, (0,0), 1.0) #adding gaussian blur
    sharp = cv2.addWeighted(clahe, 1.5, blur, -0.5, 0) #sharpening video image


cap = cv2.VideoCapture(0) #opens default camera; should be webcam if plugged in
cap.set(3,640) #picture width
cap.set(4,480) #picture height

camera = True #simple flag to keep loop running

while camera == True:

    success, frame = cap.read() #grabs a frame of the camera

    '''pyzbar returns a list of decoded objects'''
    for code in decode(frame):
        myData = code.data.decode('utf-8') #converts the raw bytes into a string
        print(myData)

        '''list of corner points (x,y) around detected barcode'''
        pts = np.array([code.polygon],np.int32)
        pts = pts.reshape((-1,1,2))
        cv2.polylines(frame,[pts],True,(255,0,255),5) #draws a line around barcode
        
        pts2 = code.rect
        cv2.putText(frame,myData,(pts2[0],pts2[1]),cv2.FONT_HERSHEY_SIMPLEX, 0.9,(255,0,255),2) #label that has decoded barcode

    cv2.imshow('Result',frame) #shows the live view

    cv2.waitKey(1) #this should make it 1fps



