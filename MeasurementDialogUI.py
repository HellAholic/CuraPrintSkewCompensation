import os
from UM.Message import Message
from UM.Logger import Logger
from UM.i18n import i18nCatalog

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QGroupBox, QFormLayout,
                             QDialogButtonBox, QSizePolicy)

from .SkewCalculator import SkewCalculator
from .PluginConstants import PluginConstants # Import PluginConstants

catalog = i18nCatalog("cura")

# Helper functions to access preferences are now removed as per the new approach.

class MeasurementDialogUI(QDialog):
    """
    A dialog for users to input measured distances from a calibration print.

    This dialog is used to collect the four key measurements (A, B, C, D)
    required to calculate print skew. It provides input fields for these
    measurements and buttons to submit or cancel.
    """
    # Signal emitted when calculation is done and values are saved
    calculation_done = pyqtSignal()

    def __init__(self, parent=None, controller=None) -> None:
        """
        Initializes the MeasurementDialogUI.
        Args:
            parent: The parent widget, if any.
            controller: The plugin controller instance.
        """
        super().__init__(parent)
        self._controller = controller # Assign controller instance
        self.setWindowTitle(catalog.i18n("Enter Measurements & Calculate Skew"))
        self.setMinimumWidth(PluginConstants.MINIMUM_DIALOG_WIDTH)
        self.setMinimumHeight(PluginConstants.MINIMUM_DIALOG_HEIGHT)
        self.setStyleSheet(PluginConstants.DIALOG_BACKGROUND_STYLE) # Use constant

        self._calculator = SkewCalculator() # Local calculator for UI display/preview

        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout() # Main content area: planes on left, results on right

        # --- Measurement Inputs & Images Side (Left) ---
        planes_v_layout = QVBoxLayout()

        # Validator for input fields
        float_validator = QDoubleValidator(0.0, 10000.0, 3)
        float_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        # Create QLineEdit widgets (will be assigned to self later for access)
        self.xy_ac_input = QLineEdit()
        self.xy_bd_input = QLineEdit()
        self.xy_ad_input = QLineEdit()
        self.xz_ac_input = QLineEdit()
        self.xz_bd_input = QLineEdit()
        self.xz_ad_input = QLineEdit()
        self.yz_ac_input = QLineEdit()
        self.yz_bd_input = QLineEdit()
        self.yz_ad_input = QLineEdit()

        self.measurement_inputs = {
            "xy_ac": (self.xy_ac_input, "xy_ac_measurement", 141.42),
            "xy_bd": (self.xy_bd_input, "xy_bd_measurement", 141.42),
            "xy_ad": (self.xy_ad_input, "xy_ad_measurement", 100.0),
            "xz_ac": (self.xz_ac_input, "xz_ac_measurement", 141.42),
            "xz_bd": (self.xz_bd_input, "xz_bd_measurement", 141.42),
            "xz_ad": (self.xz_ad_input, "xz_ad_measurement", 100.0),
            "yz_ac": (self.yz_ac_input, "yz_ac_measurement", 141.42),
            "yz_bd": (self.yz_bd_input, "yz_bd_measurement", 141.42),
            "yz_ad": (self.yz_ad_input, "yz_ad_measurement", 100.0),
        }
        for key, (input_widget, _pref_key_ignored, default_val) in self.measurement_inputs.items():
            input_widget.setValidator(float_validator)
            initial_value = default_val # Default fallback
            if self._controller and hasattr(self._controller, '_skew_calculator'):
                # 'key' from measurement_inputs (e.g., "xy_ac") matches the attribute names on SkewCalculator
                initial_value = getattr(self._controller._skew_calculator, key, default_val)
            else:
                Logger.log("w", f"MeasurementDialogUI: Controller or _skew_calculator not available for initial value of {key}, using default.")
            try:
                input_widget.setText(f"{float(initial_value):.3f}")
            except (ValueError, TypeError):
                input_widget.setText(f"{default_val:.3f}") # Fallback if conversion fails
            input_widget.setToolTip(catalog.i18n(f"Measured distance for {key.upper().replace('_', ' ')}"))
            input_widget.setStyleSheet(PluginConstants.INPUT_TEXT_STYLE) # Use constant

        # --- XY Plane Group ---
        xy_plane_group = QGroupBox(catalog.i18n("XY Plane Measurements"))
        xy_plane_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE_MEASUREMENT)
        xy_plane_group.setFixedWidth(400)
        xy_plane_layout = QHBoxLayout(xy_plane_group)
        xy_input_form_layout = QFormLayout()
        xy_input_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        xy_input_form_layout.addRow(QLabel(catalog.i18n("AC Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xy_ac_input) # Use constant
        xy_input_form_layout.addRow(QLabel(catalog.i18n("BD Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xy_bd_input) # Use constant
        xy_input_form_layout.addRow(QLabel(catalog.i18n("AD Side:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xy_ad_input) # Use constant
        xy_plane_layout.addLayout(xy_input_form_layout, 1) # Inputs take stretch factor 1

        image_label_xy = QLabel()
        self._load_image(image_label_xy, "XYpic.png", "XY Plane Diagram", (160, 240))
        xy_plane_layout.addWidget(image_label_xy, 1) # Image takes stretch factor 1
        planes_v_layout.addWidget(xy_plane_group)

        # --- XZ Plane Group ---
        xz_plane_group = QGroupBox(catalog.i18n("XZ Plane Measurements"))
        xz_plane_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE_MEASUREMENT)
        xz_plane_group.setFixedWidth(400)
        xz_plane_layout = QHBoxLayout(xz_plane_group)
        xz_input_form_layout = QFormLayout()
        xz_input_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        xz_input_form_layout.addRow(QLabel(catalog.i18n("AC Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xz_ac_input) # Use constant
        xz_input_form_layout.addRow(QLabel(catalog.i18n("BD Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xz_bd_input) # Use constant
        xz_input_form_layout.addRow(QLabel(catalog.i18n("AD Side:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xz_ad_input) # Use constant
        xz_plane_layout.addLayout(xz_input_form_layout, 1)

        image_label_xz = QLabel()
        self._load_image(image_label_xz, "XZpic.png", "XZ Plane Diagram", (160, 240))
        xz_plane_layout.addWidget(image_label_xz, 1)
        planes_v_layout.addWidget(xz_plane_group)

        # --- YZ Plane Group ---
        yz_plane_group = QGroupBox(catalog.i18n("YZ Plane Measurements"))
        yz_plane_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE_MEASUREMENT)
        yz_plane_group.setFixedWidth(400)
        yz_plane_layout = QHBoxLayout(yz_plane_group)
        yz_input_form_layout = QFormLayout()
        yz_input_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        yz_input_form_layout.addRow(QLabel(catalog.i18n("AC Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.yz_ac_input) # Use constant
        yz_input_form_layout.addRow(QLabel(catalog.i18n("BD Diagonal:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.yz_bd_input) # Use constant
        yz_input_form_layout.addRow(QLabel(catalog.i18n("AD Side:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.yz_ad_input) # Use constant
        yz_plane_layout.addLayout(yz_input_form_layout, 1)

        image_label_yz = QLabel()
        self._load_image(image_label_yz, "YZpic.png", "YZ Plane Diagram", (160, 240))
        yz_plane_layout.addWidget(image_label_yz, 1)
        planes_v_layout.addWidget(yz_plane_group)

        planes_v_layout.addStretch() # Add stretch at the bottom of the planes column
        content_layout.addLayout(planes_v_layout, 2) # Planes layout takes stretch factor 2

        # --- Right Column: Calculated Results ---
        results_group = QGroupBox(catalog.i18n("Calculated Skew Factors & G-Code"))
        results_group.setStyleSheet(PluginConstants.GROUPBOX_STYLE_MEASUREMENT)
        results_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        results_form_layout = QFormLayout()
        results_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.xy_skew_factor_label = QLabel("N/A")
        self.xz_skew_factor_label = QLabel("N/A")
        self.yz_skew_factor_label = QLabel("N/A")
        self.marlin_gcode_label = QLabel("N/A")
        self.klipper_gcode_label = QLabel("N/A")

        # Make labels selectable for copying and enable word wrap
        for label in [self.xy_skew_factor_label, self.xz_skew_factor_label, self.yz_skew_factor_label,
                      self.marlin_gcode_label, self.klipper_gcode_label]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            label.setStyleSheet(PluginConstants.RESULT_LABEL_STYLE_FORM) # Use constant

        results_form_layout.addRow(QLabel(catalog.i18n("XY Skew Factor:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xy_skew_factor_label) # Use constant
        results_form_layout.addRow(QLabel(catalog.i18n("XZ Skew Factor:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.xz_skew_factor_label) # Use constant
        results_form_layout.addRow(QLabel(catalog.i18n("YZ Skew Factor:"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.yz_skew_factor_label) # Use constant
        results_form_layout.addRow(QLabel("")) # Spacer
        results_form_layout.addRow(QLabel(catalog.i18n("Marlin (M852):"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.marlin_gcode_label) # Use constant
        results_form_layout.addRow(QLabel("")) # Spacer
        results_form_layout.addRow(QLabel(catalog.i18n("Klipper (SET_SKEW):"), styleSheet=PluginConstants.LABEL_STYLE_FORM), self.klipper_gcode_label) # Use constant

        results_group.setLayout(results_form_layout)
        content_layout.addWidget(results_group, 1, Qt.AlignmentFlag.AlignTop)

        # --- Add content layout to main layout ---
        main_layout.addLayout(content_layout, 1) # Give content_layout vertical stretch

        # --- Bottom Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        # Style the standard OK and Cancel buttons
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE) # Use constant
            ok_button.setText(catalog.i18n("Apply and Close"))
            ok_button.setToolTip(catalog.i18n("Apply calculations, save measurements, and close the dialog."))


        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setStyleSheet(PluginConstants.CLOSE_BUTTON_STYLE) # Use constant

        # Rename button for clarity
        calculate_button = QPushButton(catalog.i18n("Calculate & Preview"))
        calculate_button.setStyleSheet(PluginConstants.SELECT_BUTTON_STYLE) # Use constant
        calculate_button.setToolTip(catalog.i18n("Calculate skew factors and G-code based on the entered measurements."))
        calculate_button.clicked.connect(self._calculate_and_update_display)
        button_box.addButton(calculate_button, QDialogButtonBox.ButtonRole.ActionRole)

        main_layout.addWidget(button_box) # Add button box to main layout

        # Initial calculation and display update
        self._calculate_and_update_display()

    def _load_image(self, label: QLabel, image_name: str, description: str, dimensions: tuple[int, int]):
        """Helper function to load and set an image on a QLabel."""
        try:
            # Construct path to image within the plugin's "images" directory
            image_path = os.path.join(PluginConstants.PLUGIN_PATH, "images", image_name)
            
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    label.setPixmap(pixmap.scaled(dimensions[0], dimensions[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setToolTip(catalog.i18n(description))
                else:
                    Logger.log("w", f"Failed to load pixmap for {description} from: {image_path}")
                    label.setText(catalog.i18n(f"{description} load error"))
            else: # Should be caught by the first check, but as a safeguard
                Logger.log("w", f"{description} image definitely not found at: {image_path}")
                label.setText(catalog.i18n(f"{description} not found"))
        except Exception as e:
            Logger.logException("e", f"Error loading {description} image: {e}")
            label.setText(catalog.i18n(f"{description} load error"))

    def _get_input_values(self) -> dict[str, float] | None:
        """Reads and validates input values, returning a dict or None if invalid."""
        values = {}
        try:
            for key, (input_widget, _, _) in self.measurement_inputs.items():
                text = input_widget.text().strip()
                if not text:
                    raise ValueError(f"Input for {key.upper()} cannot be empty.")
                value = float(text)
                if key.endswith("_ad") and value <= 0:
                     raise ValueError(f"Side measurement ({key.upper()}) must be positive.")
                values[key] = value
            return values
        except ValueError as e:
            Message(text=f"Invalid Input: {e}.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.ERROR).show()
            return None

    def _on_accept(self):
        """Calculate, update controller's values, emit signal, and close."""
        if self._calculate_and_update_display(): # Calculate one last time and check validity (uses local _calculator)
            values = self._get_input_values() # Get values from UI fields
            if values:
                if self._controller and hasattr(self._controller, '_skew_calculator'):
                    # Update the controller's SkewCalculator instance with the new values
                    self._controller._skew_calculator.set_measurements(**values)
                else:
                    Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Controller or _skew_calculator not available in _on_accept. Cannot update controller's calculator.")
                
                self.calculation_done.emit() # Signal the controller to save and perform other actions
                super().accept()
            else:
                # Should not happen if _calculate_and_update_display passed, but good practice
                Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Could not save values via controller due to invalid input on accept.")
        else:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: MeasurementDialog accept prevented due to invalid input.")

    def _calculate_and_update_display(self) -> bool:
        """Calculates skew factors and updates the display labels. Returns True if successful."""
        values = self._get_input_values()
        if values is None:
            # Clear results if input is invalid
            error_html = f"<font color='{PluginConstants.ERROR_TEXT_COLOR_LIGHT_RED}'>Invalid Input</font>" # Use constant
            self.xy_skew_factor_label.setText(error_html)
            self.xz_skew_factor_label.setText(error_html)
            self.yz_skew_factor_label.setText(error_html)
            self.marlin_gcode_label.setText(error_html)
            self.klipper_gcode_label.setText(error_html)
            return False

        try:
            self._calculator.set_measurements(
                xy_ac=values["xy_ac"], xy_bd=values["xy_bd"], xy_ad=values["xy_ad"],
                xz_ac=values["xz_ac"], xz_bd=values["xz_bd"], xz_ad=values["xz_ad"],
                yz_ac=values["yz_ac"], yz_bd=values["yz_bd"], yz_ad=values["yz_ad"]
            )
            # Get calculated values
            factors = self._calculator.get_skew_factors()
            marlin_cmd = self._calculator.get_marlin_command()
            klipper_cmd = self._calculator.get_klipper_command()

            # Update labels
            self.xy_skew_factor_label.setText(f"{factors[0]:.8f}")
            self.xz_skew_factor_label.setText(f"{factors[1]:.8f}")
            self.yz_skew_factor_label.setText(f"{factors[2]:.8f}")
            self.marlin_gcode_label.setText(marlin_cmd)
            self.klipper_gcode_label.setText(klipper_cmd)
            return True

        except Exception as e:
            Logger.logException("e", f"Error during calculation or display update: {e}")
            Message(text=f"Calculation Error. An unexpected error occurred: {e}.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.ERROR).show()
            # Clear results on error
            error_html = f"<font color='{PluginConstants.ERROR_TEXT_COLOR_LIGHT_RED}'>Error</font>" # Use constant
            self.xy_skew_factor_label.setText(error_html)
            self.xz_skew_factor_label.setText(error_html)
            self.yz_skew_factor_label.setText(error_html)
            self.marlin_gcode_label.setText(error_html)
            self.klipper_gcode_label.setText(error_html)
            return False

    def reject(self):
        """Reimplement reject to add logging."""
        Message(text=catalog.i18n("Changes were not saved."),
                lifetime=5,
                title=catalog.i18n("[Print Skew Compensation]"),
                message_type=Message.MessageType.NEUTRAL).show()
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: MeasurementDialog rejected (Cancel clicked or closed).")
        super().reject()
