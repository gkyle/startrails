import cv2
import numpy
try:
    import cupy as cp
except:
    pass

IMWRITE_OPTIONS = [cv2.IMWRITE_JPEG_QUALITY, 100]


def imwrite(outfile, img, convertBGR=False):
    try:
        if not isinstance(img, numpy.ndarray):  # convert cupy array to numpy
            img = cp.asnumpy(img)
    except:
        pass
    if convertBGR:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    cv2.imwrite(outfile, img, IMWRITE_OPTIONS)


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
        self.job.interrupt = True

    def shouldInterrupt(self):
        return self.job.interrupt

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        self.observers.remove(observer)
