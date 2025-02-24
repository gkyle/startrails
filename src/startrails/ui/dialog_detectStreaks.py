
from PySide6.QtWidgets import QDialog, QButtonGroup
from enum import Enum
from startrails.ui.ui_dialog_streaks import Ui_Dialog_DetectStreaks


class MergeRadio(Enum):
    NMS = 1
    GREEDY_NMM = 2


class DetectStreaksDialog(QDialog):
    def __init__(self, app):
        super().__init__()
        self.ui = UI_DetectStreaksDialog(app)
        self.ui.setupUi(self)


class UI_DetectStreaksDialog(Ui_Dialog_DetectStreaks):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.useGPU = True

    def setupUi(self, dialog: QDialog):
        super().setupUi(dialog)

        self.radio_group_merge = QButtonGroup()
        self.radio_group_merge.buttonClicked.connect(self.onClickedMerge)
        self.radio_group_merge.addButton(self.radioButton_merge_nms)
        self.radio_group_merge.addButton(self.radioButton_merge_greedy_nmm)
        self.radio_group_merge.setId(self.radioButton_merge_nms, MergeRadio.NMS.value)
        self.radio_group_merge.setId(self.radioButton_merge_greedy_nmm, MergeRadio.GREEDY_NMM.value)
        self.radioButton_merge_nms.setChecked(True)

        self.getPreferredDevice()

    def onClickedMerge(self, id):
        button_id = self.radio_group_merge.id(self.radio_group_merge.checkedButton())

    def onChangedCheckGPU(self, checked):
        self.getPreferredDevice(checked)

    def getPreferredDevice(self, useGPU=True):
        _, _1, gpuAvailable = \
            self.app.stackSuggestBatchSize(self.app.getInputFileList()[0], useGPU)
        self.useGPU = gpuAvailable
        self.checkBox_useGPU.setChecked(gpuAvailable)

    def getMergeMethod(self) -> str:
        val = self.radio_group_merge.id(self.radio_group_merge.checkedButton())
        if val == MergeRadio.NMS.value:
            return "NMS"
        else:
            return "GREEDYNMM"

    def getUseGPU(self):
        return self.useGPU
