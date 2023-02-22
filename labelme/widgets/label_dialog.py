import re

from qtpy import QT_VERSION
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtGui import QIntValidator, QDoubleValidator

from labelme.logger import logger
import labelme.utils


QT5 = QT_VERSION[0] == "5"

# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.


class LabelQLineEdit(QtWidgets.QLineEdit):
    def setListWidget(self, list_widget):
        self.list_widget = list_widget

    def keyPressEvent(self, e):
        if e.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            self.list_widget.keyPressEvent(e)
        else:
            super(LabelQLineEdit, self).keyPressEvent(e)


class LabelDialog(QtWidgets.QDialog):
    def __init__(
        self,
        text="Enter object label",
        parent=None,
        labels=None,
        sort_labels=True,
        show_text_field=True,
        completion="startswith",
        fit_to_content=None,
        flags=None,
    ):
        if fit_to_content is None:
            fit_to_content = {"row": False, "column": True}
        self._fit_to_content = fit_to_content

        super(LabelDialog, self).__init__(parent)
        self.labelWithAttrs = None
        self.curRadioButtonAttr = None
        self.radioButtons = None
        self.objAttrsVals = None
        self.objAttributesNumRangeFields = None
        self.layout_range = None
        self.edit = LabelQLineEdit()
        self.edit.setPlaceholderText(text)
        self.edit.setValidator(labelme.utils.labelValidator())
        self.edit.editingFinished.connect(self.postProcess)
        if flags:
            self.edit.textChanged.connect(self.updateFlags)
        self.edit_group_id = QtWidgets.QLineEdit()
        self.edit_group_id.setPlaceholderText("Group ID")
        self.edit_group_id.setValidator(
            QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None)
        )
        layout = QtWidgets.QVBoxLayout()
        if show_text_field:
            layout_edit = QtWidgets.QHBoxLayout()
            layout_edit.addWidget(self.edit, 6)
            layout_edit.addWidget(self.edit_group_id, 2)
            layout.addLayout(layout_edit)
        # buttons
        self.buttonBox = bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.button(bb.Ok).setIcon(labelme.utils.newIcon("done"))
        bb.button(bb.Cancel).setIcon(labelme.utils.newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        # label_list
        self.labelList = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.labelList.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        if self._fit_to_content["column"]:
            self.labelList.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        self._sort_labels = sort_labels
        if labels:
            self.labelList.addItems(labels)
        if self._sort_labels:
            self.labelList.sortItems()
        else:
            self.labelList.setDragDropMode(
                QtWidgets.QAbstractItemView.InternalMove
            )
        self.labelList.currentItemChanged.connect(self.labelSelected)
        self.labelList.itemDoubleClicked.connect(self.labelDoubleClicked)
        self.edit.setListWidget(self.labelList)
        layout.addWidget(self.labelList)
        # label_flags
        if flags is None:
            flags = {}
        self._flags = flags
        self.flagsLayout = QtWidgets.QVBoxLayout()
        self.resetFlags()
        layout.addItem(self.flagsLayout)
        self.edit.textChanged.connect(self.updateFlags)
        self.delObjAttrsTextRangeFields
        self.deleteRangeLayout
        self.customAttrsIndxs = []
        self.customAttrsRange = []
        self.radioButtonsLayout = QtWidgets.QVBoxLayout()
        layout.addItem(self.radioButtonsLayout)
        self.resize(400, 300)
        self.setLayout(layout)
        self.layout = layout
        # completion
        completer = QtWidgets.QCompleter()
        if not QT5 and completion != "startswith":
            logger.warn(
                "completion other than 'startswith' is only "
                "supported with Qt5. Using 'startswith'"
            )
            completion = "startswith"
        if completion == "startswith":
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            # Default settings.
            # completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        elif completion == "contains":
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
        else:
            raise ValueError("Unsupported completion: {}".format(completion))
        completer.setModel(self.labelList.model())
        self.edit.setCompleter(completer)

    def addLabelHistory(self, label):
        if self.labelList.findItems(label, QtCore.Qt.MatchExactly):
            return
        self.labelList.addItem(label)
        if self._sort_labels:
            self.labelList.sortItems()

    def labelSelected(self, item):
        self.edit.setText(item.text())

    def validate(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        if text:
            self.accept()

    def labelDoubleClicked(self, item):
        self.validate()

    def postProcess(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        self.edit.setText(text)

    def updateFlags(self, label_new):
        if label_new == self.labelWithAttrs:
            self.setRadioButtonAttrs([self.curRadioButtonAttr,
                                      self.radioButtons], label_new)
            if not self.customAttrsIndxs:
                self.setTextFieldsAttributes(self.objAttrsVals,
                                             label_new)
                self.setRangeFieldsAttributes(self.objAttributesNumRangeFields,
                                              label_new)
        else:
            self.deleteRadioButtonLayout()
            self.deleteRangeLayout()
            self.delObjAttrsTextRangeFields()
        # keep state of shared flags
        flags_old = self.getFlags()

        flags_new = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label_new):
                for key in keys:
                    flags_new[key] = flags_old.get(key, False)
        self.setFlags(flags_new)

    def deleteFlags(self):
        for i in reversed(range(self.flagsLayout.count())):
            item = self.flagsLayout.itemAt(i).widget()
            self.flagsLayout.removeWidget(item)
            item.setParent(None)

    def deleteRadioButtonLayout(self):
        for i in reversed(range(self.radioButtonsLayout.count())):
            item = self.radioButtonsLayout.itemAt(i).widget()
            self.radioButtonsLayout.removeWidget(item)
            if item is not None:
                item.setParent(None)

    def deleteRangeLayout(self):
        if self.layout_range is None:
            return
        for i in reversed(range(self.layout_range.count())):
            item = self.layout_range.itemAt(i).widget()
            self.layout_range.removeWidget(item)
            if item is not None:
                item.setParent(None)

    def delObjAttrsTextRangeFields(self):
        for i in range(self.layout.count()):
            if self.layout.itemAt(i) is None:
                continue
            for itemLayout in self.customAttrsIndxs:
                if self.layout.indexOf(itemLayout) >= 0:
                    self.layout.removeWidget(self.layout.itemAt(self.layout.indexOf(itemLayout)).widget())
        self.customAttrsIndxs.clear()

    def resetFlags(self, label=""):
        flags = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label):
                for key in keys:
                    flags[key] = False
        self.setFlags(flags)

    def setFlags(self, flags):
        self.deleteFlags()
        for key in flags:
            item = QtWidgets.QCheckBox(key, self)
            item.setChecked(flags[key])
            self.flagsLayout.addWidget(item)
            item.show()

    def getFlags(self):
        flags = {}
        for i in range(self.flagsLayout.count()):
            item = self.flagsLayout.itemAt(i).widget()
            flags[item.text()] = item.isChecked()
        return flags

    def getGroupId(self):
        group_id = self.edit_group_id.text()
        if group_id:
            return int(group_id)
        return None

    def getRadioButtonsObjAttrs(self):
        if self.radioButtonsLayout is None:
            return
        headDirections = {}
        for i in range(self.radioButtonsLayout.count()):
            item = self.radioButtonsLayout.itemAt(i).widget()
            headDirections[item.text()] = item.isChecked()
        return [headDir for headDir, present in headDirections.items()
                if headDirections[headDir]]

    def getObjAtributesTextFields(self):
        try:
            objAttrs = self.objAttrsVals[0]
        except KeyError:
            objAttrs = self.objAttrsVals
        objAtributesTextFields = {}
        for i in range(self.layout.count()):
            itemName = self.layout.itemAt(i).widget()
            # Check if widget is of type QLabel or QLineEdit
            try:
                if itemName.text() in objAttrs.keys():
                    itemVal = self.layout.itemAt(i+1).widget()
                    objAtributesTextFields[itemName.text()] = itemVal.text()
            except AttributeError:
                continue
        return objAtributesTextFields

    def getObjAtributesNumRangeFields(self):
        attrs = self.objAttributesNumRangeFields
        objAtributesNumRangeFields = {}
        numRangeFieldsVals = []
        try:
            objAttrs = attrs[0]
        except KeyError:
            objAttrs = attrs
        if self.layout_range is None:
            return
        for i in range(self.layout_range.count()):
            itemName = self.layout_range.itemAt(i).widget()
            if objAttrs is None:
                if itemName.text() is not None and itemName.text()\
                        not in attrs[1].keys():
                    numRangeFieldsVals.append(itemName.text())
            else:
                if itemName.text() in objAttrs.keys():
                    itemVal = self.layout_range.itemAt(i+1).widget()
                    objAtributesNumRangeFields[itemName.text()] = itemVal.text()
        if objAttrs is None:
            for indx, key in enumerate(attrs[1].keys()):
                objAtributesNumRangeFields[key] = numRangeFieldsVals[indx]
        return objAtributesNumRangeFields

    def setRadioButtonAttrs(self, attrVals, label=""):
        self.deleteRadioButtonLayout()
        if self.layout_range is not None:
            self.deleteRangeLayout()
        if label != self.labelWithAttrs \
                or not label or attrVals[1] is None:
            return
        for key in attrVals[1]:
            item = QRadioButton(key, self)
            if self.disabledLayouts.get("disable_radio_buttons"):
                item.setEnabled(False)
            if attrVals[0] is not None:
                if self.curRadioButtonAttr is not None\
                        and attrVals[0][0] == key:
                    item.setChecked(True)
                else:
                    item.setChecked(False)
            else:
                item.setChecked(False)
            if self.disabledLayouts.get("disable_radio_buttons") \
                    and self.curRadioButtonAttr is None:
                raise Exception("Please remove 'radio_buttons' "
                                "from 'object_radio_buttons' dictionary "
                                "or set 'disable_radio_buttons' to False "
                                "in the config file, if you want to create "
                                "a label with 'radio_buttons' attribute!")
            self.radioButtonsLayout.addWidget(item)
            item.show()

    def setTextFieldsAttributes(self, objAttrsVals, label=""):
        self.delObjAttrsTextRangeFields()
        intValidator = QIntValidator()
        objAttrsValsAreEmpty = False
        floatValidator = QtGui.QDoubleValidator(
                notation=QtGui.QDoubleValidator.StandardNotation
            )
        try:
            if objAttrsVals[0] is None:
                objAttrs = {}
                objAttrsValsAreEmpty = True
                for key, val in objAttrsVals[1].items():
                    if val == "str":
                        objAttrs[key] = "name"
                    elif val == "int":
                        objAttrs[key] = 0
                    else:
                        objAttrs[key] = 0.0
                self.objAttrsVals[0] = objAttrs
                objAttrs = self.objAttrsVals[0]
            else:
                objAttrs = self.objAttrsVals[0]
        except KeyError:
            objAttrs = self.objAttrsVals
        if len(self.objAttrsVals) < 1:
            return
        if self.objAttrsVals is None or label != self.labelWithAttrs:
            return
        for attr in objAttrs.keys():
            itemName = QtWidgets.QLineEdit()
            if not objAttrsValsAreEmpty:
                if self.disabledLayouts.get("disable_text_fields"):
                    itemName.setEnabled(False)
                try:
                    float(objAttrs[attr])
                    itemName.setValidator(floatValidator)
                except ValueError:
                    if objAttrs[attr] == "int" or objAttrs[attr].isdigit():
                        itemName.setValidator(intValidator)
                    elif objAttrs[attr] == "float" or objAttrs[attr].isdigit() and "." in objAttrs[attr]:
                        itemName.setValidator(floatValidator)
                    else:
                        itemName.setValidator(labelme.utils.labelValidator())
            itemValue = QtWidgets.QLabel()
            if objAttrs is not None:
                itemValue.setText(f"{attr}")
                if objAttrs[attr] not in ["int", "str", "float"]:
                    itemName.setText(f"{objAttrs[attr]}")
                else:
                    itemName.setText(f"")
                if self.disabledLayouts.get("disable_text_fields"):
                    if objAttrs[attr] == "int"\
                            or objAttrs[attr] == "str"\
                            or objAttrs[attr] == "float":
                        raise Exception("Please remove 'text_fields' "
                                        "from 'object_attrs_values' dictionary "
                                        "or set 'disable_text_fields' to False in "
                                        "the config file, if you want to create a "
                                        "label with 'text_fields' attribute!")
            self.layout.addWidget(itemValue)
            self.layout.addWidget(itemName)
            itemName.show()
            self.customAttrsIndxs.append(itemValue)
            self.customAttrsIndxs.append(itemName)

    def setRangeFieldsAttributes(self, objAttributesNumRangeFields, label=""):
        try:
            if objAttributesNumRangeFields[0] is None:
                objAttrs = {}
                for key, val in objAttributesNumRangeFields[1].items():
                    if val == "str":
                        objAttrs[key] = "name"
                    elif val == "int":
                        objAttrs[key] = 0
                    else:
                        objAttrs[key] = 0.0
            else:
                objAttrs = objAttributesNumRangeFields[0]
        except KeyError:
            objAttrs = objAttributesNumRangeFields
        if objAttributesNumRangeFields is None or\
                label != self.labelWithAttrs:
            return
        intValidator = QIntValidator()
        floatValidator = QtGui.QDoubleValidator(
            notation=QtGui.QDoubleValidator.StandardNotation
        )
        layout_range = QtWidgets.QHBoxLayout()
        for key in objAttrs.keys():
            textFieldLabel = QtWidgets.QLabel()
            textFieldLabel.setText(key)
            textFieldtext = QtWidgets.QLineEdit()
            if self.disabledLayouts.get("disable_numeric_range"):
                textFieldtext.setEnabled(False)
            try:
                float(objAttrs[key])
                textFieldtext.setValidator(floatValidator)
            except ValueError:
                if objAttrs[key] == "int" \
                        or objAttrs[key].isdigit():
                    textFieldtext.setValidator(intValidator)
                elif objAttrs[key] == "float" \
                        or objAttrs[key].isdigit() and "." in objAttrs[key]:
                    textFieldtext.setValidator(floatValidator)
                else:
                    textFieldtext.setValidator(labelme.utils.labelValidator())
            if objAttrs is not None:
                if str(objAttrs[key]) not in ["int", "str", "float"]:
                    if objAttributesNumRangeFields[0] is not None:
                        textFieldtext.setText(str(objAttributesNumRangeFields[0][key]))
                    else:
                        textFieldtext.setText(f"")
                else:
                    textFieldtext.setText(f"")
                if self.disabledLayouts.get("disable_numeric_range"):
                    if objAttrs[key] == "int"\
                        or objAttrs[key] == "str"\
                            or objAttrs[key] == "float":
                        raise Exception("Please remove 'numeric_range' "
                                        "from 'object_attrs_values' dictionary "
                                        "or set 'disable_numeric_range' to False"
                                        " in the config file, if you want to create"
                                        " a label with 'numeric_range' attribute!")
            layout_range.addWidget(textFieldLabel, 2)
            layout_range.addWidget(textFieldtext, 3)
            self.customAttrsRange.append(textFieldLabel)
            self.customAttrsRange.append(textFieldtext)
        self.layout_range = layout_range
        self.layout.addLayout(layout_range)

    def popUp(self,
              text=None, move=True, flags=None,
              group_id=None,
              label_with_attrs=None, chosen_radio_button_obj_attr=None,
              radio_buttons=None, text_fields=None,
              numeric_range=None, disabled_layouts=None
    ):
        if self._fit_to_content["row"]:
            self.labelList.setMinimumHeight(
                self.labelList.sizeHintForRow(0) * self.labelList.count() + 2
            )
        if self._fit_to_content["column"]:
            self.labelList.setMinimumWidth(
                self.labelList.sizeHintForColumn(0) + 2
            )
        # if text is None, the previous label in self.edit is kept
        self.labelWithAttrs = label_with_attrs
        self.objAttrsVals = text_fields
        self.objAttributesNumRangeFields = numeric_range
        self.disabledLayouts = disabled_layouts
        if radio_buttons is not None:
            self.curRadioButtonAttr = chosen_radio_button_obj_attr
            self.radioButtons = radio_buttons
        if text is None:
            text = self.edit.text()
        if flags:
            self.setFlags(flags)
        else:
            self.resetFlags(text)
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))
        if text != self.labelWithAttrs:
            self.deleteRadioButtonLayout()
            self.deleteRangeLayout()
        if group_id is None:
            self.edit_group_id.clear()
        else:
            self.edit_group_id.setText(str(group_id))
        items = self.labelList.findItems(text, QtCore.Qt.MatchFixedString)
        if text_fields is not None:
            self.objAttrsVals = self.objAttrsVals
            self.objAttributesNumRangeFields = self.objAttributesNumRangeFields
            self.setTextFieldsAttributes(self.objAttrsVals)
            self.setRangeFieldsAttributes(self.objAttributesNumRangeFields)
        if chosen_radio_button_obj_attr is not None and radio_buttons is not None:
            self.radioButtons = radio_buttons
            self.setRadioButtonAttrs([self.curRadioButtonAttr, self.radioButtons], "")
        if items:
            if len(items) != 1:
                logger.warning("Label list has duplicate '{}'".format(text))
            self.labelList.setCurrentItem(items[0])
            row = self.labelList.row(items[0])
            self.edit.completer().setCurrentRow(row)
        self.edit.setFocus(QtCore.Qt.PopupFocusReason)
        if move:
            self.updateFlags(text)
            self.move(QtGui.QCursor.pos())
        if self.exec_():
            return (
                self.edit.text(),
                self.getFlags(),
                self.getGroupId(),
                self.getRadioButtonsObjAttrs(),
                self.getObjAtributesTextFields(),
                self.getObjAtributesNumRangeFields()
            )
        else:
            return None, None, None, None, None, None
