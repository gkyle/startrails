from typing import List, Optional

from startrails.lib.file import InputFile, OutputFile, Unpickle


class Project(Unpickle):

    def __init__(
        self,
        rawInputFiles: Optional[List[InputFile]] = None,
        outputFiles: Optional[List[OutputFile]] = None,
        projectFile: str = "projects/default.project.json",
        sortBy: str = "date",
        sortOrder: str = "asc",
    ):
        super().__init__()
        self.rawInputFiles = list(rawInputFiles) if rawInputFiles is not None else []
        self.outputFiles = list(outputFiles) if outputFiles is not None else []
        self.selected = None
        self.operations = {}
        self.projectFile = projectFile
        self.sortBy = sortBy
        self.sortOrder = sortOrder
