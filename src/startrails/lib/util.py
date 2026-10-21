import os
import sys
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy
try:
    import cupy as cp
except:
    pass

from startrails.lib.image_io import IMWRITE_OPTIONS, imread, imwrite


def applyMask(image, masks):
    for mask in masks:
        cv2.fillPoly(image, [mask], (0, 0, 0))
    return image


class Job:
    def __init__(self, total):
        self.total = total
        self.count = 0
        self.done = False
        self.interrupt = False


class Observable():
    def __init__(self):
        self.job: Job = None
        self.observers = []

    def startJob(self, total):
        self.job = Job(total)
        self.notifyObservers()

    def updateJob(self, increment, data=None):
        if not self.job is None:
            self.job.count += increment
            if self.job.count >= self.job.total:
                self.job.done = True

        self.notifyObservers(increment, data)

    def notifyObservers(self, increment=0, data=None):
        for observer in self.observers:
            observer(
                self.job.total,
                increment,
                self.job.count,
                self.job.done,
                data)

    def requestInterrupt(self):
        if self.job is not None:
            self.job.interrupt = True

    def shouldInterrupt(self):
        return self.job.interrupt if self.job is not None else False

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        self.observers.remove(observer)
