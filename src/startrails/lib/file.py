from enum import Enum


class Unpickle:
    # forces reinitialization of instance during unpickling so that fields that weren't present at pickling time are present at run time.
    def __getstate__(self):
        return super().__getstate__()

    def __setstate__(self, state: dict):
        self.__init__()
        self.__dict__.update(state)


class File(Unpickle):

    def __init__(self, basename=None, path=None):
        super().__init__()
        self.basename = basename
        self.path = path


class InputFile(File):

    def __init__(self, basename=None, path=None):
        super().__init__(basename, path)
        self.streaksMasks = []
        self.streaksManualMasks = []
        self.activeMaskPoints = []
        self.excludeFromStack = False


class OutputFile(File):

    def __init__(self, basename=None, path=None, operation=None, fadeGradient=None):
        super().__init__(basename, path)
        self.operation = operation
        self.fadeGradient = fadeGradient


class Operation(Enum):
    STACK = 1
    FILL_GAPS = 2
    FILL_GAPS_MASK = 3
