import os
import configparser
import hashlib
import re
from UM.Application import Application
from UM.Logger import Logger
from UM.i18n import i18nCatalog
from UM.Message import Message
from UM.Extension import Extension

from PyQt6.QtCore import QUrl

from .MeasurementDialogUI import MeasurementDialogUI
from .SkewCalculator import SkewCalculator
from .GCodeManager import GCodeManager
from .PluginConstants import PluginConstants

catalog = i18nCatalog("cura")

class PluginController(Extension):
    """
    Main controller for the Print Skew Compensation plugin.

    Handles plugin initialization, menu interactions, settings management,
    and communication between different plugin components like the UI dialogs
    and the G-code manager.
    """
    def __init__(self) -> None:
        """Initializes the PluginController."""
        super().__init__()
        self._application = Application.getInstance()
        self._preferences = self._application.getPreferences()
        self._skew_calculator = SkewCalculator()
        self._gcode_manager = GCodeManager(self._application, Logger)
        self._measurement_dialog_instance = None
        self._plugin_menu_dialog_instance = None
        self._actions = {}
        self.pp_script_checkbox_state = False

        self._global_container_stack = None
        self._connect_to_global_stack_metadata()
        Application.getInstance().globalContainerStackChanged.connect(self._handle_global_container_stack_changed)

        self.setMenuName(catalog.i18n("Print Skew Compensation"))

        self._update_internal_state_from_printer_config()

        action_open_menu = self.addMenuItem(catalog.i18n("Calibrate Skew..."), self._show_plugin_menu_dialog)
        if not action_open_menu:
            Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Failed to create 'Open Plugin Menu' menu item action.")

        if self._preferences:
            self._preferences.preferenceChanged.connect(self._on_preference_changed)
        else:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Could not get preferences instance to connect signal.")

        PluginConstants.get_operating_system()
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: PluginController Initialized for {PluginConstants.CURRENT_OS} OS.")

    # Handlers for reading/writing printer settings

    def _write_printer_settings_to_file(self, printer_name, settings) -> None:
        """Writes printer settings to the plugin's configuration file for the given printer name."""
        cfg_path = self._get_printer_cfg_path(printer_name)
        config = configparser.ConfigParser()
        config['settings'] = {k: str(v).replace('%','%%') for k, v in settings.items()}
        config['settings']['printer_name'] = str(printer_name).replace('%','%%')  # Store printer name for reference
        # Check if the directory exists, create it if not (safeguard)
        if not os.path.exists(cfg_path):
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        
        try:
            with open(cfg_path, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Error writing printer settings to file {cfg_path}: {e}")
            Message(text=catalog.i18n("An error occurred while saving printer settings."), title=catalog.i18n("[Print Skew Compensation]")).show()
            return

    def _read_printer_settings_from_file(self, printer_name) -> dict:
        """Reads printer settings from the plugin's configuration file for the given printer name."""
        cfg_path = self._get_printer_cfg_path(printer_name)
        if not os.path.exists(cfg_path):
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Printer settings file does not exist: {cfg_path}. Using default settings.")
            return self._get_default_settings()

        config = configparser.ConfigParser()
        config.read(cfg_path)

        if 'settings' not in config:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: No 'settings' section found in {cfg_path}. Using default settings.")
            return self._get_default_settings()

        settings = {k: v for k, v in config['settings'].items()}
        return settings

    def _get_default_settings(self) -> dict:
        return {
            "compensation_enabled": False,
            "compensation_method": "none",
            "marlin_add_to_gcode": False,
            "klipper_add_to_gcode": False,
            "xy_ac_measurement": 141.42,
            "xy_bd_measurement": 141.42,
            "xy_ad_measurement": 100.0,
            "xz_ac_measurement": 141.42,
            "xz_bd_measurement": 141.42,
            "xz_ad_measurement": 100.0,
            "yz_ac_measurement": 141.42,
            "yz_bd_measurement": 141.42,
            "yz_ad_measurement": 100.0,
            "pp_script_checkbox_state": False
        }
    
    def _get_printer_cfg_path(self, printer_name) -> str:
        """Returns the path to the plugin's printer configuration file path based on the printer name."""
        if not printer_name:
            Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Printer name is empty, cannot determine config path.")
            return None
        printer_file_name = self._sanitized_settings_file_name(printer_name)
        cfg_path = os.path.join(PluginConstants.PLUGIN_CONFIGURATION_PATH, printer_file_name)
        return cfg_path
    
    def _sanitized_settings_file_name(self, printer_name) -> str:
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', printer_name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        hash_part = hashlib.sha256(printer_name.encode('utf-8')).hexdigest()[:8]
        return f"{safe_name}_{hash_part}.cfg"

    def _get_current_printer_name(self) -> str:
        """Returns the name of the currently active printer."""
        stack = self._application.getGlobalContainerStack()
        if stack:
            return stack.getName()
        return None

    def _update_internal_state_from_printer_config(self):
        printer_name = self._get_current_printer_name()
        default_settings = self._get_default_settings()

        if not printer_name:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: No printer selected, using default settings.")
            current_settings_source = default_settings # Use defaults directly, types are correct
        else:
            current_settings_source = self._read_printer_settings_from_file(printer_name)

        # Helper to get a value and convert if it's a string, falling back to default typed value
        def get_typed_value(key_name, default_typed_value_from_schema):
            value_from_source = current_settings_source.get(key_name, default_typed_value_from_schema)
            target_type = type(default_typed_value_from_schema)

            if isinstance(value_from_source, str):
                try:
                    if target_type is bool:
                        return value_from_source.lower() == 'true'
                    elif target_type is float:
                        return float(value_from_source)
                    elif target_type is str:
                        return value_from_source
                    else: # Fallback for unexpected types, try direct conversion
                        return target_type(value_from_source)
                except ValueError:
                    Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Invalid value '{value_from_source}' for '{key_name}'. Using default: {default_typed_value_from_schema}")
                    return default_typed_value_from_schema
            elif isinstance(value_from_source, target_type):
                return value_from_source
            else:
                try:
                    Logger.log("d", f"{PluginConstants.PLUGIN_ID}: Value for '{key_name}' is of type {type(value_from_source)}, attempting cast to {target_type}.")
                    return target_type(value_from_source)
                except Exception as e:
                    Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Could not convert value '{value_from_source}' for '{key_name}' to {target_type}. Error: {e}. Using default: {default_typed_value_from_schema}")
                    return default_typed_value_from_schema

        self.enabled = get_typed_value("compensation_enabled", default_settings["compensation_enabled"])
        self.method = get_typed_value("compensation_method", default_settings["compensation_method"])
        self.marlin_add_to_gcode = get_typed_value("marlin_add_to_gcode", default_settings["marlin_add_to_gcode"])
        self.klipper_add_to_gcode = get_typed_value("klipper_add_to_gcode", default_settings["klipper_add_to_gcode"])
        self.pp_script_checkbox_state = get_typed_value("pp_script_checkbox_state", default_settings["pp_script_checkbox_state"])

        xy_ac = get_typed_value("xy_ac_measurement", default_settings["xy_ac_measurement"])
        xy_bd = get_typed_value("xy_bd_measurement", default_settings["xy_bd_measurement"])
        xy_ad = get_typed_value("xy_ad_measurement", default_settings["xy_ad_measurement"])
        xz_ac = get_typed_value("xz_ac_measurement", default_settings["xz_ac_measurement"])
        xz_bd = get_typed_value("xz_bd_measurement", default_settings["xz_bd_measurement"])
        xz_ad = get_typed_value("xz_ad_measurement", default_settings["xz_ad_measurement"])
        yz_ac = get_typed_value("yz_ac_measurement", default_settings["yz_ac_measurement"])
        yz_bd = get_typed_value("yz_bd_measurement", default_settings["yz_bd_measurement"])
        yz_ad = get_typed_value("yz_ad_measurement", default_settings["yz_ad_measurement"])

        self._skew_calculator.set_measurements(
            xy_ac=xy_ac,
            xy_bd=xy_bd,
            xy_ad=xy_ad,
            xz_ac=xz_ac,
            xz_bd=xz_bd,
            xz_ad=xz_ad,
            yz_ac=yz_ac,
            yz_bd=yz_bd,
            yz_ad=yz_ad
        )
        self._update_plugin_menu_dialog_state()

    def _save_current_settings(self):
        self._update_plugin_menu_dialog_state()
        printer_name = self._get_current_printer_name()
        if not printer_name:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: No printer selected, cannot save settings.")
            return
        settings = {
            "compensation_enabled": self.enabled,
            "compensation_method": self.method,
            "marlin_add_to_gcode": self.marlin_add_to_gcode,
            "klipper_add_to_gcode": self.klipper_add_to_gcode,
            "xy_ac_measurement": self._skew_calculator.xy_ac,
            "xy_bd_measurement": self._skew_calculator.xy_bd,
            "xy_ad_measurement": self._skew_calculator.xy_ad,
            "xz_ac_measurement": self._skew_calculator.xz_ac,
            "xz_bd_measurement": self._skew_calculator.xz_bd,
            "xz_ad_measurement": self._skew_calculator.xz_ad,
            "yz_ac_measurement": self._skew_calculator.yz_ac,
            "yz_bd_measurement": self._skew_calculator.yz_bd,
            "yz_ad_measurement": self._skew_calculator.yz_ad,
            "pp_script_checkbox_state": self.pp_script_checkbox_state
        }
        self._write_printer_settings_to_file(printer_name, settings)
    
    # End of handlers for reading/writing printer settings

    def _connect_to_global_stack_metadata(self):
        """Connects (or reconnects) to the global container stack's metaDataChanged signal."""
        new_stack = Application.getInstance().getGlobalContainerStack()

        if self._global_container_stack and self._global_container_stack != new_stack:
            try:
                self._global_container_stack.metaDataChanged.disconnect(self._on_global_metadata_changed)
            except TypeError:
                Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Error disconnecting from old global_container_stack.metaDataChanged; was it connected?")
            except Exception as e:
                Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Unexpected error disconnecting from old global_container_stack: {e}")


        self._global_container_stack = new_stack

        if self._global_container_stack:
            try:
                self._global_container_stack.metaDataChanged.connect(self._on_global_metadata_changed)
                Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Connected listener to global_container_stack.metaDataChanged.")
                # Trigger a check to sync state immediately after connecting/reconnecting
                self._on_global_metadata_changed()
            except Exception as e:
                Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Failed to connect to global_container_stack.metaDataChanged: {e}")
        else:
            Logger.log("w", f"{PluginConstants.PLUGIN_ID}: No global_container_stack available to connect metaDataChanged listener.")

    def _handle_global_container_stack_changed(self):
        """Handles the global container stack changing."""
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Global container stack has changed. Re-evaluating metadata listener connection.")
        self._connect_to_global_stack_metadata()

    def _on_global_metadata_changed(self): # Signature changed: no key argument
        """Handles changes to the global container stack's metadata."""
        self._update_plugin_menu_dialog_state()

    def _on_preference_changed(self, *args):  # Add *args to accept any additional arguments
        self._update_internal_state_from_printer_config()

    def _show_plugin_menu_dialog(self):
        """Displays the main plugin menu dialog."""
        # --- Check actual script state and update internal state/preference ---
        actual_script_state = self._is_post_processing_script_active()
        if self.pp_script_checkbox_state != actual_script_state:
            Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Actual PP script state ({actual_script_state}) differs from saved state ({self.pp_script_checkbox_state}). Updating.")
            self.pp_script_checkbox_state = actual_script_state
        # --- End check ---

        if self._plugin_menu_dialog_instance is not None and self._plugin_menu_dialog_instance.isVisible():
            self._update_plugin_menu_dialog_state()
            self._plugin_menu_dialog_instance.raise_()
            self._plugin_menu_dialog_instance.activateWindow()
            return

        try:
            from .PluginMenuDialog import PluginMenuDialog
        except ImportError as e:
            Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Could not import PluginMenuDialog: {e}")
            Message(text=f"Could not load the plugin menu dialog component.\nError: {e}",
                    title=catalog.i18n("[Print Skew Compensation Plugin Error]"),
                    message_type=Message.MessageType.ERROR).show()
            return

        self._plugin_menu_dialog_instance = PluginMenuDialog(parent=None)

        self._plugin_menu_dialog_instance.enter_measurements_requested.connect(self._show_measurement_dialog)
        self._plugin_menu_dialog_instance.add_model_requested.connect(self._add_calibration_model)
        self._plugin_menu_dialog_instance.add_marlin_gcode_toggled.connect(self._handle_add_marlin_gcode_request)
        self._plugin_menu_dialog_instance.add_klipper_gcode_toggled.connect(self._handle_add_klipper_gcode_request)
        self._plugin_menu_dialog_instance.enable_compensation_toggled.connect(self._handle_enable_compensation_toggle)
        self._plugin_menu_dialog_instance.toggle_post_processing_script_requested.connect(self._handle_toggle_post_processing_script)

        self._plugin_menu_dialog_instance.finished.connect(self._on_plugin_menu_dialog_finished)

        self._update_internal_state_from_printer_config()
        self._plugin_menu_dialog_instance.show()
        self._plugin_menu_dialog_instance.activateWindow()

    def _update_plugin_menu_dialog_state(self):
        if self._plugin_menu_dialog_instance:
            marlin_command = self._skew_calculator.get_marlin_command()
            klipper_command = self._skew_calculator.get_klipper_command()

            marlin_active = self.enabled and self.method == "marlin" and self.marlin_add_to_gcode
            klipper_active = self.enabled and self.method == "klipper" and self.klipper_add_to_gcode
            pp_script_active = self.enabled and self.method == "postprocessing" and self.pp_script_checkbox_state
            self._ensure_pp_script_state(pp_script_active)
            self._sync_gcode_based_on_state()

            self._plugin_menu_dialog_instance.update_display(
                marlin_gcode=marlin_command,
                klipper_gcode=klipper_command,
                is_enabled=self.enabled,
                is_pp_script_active=pp_script_active,
                marlin_method_active=marlin_active,
                klipper_method_active=klipper_active
            )

    def _is_post_processing_script_active(self) -> bool:
        try:
            post_processing_plugin = Application.getInstance().getPluginRegistry().getPluginObject("PostProcessingPlugin")
            if post_processing_plugin:
                active_script_keys = post_processing_plugin.scriptList
                is_active = PluginConstants.POST_PROCESSING_SCRIPT_NAME in active_script_keys
                self.pp_script_checkbox_state = is_active  # Update internal state
                return is_active
            else:
                Logger.log("w", f"{PluginConstants.PLUGIN_ID}: Could not get PostProcessingPlugin instance to check active scripts.")
        except Exception as e:
            Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Error checking active post-processing scripts: {e}")
        self.pp_script_checkbox_state = False  # Reset state if we can't determine it
        return False

    def _ensure_pp_script_state(self, target_state: bool) -> bool:
        """Adds or removes the PP script to match the target state."""
        script_key = PluginConstants.POST_PROCESSING_SCRIPT_NAME
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Ensuring PP script '{script_key}' state is {target_state}.")
        try:
            post_processing_plugin = Application.getInstance().getPluginRegistry().getPluginObject("PostProcessingPlugin")
            if not post_processing_plugin:
                Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Could not get PostProcessingPlugin instance to ensure script state.")
                return False

            current_index = -1
            active_script_keys = post_processing_plugin.scriptList
            for idx, script in enumerate(active_script_keys):
                if script == script_key:
                    current_index = idx
                    break
            is_currently_active = current_index != -1

            if target_state and not is_currently_active:
                loaded_scripts = post_processing_plugin.loadedScriptList
                if script_key in loaded_scripts:
                    post_processing_plugin.addScriptToList(script_key)
                    post_processing_plugin.writeScriptsToStack()
                    active_script_keys = post_processing_plugin.scriptList
                    current_index = len(active_script_keys) - 1
                    # Move the newly added script to index 0, one step at a time
                    for current_index in range(len(active_script_keys) - 1, 0, -1):
                        post_processing_plugin.moveScript(current_index, current_index - 1)
                    Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Added script '{script_key}' to active post-processing list.")
                    return True
                else:
                    Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Script '{script_key}' not found in loaded scripts. Cannot add.")
                    self.method = "none"
                    Message(text=catalog.i18n("The script '{script_key}' could not be found.").format(script_key=script_key), title=catalog.i18n("[Print Skew Compensation]")).show()
                    return False
            elif not target_state and is_currently_active:
                post_processing_plugin.removeScriptByIndex(current_index)
                post_processing_plugin.writeScriptsToStack()
                Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Removed script '{script_key}' from active post-processing list.")
                return True
            else:
                return True # State already correct

        except Exception as e:
            Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Error ensuring post-processing script state: {e}")
            Message(text=catalog.i18n("An error occurred while managing the post-processing script."), title=catalog.i18n("[Print Skew Compensation]")).show()
            return False

    def _sync_gcode_based_on_state(self):
        """Syncs start G-code based on the current internal state."""

        # Determine effective method and add flags based on enabled status
        effective_method = "none"
        add_marlin = False
        add_klipper = False

        if self.enabled:
            effective_method = self.method
            if self.method == "marlin" and self.marlin_add_to_gcode:
                add_marlin = True
            elif self.method == "klipper" and self.klipper_add_to_gcode:
                add_klipper = True
            # If method is 'none' or the specific add flag is false, flags remain False

        self._gcode_manager.sync_start_gcode(
            self._skew_calculator,
            effective_method, # Pass the effective method ('marlin', 'klipper', or 'none')
            add_marlin,       # Pass the specific flag for Marlin
            add_klipper       # Pass the specific flag for Klipper
        )

    def _handle_add_marlin_gcode_request(self, enable: bool):
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Manual request to add Marlin G-code to start script.")
        if not self.enabled:
            Message(text=catalog.i18n("Skew compensation is currently disabled. Marlin G-code will not be active until enabled."),
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
        elif enable:
            # --- Enforce Mutual Exclusivity ---
            self.method = "marlin"
            self.marlin_add_to_gcode = True
            self.klipper_add_to_gcode = False
            self._ensure_pp_script_state(False) # Action: ensure PP script is off
            self.pp_script_checkbox_state = False   # State: PP method is off
            # --- End Mutual Exclusivity ---

            # User Feedback
            Message(text=catalog.i18n("Compensation method set to Marlin and start G-code updated with the M852 command."),
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.POSITIVE).show()
        else: # Disabling Marlin
            self.method = "none"
            self.marlin_add_to_gcode = False
            self.klipper_add_to_gcode = False # Ensure Klipper is also off
            self._ensure_pp_script_state(False) # Action: ensure PP script is off
            self.pp_script_checkbox_state = False   # State: PP method is off

        # Update internal state after changing multiple prefs
        self._save_current_settings()


    def _handle_add_klipper_gcode_request(self, enable: bool):
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Manual request to add Klipper G-code to start script.")
        if not self.enabled:
            Message(text=catalog.i18n("Skew compensation is currently disabled. Klipper G-code will not be active until enabled."),
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
        elif enable:
            # --- Enforce Mutual Exclusivity ---
            self.method = "klipper"
            self.marlin_add_to_gcode = False
            self.klipper_add_to_gcode = True
            self._ensure_pp_script_state(False) # Action: ensure PP script is off
            self.pp_script_checkbox_state = False   # State: PP method is off
            # --- End Mutual Exclusivity ---
            # User Feedback
            Message(text=catalog.i18n("Compensation method set to Klipper and start G-code updated with the SET_SKEW command."),
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.POSITIVE).show()
        else: # Disabling Klipper
            self.method = "none"
            self.marlin_add_to_gcode = False
            self.klipper_add_to_gcode = False
            self._ensure_pp_script_state(False) # Action: ensure PP script is off
            self.pp_script_checkbox_state = False   # State: PP method is off

        self._save_current_settings()


    def _handle_toggle_post_processing_script(self, enable: bool):
        script_key = PluginConstants.POST_PROCESSING_SCRIPT_NAME
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Request to {'enable' if enable else 'disable'} post-processing script '{script_key}'. Current checkbox state: {self.pp_script_checkbox_state}")
        if not self.enabled:
            Message(text=catalog.i18n("Skew compensation is currently disabled. Post Processing G-code will not be active until enabled."),
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
        elif enable:
            self.method = "postprocessing"
            self.marlin_add_to_gcode = False
            self.klipper_add_to_gcode = False
            self.pp_script_checkbox_state = True
            self._ensure_pp_script_state(True)
            if self.pp_script_checkbox_state:
                Message(text=catalog.i18n("Compensation method set to Cura Post Processing and the script has been updated with the calculated values."),
                        title=catalog.i18n("[Print Skew Compensation]"),
                        message_type=Message.MessageType.POSITIVE).show()
        else:
            self.method = "none"
            self.marlin_add_to_gcode = False
            self.klipper_add_to_gcode = False
            self._ensure_pp_script_state(False) 
            self.pp_script_checkbox_state = False

        # Update internal state after potentially changing multiple prefs
        self._save_current_settings()

    def _handle_enable_compensation_toggle(self, enable: bool):
        self.enabled = enable
        self._save_current_settings()

    def _on_plugin_menu_dialog_finished(self, result):
        Logger.log("i", f"Plugin menu dialog finished with result: {result}")
        self._plugin_menu_dialog_instance = None

    def _show_measurement_dialog(self):
        if self._measurement_dialog_instance is not None and self._measurement_dialog_instance.isVisible():
            self._measurement_dialog_instance.raise_()
            self._measurement_dialog_instance.activateWindow()
            return

        self._measurement_dialog_instance = MeasurementDialogUI(controller=self)
        self._measurement_dialog_instance.calculation_done.connect(self._on_dialog_settings_saved)
        self._measurement_dialog_instance.finished.connect(self._on_dialog_finished)

        self._measurement_dialog_instance.show()
        self._measurement_dialog_instance.activateWindow()

    def _on_dialog_settings_saved(self):
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Measurement dialog settings saved.")
        self._save_current_settings()
        if self.enabled:
            self._gcode_manager.sync_start_gcode(
                self._skew_calculator,
                self.method,
                self.marlin_add_to_gcode,
                self.klipper_add_to_gcode
            )
        else:
            self._gcode_manager.sync_start_gcode(self._skew_calculator, "none", False, False)
        self._update_plugin_menu_dialog_state()

    def _on_dialog_finished(self, result):
        Logger.log("i", f"Measurement dialog finished with result: {result}")
        self._measurement_dialog_instance = None

    def _load_single_model(self, model_path: str) -> bool:
        if not os.path.exists(model_path):
            Logger.log("e", f"Calibration model file not found: {model_path}")
            return False
        try:
            file_url = QUrl.fromLocalFile(model_path)
            success = self._application.readLocalFile(file_url)
            if success:
                Logger.log("i", f"readLocalFile returned True for: {model_path}")
            else:
                Logger.log("w", f"readLocalFile returned False for: {model_path}. Model might still load asynchronously.")
            return True
        except Exception as e:
            Logger.logException("e", f"Error calling readLocalFile for model {model_path}: {e}")
            return False

    def _add_calibration_model(self, model_type: str):
        models_to_load = []
        msg_text = ""
        if model_type == "xy":
            models_to_load.append(("XY", os.path.join(PluginConstants.CALIBRATION_MODEL_PATH, "Skew_Model_XY.stl")))
            msg_text = "Make sure the XY model is oriented flat on the build plate with the X and Y sides aligned as shown on the model."
        elif model_type == "xz":
            models_to_load.append(("XZ", os.path.join(PluginConstants.CALIBRATION_MODEL_PATH, "Skew_Model_XZ.stl")))
            msg_text = "Make sure the XZ model is oriented vertically on the build plate with X and Z sides aligned as shown on the model."
        elif model_type == "yz":
            models_to_load.append(("YZ", os.path.join(PluginConstants.CALIBRATION_MODEL_PATH, "Skew_Model_YZ.stl")))
            msg_text = "Make sure the YZ model is oriented vertically on the build plate with the Y and Z sides aligned as shown on the model."
        elif model_type == "all":
            models_to_load.append(("All", os.path.join(PluginConstants.CALIBRATION_MODEL_PATH, "All_Skew_Models.stl")))
            msg_text = "The models should come in oriented as required. Make sure they are oriented as per the axes on each model."
        else:
            Logger.log("e", f"Invalid model type specified: {model_type}")
            Message(text=catalog.i18n("Invalid calibration model type specified."), lifetime=10, title=catalog.i18n("[Print Skew Compensation] Error")).show()
            return

        success_count = 0
        failed_models = []
        total_expected = len(models_to_load)

        for name, path in models_to_load:
            if self._load_single_model(path):
                success_count += 1
            else:
                failed_models.append(name)

        parent_widget = self._measurement_dialog_instance if self._measurement_dialog_instance and self._measurement_dialog_instance.isVisible() else None
        if success_count == total_expected:
            Message(text=msg_text,
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.NEUTRAL).show()
        elif success_count > 0:
            Logger.log("w", f"Initiated loading for {success_count}/{total_expected} model(s) of type '{model_type}', but failed for: {', '.join(failed_models)}")
            Message(text=("Some calibration models failed to load: {failed_list}").format(failed_list=', '.join(failed_models)), title=catalog.i18n("[Print Skew Compensation] Warning"), parent=parent_widget).show()
        else:
            Logger.log("e", f"Failed to initiate loading for any calibration models of type '{model_type}'. Failed: {', '.join(failed_models)}")
            Message(
                    text="Could not find or load the requested calibration model(s). Please check they exist in the plugin's 'calibration_model' folder.",
                    lifetime=10,
                    title=catalog.i18n("[Print Skew Compensation] Error"),
                    message_type=Message.MessageType.ERROR).show()
