import os
import sys
from pathlib import Path
from threading import Event
from typing import Callable, Optional, Union
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


class Observable:
    def __init__(
        self,
        cancel_event: Optional[Event] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        self.job: Optional[Job] = None
        self.observers = []
        self.cancel_event = cancel_event if cancel_event is not None else Event()
        self.cancel_check = cancel_check

    def startJob(self, total):
        self.job = Job(total)
        self.notifyObservers()

    def updateJob(self, increment, data=None):
        if self.job is not None:
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
        self.cancel_event.set()
        if self.job is not None:
            self.job.interrupt = True

    def shouldInterrupt(self):
        return (
            self.cancel_event.is_set()
            or (self.job.interrupt if self.job is not None else False)
            or bool(self.cancel_check and self.cancel_check())
        )

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        self.observers.remove(observer)
