import cv2
import numpy
import cupy as cp

def imwrite(outfile, img, convertBGR=False):
    if not isinstance(img, numpy.ndarray): # convert cupy array to numpy
        img = cp.asnumpy(img)
    if convertBGR:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    cv2.imwrite(outfile, img)