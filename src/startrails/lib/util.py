from abc import abstractmethod
import cv2
import numpy
import cupy as cp
from tqdm.auto import tqdm

IMWRITE_OPTIONS = [cv2.IMWRITE_JPEG_QUALITY, 100]


def imwrite(outfile, img, convertBGR=False):
    if not isinstance(img, numpy.ndarray):  # convert cupy array to numpy
        img = cp.asnumpy(img)
    if convertBGR:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    cv2.imwrite(outfile, img, IMWRITE_OPTIONS)


def applyMask(image, masks):
    for mask in masks:
        cv2.fillPoly(image, [mask], (0, 0, 0))
    return image


class Observable():
    jobs = {}
    observers = []

    def startJob(self, label, total):
        self.jobs[label] = {
            "total": total,
            "count": 0,
            "done": False
        }
        self.notifyObservers(label)

    def updateJob(self, label, increment, data=None):
        self.jobs[label]["count"] += increment
        if self.jobs[label]["count"] >= self.jobs[label]["total"]:
            self.jobs[label]["done"] = True

        self.notifyObservers(label, increment, data)

    def notifyObservers(self, label, increment=0, data=None):
        for observer in self.observers:
            observer(
                self.jobs[label]["total"],
                increment,
                self.jobs[label]["count"],
                self.jobs[label]["done"],
                data)

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        self.observers.remove(observer)


class ProgressBar:
    @abstractmethod
    def update(self, total, increment, count, done, _):
        pass


class CmdProgressBar(ProgressBar):
    pbar = None
    label = None

    def __init__(self, label):
        self.label = label

    def update(self, total, increment, count, done, _):
        if self.pbar is None:
            self.pbar = tqdm(desc=self.label, total=total)
        self.pbar.update(increment)
        if done:
            self.pbar.close()
            self.pbar = None
