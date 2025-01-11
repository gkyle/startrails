
from threading import Thread
import time

class Task(Thread):
    def __init__(self, callback=None):
        Thread.__init__(self)


class TaskQueue(Thread):
    pending = []
    active = {}
    limit = 5
    progressBar = None
    done = False
    
    def __init__(self, progressBar, limit=5):
        Thread.__init__(self)
        self.progressBar = progressBar
        self.limit = limit
        self.daemon = True

    def run(self):
        while(not self.done):
            if len(self.active) < self.limit:
                self.next()
            time.sleep(0.1)

    def append(self, task: Task):
        task.callback=self.complete
        self.pending.append(task)
    
    def next(self):
        if len(self.pending) > 0:
            task = self.pending.pop(0)
            self.active[hash(task)] = task
            task.start()

    def complete(self, task):
        del self.active[hash(task)]
        self.progressBar.update(1)
        if len(self.pending) ==0 and len(self.active) == 0:
            self.done = True