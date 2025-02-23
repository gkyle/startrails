from typing import List

from startrails.ui.file import InputFile, OutputFile, Unpickle


class Project(Unpickle):

    def __init__(self, rawInputFiles: List[InputFile] = [], outputFiles: List[OutputFile] = [], projectFile: str = "default_project.json"):
        super().__init__()
        self.rawInputFiles = rawInputFiles
        self.outputFiles = outputFiles
        self.selected = None
        self.operations = {}
        self.projectFile = projectFile
