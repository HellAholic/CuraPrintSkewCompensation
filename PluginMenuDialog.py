import os
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QCheckBox, QLabel, QTextEdit, QSizePolicy, QScrollArea, QWidget,
    QListWidget, QListWidgetItem, QSplitter
)
from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Logger import Logger

from .PluginConstants import PluginConstants

catalog = i18nCatalog("cura")

# --- HelpDialog class ---
class HelpDialog(QDialog):
    def __init__(self, help_topics, initial_topic_key=None, parent=None):
        super().__init__(parent)
        self.help_topics = help_topics
        self.setWindowTitle(catalog.i18n("Detailed Explanations"))
        self.setFixedSize(PluginConstants.MINIMUM_DIALOG_WIDTH, PluginConstants.MAXIMUM_DIALOG_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.topic_list_widget = QListWidget()
        self.topic_list_widget.setMaximumWidth(220)
        self.topic_list_widget.setStyleSheet(PluginConstants.HELP_PAGE_STYEL)

        self.content_display_area = QTextEdit()
        self.content_display_area.setReadOnly(True)
        self.content_display_area.setStyleSheet(PluginConstants.HELP_PAGE_STYEL)

        splitter.addWidget(self.topic_list_widget)
        splitter.addWidget(self.content_display_area)
        splitter.setSizes(PluginConstants.HELP_PAGE_SPLIT_SIZE)

        layout.addWidget(splitter)

        close_button = QPushButton(catalog.i18n("Close"))
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet(PluginConstants.CLOSE_BUTTON_STYLE)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self._populate_topics()
        self.topic_list_widget.currentItemChanged.connect(self._on_topic_selected)

        if initial_topic_key:
            self.select_topic(initial_topic_key)
        elif self.topic_list_widget.count() > 0:
            self.topic_list_widget.setCurrentRow(0)

    def _populate_topics(self):
        for key, data in self.help_topics.items():
            item = QListWidgetItem(data["title"])
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.topic_list_widget.addItem(item)

    def _on_topic_selected(self, current_item, previous_item):
        if current_item:
            topic_key = current_item.data(Qt.ItemDataRole.UserRole)
            if topic_key in self.help_topics:
                self.content_display_area.setHtml(self.help_topics[topic_key]["content"])

    def select_topic(self, topic_key):
        for i in range(self.topic_list_widget.count()):
            item = self.topic_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == topic_key:
                self.topic_list_widget.setCurrentItem(item)
                return
        if self.topic_list_widget.count() > 0:
            self.topic_list_widget.setCurrentRow(0)

class PluginMenuDialog(QDialog):
    """
    The main menu dialog for the Print Skew Compensation plugin.

    This dialog provides a user interface to:
    - Enable or disable skew compensation.
    - Choose the compensation method (Marlin G-code, Klipper G-code, or Cura Post-Processing Script).
    - View the generated G-code commands for Marlin and Klipper.
    - Open the dialog to enter/edit skew measurements.
    - Add calibration models (XY, XZ, YZ, or all) to the build plate.
    - Toggle the Cura Post-Processing script for skew compensation.
    """

    # Signals for actions triggered by the user
    enter_measurements_requested = pyqtSignal()
    add_model_requested = pyqtSignal(str) # xy, xz, yz, all
    add_marlin_gcode_toggled = pyqtSignal(bool)
    add_klipper_gcode_toggled = pyqtSignal(bool)
    restore_models_requested = pyqtSignal()
    apply_transform_requested = pyqtSignal()
    enable_compensation_toggled = pyqtSignal(bool)
    toggle_post_processing_script_requested = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        """
        Initializes the PluginMenuDialog.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.setWindowTitle(catalog.i18n("Print Skew Compensation Menu"))
        self.setFixedSize(PluginConstants.MINIMUM_DIALOG_WIDTH, PluginConstants.MAXIMUM_DIALOG_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE)

        main_layout = QVBoxLayout(self)
        self.active_printer = Application.getInstance().getGlobalContainerStack().getName()

        # --- Help Content ---
        self.help_content = {
            "calibration_models": {
                "title": catalog.i18n("Calibration Models"),
                "content": catalog.i18n("""
                    <h2>1. Printing Calibration Models</h2>
                    <p>This section allows you to add calibration models directly to your build plate. These models are designed to help you accurately measure your printer's skew on different planes.</p>
                    <p><b>XY Plane Model:</b> Used for measuring skew in the XY plane (this is the most common type of printer skew, often related to the printer frame not being perfectly square). The model should be printed with its text facing up.</p>
                    <p><b>XZ Plane Model:</b> Used for measuring skew between the X and Z axes (e.g., if one Z-axis tower leans forward or backward relative to the X-axis). The model should be printed with its text facing the front of the printer.</p>
                    <p><b>YZ Plane Model:</b> Used for measuring skew between the Y and Z axes (e.g., if one Z-axis tower leans sideways relative to the Y-axis). The model should be printed with its text facing the right side of the printer.</p>
                    <p><b>All 3 Models:</b> Adds all three calibration models to the build plate simultaneously. Ensure you orient each model correctly as described above.</p>
                    <p><b>Scaling:</b> You are encouraged to scale these models up if your build plate allows. Larger models generally yield more accurate skew measurements because any measurement error becomes a smaller percentage of the total length measured. You may wish to scale them down for smaller printers.  Looking at the face of any model - the width and height must always be scaled uniformly.  You may scale the 'thickness' differently to save material.</p>
                    <p><b>Orientation:</b> Correct orientation is crucial for accurate measurements. The text on the models indicates the intended 'up' or 'front' direction relative to the printer's axes. Misorienting the models will lead to incorrect skew factor calculations.  Some printers with the origin at the right-rear (Creality Ender 5 and 6 for example) will need the model orientation rotated 180° from 'normal'.  You must know your machine to properly orient the models.</p>
                """)
            },
            "measurements": {
                "title": catalog.i18n("Entering Measurements"),
                "content": catalog.i18n("""
                    <h2>2. Entering Measurements and Calculating Skew Factors</h2>
                    <p>After printing the calibration model(s), you need to measure them carefully using a precise instrument like digital calipers.  Take a look at the surfaces that will be measured and insure there are no 'pips' sticking up.  You want to measure 'across the flats'.</p>
                    <p>The 'Enter Measurements and Calculate Skew Factors' button opens a separate dialog. In this dialog, you will input the dimensions you measured from your printed calibration models. The plugin compares these measurements to the ideal dimensions of the models to calculate the 'skew factors' needed for compensation.</p>
                    <p><b>Machine Specific:</b> It is very important to understand that these measurements and the resulting skew factors are specific to the currently active printer profile in Cura, which is <b>'{printer_name}'</b>. If you have multiple 3D printers, or even different nozzle/material setups on the same printer that might affect dimensional accuracy, you must repeat the entire 'Print Calibration Model(s) -> Measure -> Enter Measurements' process for each distinct printer configuration for which you want to apply skew compensation.</p>
                    <p><b>Accuracy:</b> The accuracy of your skew compensation depends directly on the accuracy of your measurements. Take multiple readings if possible and ensure your measuring tool is calibrated.</p>
                """).format(printer_name=self.active_printer)
            },
            "marlin_method": {
                "title": catalog.i18n("Marlin M852 Method"),
                "content": catalog.i18n("""
                    <h2>3a. Marlin Method (M852 G-code)</h2>
                    <p>This compensation method is designed for printers running Marlin firmware that has skew correction features enabled (specifically, support for the <code>M852</code> G-code command).</p>
                    <p><b>How it works:</b> Based on the skew factors calculated from your measurements, the plugin generates an <code>M852</code> command (e.g., <code>M852 I[XY_skew_factor] J[XZ_skew_factor] K[YZ_skew_factor]</code>). This command instructs the Marlin firmware to apply real-time adjustments to motor movements to counteract the measured skew.</p>
                    <p><b>Plugin Action:</b> If you check the "Marlin - Insert M852 into the G-code file" option, the plugin will automatically add the calculated <code>M852</code> command near the beginning of every G-code file generated by Cura (typically, it's inserted after your machine's standard Start G-code sequence).</p>
                    <p><b>Manual Alternative:</b> You can view the generated <code>M852</code> command in the text box. If you prefer, you can copy this command and manually add it to the 'Start G-code' section in Cura's Machine Settings for your printer. If you do this, you would typically uncheck the "Insert M852" option in the plugin to avoid adding the command twice. This approach makes the compensation part of your printer's default startup routine.</p>
                    <p><b>Firmware Requirement:</b> Ensure that your specific version of Marlin firmware is compiled with <code>SKEW_CORRECTION</code> (or a similarly named feature that enables <code>M852</code>) enabled. If not, the <code>M852</code> command will be ignored by the printer.</p>
                """)
            },
            "klipper_method": {
                "title": catalog.i18n("Klipper SET_SKEW Method"),
                "content": catalog.i18n("""
                    <h2>3b. Klipper Method (SET_SKEW G-code)</h2>
                    <p>This method is for printers running Klipper firmware. Klipper typically handles skew correction via a <code>[skew_correction]</code> module in its <code>printer.cfg</code> file, which then allows the use of a <code>SET_SKEW</code> G-code command (or a custom macro that implements similar functionality).</p>
                    <p><b>How it works:</b> The plugin calculates the necessary parameters for Klipper's skew correction (e.g., <code>XY_SKEW</code>, <code>XZ_SKEW</code>, <code>YZ_SKEW</code>) and formats them into a <code>SET_SKEW</code> command (e.g., <code>SET_SKEW XY=[value] XZ=[value] YZ=[value]</code>).</p>
                    <p><b>Plugin Action:</b> If "Klipper - Insert SET_SKEW into the G-code file" is checked, the plugin will add this <code>SET_SKEW</code> command to the start of your G-code files, after the StartUp G-code.</p>
                    <p><b>Manual Alternative:</b> You can copy the generated <code>SET_SKEW</code> command. Many Klipper users prefer to add this to their <code>PRINT_START</code> macro in their <code>printer.cfg</code> file, or define the skew parameters directly in the <code>[skew_correction]</code> section of <code>printer.cfg</code>. If you configure it directly in Klipper or via your start macro, you would uncheck the plugin's insertion option.</p>
                    <p><b>Klipper Configuration:</b> You must have the <code>[skew_correction]</code> module (or an equivalent custom macro setup) configured in your Klipper <code>printer.cfg</code> file for the <code>SET_SKEW</code> command to be effective. Consult the Klipper documentation for details on setting this up.  If you are using a different macro name for Skew Compensation then you should change it to 'SET_SKEW' or alternatively use Search and Replace to change 'SET_SKEW' to your macro name.</p>
                """)
            },
            "cura_method": {
                "title": catalog.i18n("Cura Post-Processing Method"),
                "content": catalog.i18n("""
                    <h2>3c. Cura Method (Post-Process the G-code)</h2>
                    <p>This method uses a Cura post-processing script (bundled with this plugin) to directly modify the G-code paths to counteract printer skew. This is a software-level compensation applied by Cura before the G-code file is saved.</p>
                    <p><b>How it works:</b> When this option is enabled, the plugin activates its post-processing script named 'PrintSkewCompensationCKM.py'. This script takes the calculated skew factors and applies a mathematical transformation (an affine transformation matrix) to all X, Y, and Z coordinates in the G-code. Essentially, it pre-distorts the model's G-code in the opposite direction of your printer's skew, so that the physical print comes out corrected.</p>
                    <p><b>Plugin Action:</b> Checking the "Cura - Post-Process the G-Code file to counteract the Skew" option will add the 'PrintSkewCompensationCKM.py' script to Cura's list of active post-processing scripts. You can verify this under 'Extensions > Post Processing > Modify G-Code'. Unchecking the box will remove the script from the active list.</p>
                    <p><b>Important Considerations:</b></p>
                    <ul>
                        <li>This method directly alters the G-code. The compensation is "baked into" the G-code file.</li>
                        <li>If you use this method, ensure that any firmware-level skew compensation (like Marlin's M852 or Klipper's SET_SKEW) is <b>disabled</b> on your printer. Applying both software (Cura script) and firmware compensation simultaneously will likely result in over-correction or other undesirable effects. Choose one method only.</li>
                        <li>This is a good option if your printer's firmware does not support skew compensation commands, or if you prefer to manage all compensations at the slicer level.</li>
                    </ul>
                """)
            }
        }

        # --- Enable Section ---
        enable_layout = QHBoxLayout()
        self.enable_checkbox = QCheckBox(catalog.i18n(f"Enable Print Skew Compensation: {self.active_printer}"))
        self.enable_checkbox.setToolTip(catalog.i18n(f"Enable or disable the skew compensation features for the currently active printer {self.active_printer}."))
        self.enable_checkbox.setStyleSheet(PluginConstants.CHECKBOX_STYLE)
        enable_layout.addWidget(self.enable_checkbox)
        enable_layout.addStretch()
        main_layout.addLayout(enable_layout)
        
        # --- Add Calibration Models Group ---
        add_models_group = QGroupBox()
        add_models_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        add_models_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        add_models_main_layout = QVBoxLayout()
        # Title row
        add_models_title_layout = QHBoxLayout()
        add_models_title_label = QLabel(catalog.i18n("1. Print Calibration Model(s)"))
        add_models_title_label.setStyleSheet(PluginConstants.GROUP_TITLE_LABEL_STYLE)
        self.add_models_help_button = QPushButton("?")
        self.add_models_help_button.setFixedSize(15, 15)
        self.add_models_help_button.setToolTip(catalog.i18n("Help for Printing Calibration Models"))
        self.add_models_help_button.setStyleSheet(PluginConstants.HELP_BUTTON_STYLE)
        self.add_models_help_button.clicked.connect(lambda: self._show_help_dialog("calibration_models"))
        add_models_title_layout.addWidget(add_models_title_label)
        add_models_title_layout.addStretch()
        add_models_title_layout.addWidget(self.add_models_help_button)
        add_models_main_layout.addLayout(add_models_title_layout)
        add_models_label = QLabel(catalog.i18n("Add calibration model(s) to the build plate to print for measurement. Make sure they are oriented correctly."))
        add_models_label.setStyleSheet(f"color: {PluginConstants.TEXT_COLOR_LIGHT_GRAY};")
        add_models_main_layout.addWidget(add_models_label)

        add_buttons_layout = QHBoxLayout()
        add_buttons_layout.addStretch()
        self.add_xy_button = QPushButton(catalog.i18n("XY Plane"))
        self.add_xy_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE)
        self.add_xz_button = QPushButton(catalog.i18n("XZ Plane"))
        self.add_xz_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE)
        self.add_yz_button = QPushButton(catalog.i18n("YZ Plane"))
        self.add_yz_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE)
        self.add_all_button = QPushButton(catalog.i18n("All 3"))
        self.add_all_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE)
        
        self.add_xy_button.setToolTip(catalog.i18n("Add the XY plane calibration model to the build plate. (Model text facing up)."))
        self.add_xz_button.setToolTip(catalog.i18n("Add the XZ plane calibration model to the build plate. (Model text facing front)."))
        self.add_yz_button.setToolTip(catalog.i18n("Add the YZ plane calibration model to the build plate. (Model text facing right)."))
        self.add_all_button.setToolTip(catalog.i18n("Add all three calibration models to the build plate. (Orient the models properly)."))
        add_buttons_layout.addWidget(self.add_xy_button)
        add_buttons_layout.addWidget(self.add_xz_button)
        add_buttons_layout.addWidget(self.add_yz_button)
        add_buttons_layout.addWidget(self.add_all_button)
        add_buttons_layout.addStretch()
        add_models_main_layout.addLayout(add_buttons_layout)

        add_models_group.setLayout(add_models_main_layout)
        main_layout.addWidget(add_models_group)
        
        # --- Measurements Group ---
        measure_group = QGroupBox()
        measure_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        measure_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        measure_layout = QVBoxLayout()
        measure_title_layout = QHBoxLayout()
        measure_title_label = QLabel(catalog.i18n("2. Add the Measurements for the 'Skew Factor' calculations."))
        measure_title_label.setStyleSheet(PluginConstants.GROUP_TITLE_LABEL_STYLE)
        self.measure_help_button = QPushButton("?")
        self.measure_help_button.setFixedSize(15, 15)
        self.measure_help_button.setToolTip(catalog.i18n("Help for Entering Measurements"))
        self.measure_help_button.setStyleSheet(PluginConstants.HELP_BUTTON_STYLE)
        self.measure_help_button.clicked.connect(lambda: self._show_help_dialog("measurements"))
        measure_title_layout.addWidget(measure_title_label)
        measure_title_layout.addStretch()
        measure_title_layout.addWidget(self.measure_help_button)
        measure_layout.addLayout(measure_title_layout)
        measure_desc = QLabel(catalog.i18n(f"Enter the measurements from your printed calibration models here to calculate the necessary skew compensation factors."))
        measure_desc.setWordWrap(True)
        measure_desc.setStyleSheet(PluginConstants.DESCRIPTION_STYLE_MENU)
        self.measure_button = QPushButton(catalog.i18n("Enter Measurements and Calculate Skew Factors"))
        self.measure_button.setStyleSheet(PluginConstants.MEASURE_BUTTON_STYLE)
        self.measure_button.setToolTip(catalog.i18n("Open the dialog to enter calibration model measurements and calculate skew factors."))
        measure_layout.addWidget(measure_desc)

        measure_button_layout = QHBoxLayout()
        measure_button_layout.addStretch()
        measure_button_layout.addWidget(self.measure_button)
        measure_button_layout.addStretch()
        measure_layout.addLayout(measure_button_layout)

        measure_group.setLayout(measure_layout)
        main_layout.addWidget(measure_group)

        # --- Marlin G-code Group ---
        marlin_group = QGroupBox()
        marlin_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        marlin_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        marlin_layout = QVBoxLayout()
        marlin_title_layout = QHBoxLayout()
        marlin_title_label = QLabel(catalog.i18n("3a. Marlin Method (add an 'M852' line to the G-code file)"))
        marlin_title_label.setStyleSheet(PluginConstants.GROUP_TITLE_LABEL_STYLE)
        self.marlin_help_button = QPushButton("?")
        self.marlin_help_button.setFixedSize(15, 15)
        self.marlin_help_button.setToolTip(catalog.i18n("Help for Marlin Method"))
        self.marlin_help_button.setStyleSheet(PluginConstants.HELP_BUTTON_STYLE)
        self.marlin_help_button.clicked.connect(lambda: self._show_help_dialog("marlin_method"))
        marlin_title_layout.addWidget(marlin_title_label)
        marlin_title_layout.addStretch()
        marlin_title_layout.addWidget(self.marlin_help_button)
        marlin_layout.addLayout(marlin_title_layout)
        marlin_desc = QLabel(catalog.i18n("For Marlin firmware that supports M852. The plugin will add the G-code command line to the Machine Start G-code."))
        marlin_desc.setWordWrap(True)
        marlin_desc.setStyleSheet(PluginConstants.DESCRIPTION_STYLE_MENU)
        marlin_gcode_layout = QHBoxLayout()
        self.marlin_gcode_display = QTextEdit()
        self.marlin_gcode_display.setReadOnly(True)
        self.marlin_gcode_display.setToolTip(catalog.i18n("Calculated M852 G-code. Select and copy (Ctrl+C) if needed."))
        self.marlin_gcode_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.marlin_gcode_display.setFixedHeight(30)
        self.marlin_gcode_display.setStyleSheet(PluginConstants.INPUT_TEXT_STYLE)
        self.add_marlin_gcode_checkbox = QCheckBox(catalog.i18n("Marlin - Insert M852 into the G-code file"))
        self.add_marlin_gcode_checkbox.setToolTip(catalog.i18n("Insert the M852 command into the G-code file at the end of your StartUp section."))
        self.add_marlin_gcode_checkbox.setStyleSheet(PluginConstants.CHECKBOX_STYLE)
        marlin_gcode_layout.addWidget(self.marlin_gcode_display)
        marlin_layout.addWidget(marlin_desc)
        marlin_layout.addLayout(marlin_gcode_layout)
        marlin_layout.addWidget(self.add_marlin_gcode_checkbox)
        marlin_group.setLayout(marlin_layout)
        main_layout.addWidget(marlin_group)

        # --- Klipper G-code Group ---
        klipper_group = QGroupBox()
        klipper_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        klipper_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        klipper_layout = QVBoxLayout()
        klipper_title_layout = QHBoxLayout()
        klipper_title_label = QLabel(catalog.i18n("3b. Klipper Method (add a 'SET_SKEW' line to the G-code)"))
        klipper_title_label.setStyleSheet(PluginConstants.GROUP_TITLE_LABEL_STYLE)
        self.klipper_help_button = QPushButton("?")
        self.klipper_help_button.setFixedSize(15, 15)
        self.klipper_help_button.setToolTip(catalog.i18n("Help for Klipper Method"))
        self.klipper_help_button.setStyleSheet(PluginConstants.HELP_BUTTON_STYLE)
        self.klipper_help_button.clicked.connect(lambda: self._show_help_dialog("klipper_method"))
        klipper_title_layout.addWidget(klipper_title_label)
        klipper_title_layout.addStretch()
        klipper_title_layout.addWidget(self.klipper_help_button)
        klipper_layout.addLayout(klipper_title_layout)
        klipper_desc = QLabel(catalog.i18n("For Klipper firmware that supports SET_SKEW.  The plugin will add the G-code command line to the Machine Start G-code."))
        klipper_desc.setWordWrap(True)
        klipper_desc.setStyleSheet(PluginConstants.DESCRIPTION_STYLE_MENU)
        klipper_gcode_layout = QHBoxLayout()
        self.klipper_gcode_display = QTextEdit()
        self.klipper_gcode_display.setReadOnly(True)
        self.klipper_gcode_display.setToolTip(catalog.i18n("Calculated SET_SKEW G-code. Select and copy (Ctrl+C) if needed."))
        self.klipper_gcode_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.klipper_gcode_display.setFixedHeight(30)
        self.klipper_gcode_display.setStyleSheet(PluginConstants.INPUT_TEXT_STYLE)
        self.add_klipper_gcode_checkbox = QCheckBox(catalog.i18n("Klipper - Insert SET_SKEW into the G-code file"))
        self.add_klipper_gcode_checkbox.setToolTip(catalog.i18n("Insert the SET_SKEW command into the G-code file after your StartUp Gcode."))
        self.add_klipper_gcode_checkbox.setStyleSheet(PluginConstants.CHECKBOX_STYLE)
        klipper_gcode_layout.addWidget(self.klipper_gcode_display)
        klipper_layout.addWidget(klipper_desc)
        klipper_layout.addLayout(klipper_gcode_layout)
        klipper_layout.addWidget(self.add_klipper_gcode_checkbox)
        klipper_group.setLayout(klipper_layout)
        main_layout.addWidget(klipper_group)

        # --- Post-Processing Script Group ---
        pp_script_group = QGroupBox()  # Title removed
        pp_script_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE)
        pp_script_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        pp_script_group_layout = QVBoxLayout()
        pp_title_layout = QHBoxLayout()
        pp_title_label = QLabel(catalog.i18n("3c. Cura Method (post-process the G-code)"))
        pp_title_label.setStyleSheet(PluginConstants.GROUP_TITLE_LABEL_STYLE)
        self.pp_help_button = QPushButton("?")
        self.pp_help_button.setFixedSize(15, 15)
        self.pp_help_button.setToolTip(catalog.i18n("Help for Cura Post-Processing Method"))
        self.pp_help_button.setStyleSheet(PluginConstants.HELP_BUTTON_STYLE)
        self.pp_help_button.clicked.connect(lambda: self._show_help_dialog("cura_method"))
        pp_title_layout.addWidget(pp_title_label)
        pp_title_layout.addStretch()
        pp_title_layout.addWidget(self.pp_help_button)
        pp_script_group_layout.addLayout(pp_title_layout)
        pp_script_desc = QLabel(catalog.i18n("Enable this to load and use the post-processing script 'PrintSkewCompensationCKM'. The G-Code file will be 'counter-skewed'."))
        pp_script_desc.setWordWrap(True)
        pp_script_desc.setStyleSheet(PluginConstants.DESCRIPTION_STYLE_MENU)
        self.pp_script_active_checkbox = QCheckBox(catalog.i18n("Cura - Post-Process the G-Code file to counteract the Skew"))
        self.pp_script_active_checkbox.setToolTip(catalog.i18n("Adds/Removes 'PrintSkewCompensationCKM.py' from the list in 'Extensions > Post Processing > Modify G-Code'."))
        self.pp_script_active_checkbox.setStyleSheet(PluginConstants.CHECKBOX_STYLE)
        pp_script_group_layout.addWidget(pp_script_desc)
        pp_script_group_layout.addWidget(self.pp_script_active_checkbox)
        pp_script_group.setLayout(pp_script_group_layout)
        main_layout.addWidget(pp_script_group)

        # --- Connections ---
        self.enable_checkbox.toggled.connect(self.enable_compensation_toggled)
        self.measure_button.clicked.connect(self.enter_measurements_requested)
        self.add_xy_button.clicked.connect(lambda: self.add_model_requested.emit("xy"))
        self.add_xz_button.clicked.connect(lambda: self.add_model_requested.emit("xz"))
        self.add_yz_button.clicked.connect(lambda: self.add_model_requested.emit("yz"))
        self.add_all_button.clicked.connect(lambda: self.add_model_requested.emit("all"))
        self.add_marlin_gcode_checkbox.toggled.connect(self._on_marlin_toggled)
        self.add_klipper_gcode_checkbox.toggled.connect(self._on_klipper_toggled)
        self.pp_script_active_checkbox.toggled.connect(self._on_pp_script_toggled)

    def _on_marlin_toggled(self, checked: bool):
        if checked:
            # Block signals to prevent recursion/loops when unchecking others
            self.add_klipper_gcode_checkbox.blockSignals(True)
            self.pp_script_active_checkbox.blockSignals(True)

            self.add_klipper_gcode_checkbox.setChecked(False)
            self.pp_script_active_checkbox.setChecked(False)

            self.add_klipper_gcode_checkbox.blockSignals(False)
            self.pp_script_active_checkbox.blockSignals(False)
        self.add_marlin_gcode_toggled.emit(checked)

    def _on_klipper_toggled(self, checked: bool):
        if checked:
            self.add_marlin_gcode_checkbox.blockSignals(True)
            self.pp_script_active_checkbox.blockSignals(True)

            self.add_marlin_gcode_checkbox.setChecked(False)
            self.pp_script_active_checkbox.setChecked(False)

            self.add_marlin_gcode_checkbox.blockSignals(False)
            self.pp_script_active_checkbox.blockSignals(False)
        self.add_klipper_gcode_toggled.emit(checked)

    def _on_pp_script_toggled(self, checked: bool):
        if checked:
            self.add_marlin_gcode_checkbox.blockSignals(True)
            self.add_klipper_gcode_checkbox.blockSignals(True)

            self.add_marlin_gcode_checkbox.setChecked(False)
            self.add_klipper_gcode_checkbox.setChecked(False)

            self.add_marlin_gcode_checkbox.blockSignals(False)
            self.add_klipper_gcode_checkbox.blockSignals(False)
        self.toggle_post_processing_script_requested.emit(checked)

    def _get_resource_path(self, filename):
        """Helper to get the absolute path to a resource file."""
        try:
            # Use Application to find the plugin directory
            plugin_path = Application.getInstance().getPluginRegistry().getPluginPath(PluginConstants.PLUGIN_ID)
            if plugin_path:
                return os.path.join(plugin_path, "resources", filename)
        except Exception as e:
            Logger.log("w", f"Could not determine resource path for {filename}: {e}")
        # Fallback or default path if needed
        return filename # Or potentially raise an error

    def update_display(
        self,
        marlin_gcode: str,
        klipper_gcode: str,
        is_enabled: bool,
        is_pp_script_active: bool,
        marlin_method_active: bool,
        klipper_method_active: bool
    ) -> None:
        """
        Updates the dialog's display based on the current plugin state.

        Args:
            marlin_gcode (str): The Marlin G-code command string.
            klipper_gcode (str): The Klipper G-code command string.
            is_enabled (bool): True if skew compensation is globally enabled, False otherwise.
            is_pp_script_active (bool): True if the Cura Post-Processing script is currently active for compensation.
            marlin_method_active (bool): True if the Marlin G-code method is selected AND compensation is enabled.
            klipper_method_active (bool): True if the Klipper G-code method is selected AND compensation is enabled.
        """
        # Update active printer name if it has changed
        current_active_printer = Application.getInstance().getGlobalContainerStack().getName()
        if self.active_printer != current_active_printer:
            self.active_printer = current_active_printer
            self.enable_checkbox.setText(catalog.i18n(f"Enable Print Skew Compensation: {self.active_printer}"))

        # Block signals temporarily to prevent feedback loops when setting state
        self.enable_checkbox.blockSignals(True)
        self.enable_checkbox.setChecked(is_enabled)
        self.enable_checkbox.blockSignals(False)

        self.pp_script_active_checkbox.blockSignals(True)
        self.pp_script_active_checkbox.setChecked(is_pp_script_active)
        self.pp_script_active_checkbox.blockSignals(False)

        self.add_marlin_gcode_checkbox.blockSignals(True)
        self.add_marlin_gcode_checkbox.setChecked(marlin_method_active)
        self.add_marlin_gcode_checkbox.blockSignals(False)

        self.add_klipper_gcode_checkbox.blockSignals(True)
        self.add_klipper_gcode_checkbox.setChecked(klipper_method_active)
        self.add_klipper_gcode_checkbox.blockSignals(False)

        self.marlin_gcode_display.setText(marlin_gcode if marlin_gcode else "")
        self.klipper_gcode_display.setText(klipper_gcode if klipper_gcode else "")

    # Add this new method to update the checkbox state
    def update_post_processing_script_state(self, is_active: bool):
        """Sets the state of the post-processing script checkbox."""
        self.pp_script_active_checkbox.blockSignals(True)
        self.pp_script_active_checkbox.setChecked(is_active)
        self.pp_script_active_checkbox.blockSignals(False)

    def _show_help_dialog(self, topic_key: str) -> None:
        """
        Shows the help dialog for the given topic.
        """
        # Ensure the measurements help content is up-to-date with the current printer name
        current_active_printer = Application.getInstance().getGlobalContainerStack().getName()
        if self.active_printer != current_active_printer:
            self.active_printer = current_active_printer
            self.help_content["measurements"]["content"] = catalog.i18n("""
                <h2>2. Entering Measurements and Calculating Skew Factors</h2>
                <p>After printing the calibration model(s), you need to measure them carefully using a precise instrument like digital calipers.  Take a look at the surfaces that will be measured and insure there are no 'pips' sticking up.  You want to measure 'across the flats'.</p>
                <p>The 'Enter Measurements and Calculate Skew Factors' button opens a separate dialog. In this dialog, you will input the dimensions you measured from your printed calibration models. The plugin compares these measurements to the ideal dimensions of the models to calculate the 'skew factors' needed for compensation.</p>
                <p><b>Machine Specific:</b> It is very important to understand that these measurements and the resulting skew factors are specific to the currently active printer profile in Cura, which is <b>'{printer_name}'</b>. If you have multiple 3D printers, or even different nozzle/material setups on the same printer that might affect dimensional accuracy, you must repeat the entire 'Print Calibration Model(s) -> Measure -> Enter Measurements' process for each distinct printer configuration for which you want to apply skew compensation.</p>
                <p><b>Accuracy:</b> The accuracy of your skew compensation depends directly on the accuracy of your measurements. Take multiple readings if possible and ensure your measuring tool is calibrated.</p>
            """).format(printer_name=self.active_printer)
        dialog = HelpDialog(self.help_content, initial_topic_key=topic_key, parent=self)
        dialog.exec()

