
from PySide6.QtWidgets import QDialog, QButtonGroup
from enum import Enum
from startrails.ui.ui_dialog_stack import Ui_Dialog_StackImages


class FadeRadio(Enum):
    NONE = 1
    START = 2
    END = 3
    BOTH = 4


class StreaksRadio(Enum):
    KEEP = 1
    REMOVE = 2


class StackImagesDialog(QDialog):
    def __init__(self, app, readyStreaksRemoved: bool):
        super().__init__()
        self.ui = UI_StackImagesDialog(app)
        self.ui.setupUi(self, readyStreaksRemoved)


class UI_StackImagesDialog(Ui_Dialog_StackImages):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.useGPU = True

    def setupUi(self, dialog: QDialog, readyStreaksRemoved):
        super().setupUi(dialog)

        self.radio_group_streaks = QButtonGroup()
        self.radio_group_streaks.buttonClicked.connect(self.onClickedStreaksRemoved)
        self.radio_group_streaks.addButton(self.radioButton_streaks_keep)
        self.radio_group_streaks.addButton(self.radioButton_streaks_remove)
        self.radio_group_streaks.setId(self.radioButton_streaks_keep, StreaksRadio.KEEP.value)
        self.radio_group_streaks.setId(self.radioButton_streaks_remove, StreaksRadio.REMOVE.value)
        if readyStreaksRemoved:
            self.radioButton_streaks_remove.setEnabled(True)
            self.radioButton_streaks_remove.setChecked(True)
        else:
            self.radioButton_streaks_keep.setChecked(True)

        self.radio_group_fade = QButtonGroup()
        self.radio_group_fade.buttonClicked.connect(self.onClickedFade)
        self.radio_group_fade.addButton(self.radioButton_fade_none)
        self.radio_group_fade.addButton(self.radioButton_fade_start)
        self.radio_group_fade.addButton(self.radioButton_fade_end)
        self.radio_group_fade.addButton(self.radioButton_fade_both)
        self.radio_group_fade.setId(self.radioButton_fade_none, FadeRadio.NONE.value)
        self.radio_group_fade.setId(self.radioButton_fade_start, FadeRadio.START.value)
        self.radio_group_fade.setId(self.radioButton_fade_end, FadeRadio.END.value)
        self.radio_group_fade.setId(self.radioButton_fade_both, FadeRadio.BOTH.value)
        self.radioButton_fade_both.setChecked(True)

        self.horizontalSlider_fade_amount.valueChanged.connect(self.onChangedFadeAmount)
        self.horizontalSlider_fade_amount.setValue(20)

        self.checkBox_useGPU.setChecked(self.useGPU)
        self.checkBox_useGPU.stateChanged.connect(self.onChangedCheckGPU)
        self.showBatchSize()

    def onClickedStreaksRemoved(self, id):
        button_id = self.radio_group_streaks.id(self.radio_group_streaks.checkedButton())

    def onClickedFade(self, id):
        button_id = self.radio_group_fade.id(self.radio_group_fade.checkedButton())
        if button_id == FadeRadio.NONE.value:
            self.horizontalSlider_fade_amount.setEnabled(False)
        else:
            self.horizontalSlider_fade_amount.setEnabled(True)

    def onChangedCheckGPU(self, checked):
        self.showBatchSize(checked)

    def showBatchSize(self, useGPU=True):
        batchSizeSuggestion, expectedMemoryUsed, gpuAvailable = \
            self.app.stackSuggestBatchSize(self.app.getInputFileList()[0], useGPU)
        self.lineEdit_batchSize.setText(str(batchSizeSuggestion))
        gbUSed = expectedMemoryUsed / 1024 / 1024 / 1024
        deviceText = "GPU" if gpuAvailable else "CPU"
        self.label_memory.setText("{:0.2f} GB {}".format(gbUSed, deviceText))
        self.useGPU = gpuAvailable

    def onChangedFadeAmount(self, value):
        self.label_fade_amount.setText(f"Gradient: {value}%")

    def getFadeAmount(self) -> tuple[int, int]:
        if self.radio_group_fade.checkedId() == FadeRadio.START.value:
            return self.horizontalSlider_fade_amount.value(), 0
        elif self.radio_group_fade.checkedId() == FadeRadio.END.value:
            return 0, self.horizontalSlider_fade_amount.value()
        elif self.radio_group_fade.checkedId() == FadeRadio.BOTH.value:
            return self.horizontalSlider_fade_amount.value(), self.horizontalSlider_fade_amount.value()
        else:
            return 0, 0

    def getFade(self) -> FadeRadio:
        return self.radio_group_fade.id(self.radio_group_fade.checkedButton())

    def getStreaksRemoved(self) -> StreaksRadio:
        return self.radio_group_streaks.id(self.radio_group_streaks.checkedButton())

    def getUseGPU(self):
        return self.useGPU
