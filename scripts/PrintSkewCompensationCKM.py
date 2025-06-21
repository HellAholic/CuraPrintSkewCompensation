"""
Designed by GregValiant (Greg Foresi) in April of 2025.
The script requires that a calibration print is done for each axis plane (XY, XZ, YZ) and it is measured.
There are three main options:
    'Cura':
        Will go through the gcode and adjust it per the skew factors.
    'Marlin' and 'Klipper':
        Will use the entered values to calculate the skew factors and then enter them into the StartUp Gcode.  For 'Marlin' that is an M852 line.  'Klipper' is 'SET_SKEW'.
"""
import math
import json
import configparser
import os
import hashlib
import re

from UM.Application import Application
from ..Script import Script
from UM.Logger import Logger
from UM.Message import Message
from UM.i18n import i18nCatalog
from UM.Resources import Resources

catalog = i18nCatalog("cura")

class PrintSkewCompensationCKM(Script):
    def __init__(self):
        super().__init__()
        self._application = Application.getInstance()
        self._plugin_enabled = None
        self._settings_source = None
        self.cura_configuration_path = Resources.getConfigStoragePath()
        self.script_key = "PrintSkewCompensationCKM"
        self._plugin_settings = self._get_default_settings()
        self.found_in_configuration = False
        self._calculated_factors = {
            "xy": 0.0,
            "xz": 0.0,
            "yz": 0.0
        }
    
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
    
    def _read_printer_settings_from_file(self, printer_name) -> dict:
        """Reads printer settings from the plugin's configuration file for the given printer name."""
        cfg_path = self._get_printer_cfg_path(printer_name)
        if not os.path.exists(cfg_path):
            Logger.log("w", f"{self.script_key}: Printer settings file does not exist: {cfg_path}. Using default settings.")
            return self._get_default_settings()

        config = configparser.ConfigParser()
        config.read(cfg_path)

        if 'settings' not in config:
            Logger.log("w", f"{self.script_key}: No 'settings' section found in {cfg_path}. Using default settings.")
            return self._get_default_settings()

        settings = {k: v for k, v in config['settings'].items()}
        return settings
    
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

    def _get_printer_cfg_path(self, printer_name) -> str:
        """Returns the path to the plugin's printer configuration file path based on the printer name."""
        if not printer_name:
            Logger.log("e", f"{self.script_key}: Printer name is empty, cannot determine config path.")
            return None
        printer_file_name = self._sanitized_settings_file_name(printer_name)
        plugin_path = os.path.join(self.cura_configuration_path, "plugins", "PrintSkewCompensation")
        cfg_path = os.path.join(plugin_path, "configuration", printer_file_name)
        return cfg_path
    
    def _calculate_factors_from_configuration(self):
        # XY Axis - Calculate only if measurements are valid
        current_printer_name = self._get_current_printer_name()
        self._plugin_settings = self._read_printer_settings_from_file(current_printer_name)
        
        raw_comp_enabled_value = self._plugin_settings.get("compensation_enabled", False)
        if isinstance(raw_comp_enabled_value, str):
            self._plugin_enabled = raw_comp_enabled_value.lower() == 'true'
        else:
            self._plugin_enabled = bool(raw_comp_enabled_value) # Ensures it's a proper boolean if it was already (e.g. from defaults)
        
        def get_float_setting(key_name: str) -> float | None:
            """Safely retrieves and converts a setting to float."""
            str_value = self._plugin_settings.get(key_name)
            if str_value is None:
                # Logger.log("d", f"[{self.script_key}] Setting '{key_name}' not found in configuration.")
                return None
            try:
                return float(str_value)
            except ValueError:
                Logger.log("w", f"[{self.script_key}] Invalid float value for setting '{key_name}': '{str_value}'. Using None.")
                return None

        xy_ac = get_float_setting("xy_ac_measurement")
        xy_bd = get_float_setting("xy_bd_measurement")
        xy_ad = get_float_setting("xy_ad_measurement")

        if None not in [xy_ac, xy_bd, xy_ad]:
            try:
                self._calculated_factors["xy"] = self.calculate_skew_factor(
                    xy_ac,
                    xy_bd,
                    xy_ad
                )
                Logger.log("i", f"[{self.script_key}] Calculated XY skew factor from configuration measurements: {self._calculated_factors['xy']}")
                self._settings_source = "configuration (calculated)"
                self.found_in_configuration = True
            except Exception as e_xy_calc:
                Logger.log("w", f"[{self.script_key}] Could not calculate XY factor from configuration measurements: {e_xy_calc}")
                self._calculated_factors["xy"] = 0.0
        else:
             self._calculated_factors["xy"] = 0.0

        # XZ Axis - Calculate only if measurements are valid
        xz_ac = get_float_setting("xz_ac_measurement")
        xz_bd = get_float_setting("xz_bd_measurement")
        xz_ad = get_float_setting("xz_ad_measurement")

        if None not in [xz_ac, xz_bd, xz_ad]:
            try:
                self._calculated_factors["xz"] = self.calculate_skew_factor(
                    xz_ac,
                    xz_bd,
                    xz_ad
                )
                Logger.log("i", f"[{self.script_key}] Calculated XZ skew factor from configuration measurements: {self._calculated_factors['xz']}")
                # Don't overwrite settings_source if already set by XY
                if self._settings_source == "configuration": self._settings_source = "configuration (calculated)" # Note: This condition might need review if settings_source can be None initially
                elif self._settings_source is None: self._settings_source = "configuration (calculated)" # Ensure it's set if XY was skipped
                self.found_in_configuration = True
            except Exception as e_xz_calc:
                Logger.log("w", f"[{self.script_key}] Could not calculate XZ factor from configuration measurements: {e_xz_calc}")
                self._calculated_factors["xz"] = 0.0
        else:
             self._calculated_factors["xz"] = 0.0

        # YZ Axis - Calculate only if measurements are valid
        yz_ac = get_float_setting("yz_ac_measurement")
        yz_bd = get_float_setting("yz_bd_measurement")
        yz_ad = get_float_setting("yz_ad_measurement")

        if None not in [yz_ac, yz_bd, yz_ad]:
            try:
                self._calculated_factors["yz"] = self.calculate_skew_factor(
                    yz_ac,
                    yz_bd,
                    yz_ad
                )
                Logger.log("i", f"[{self.script_key}] Calculated YZ skew factor from configuration measurements: {self._calculated_factors['yz']}")
                # Don't overwrite settings_source if already set by XY/XZ
                if self._settings_source == "configuration": self._settings_source = "configuration (calculated)"
                elif self._settings_source is None: self._settings_source = "configuration (calculated)" # Ensure it's set if XY/XZ were skipped
                self.found_in_configuration = True
            except Exception as e_yz_calc:
                Logger.log("w", f"[{self.script_key}] Could not calculate YZ factor from configuration measurements: {e_yz_calc}")
                self._calculated_factors["yz"] = 0.0
        else:
             self._calculated_factors["yz"] = 0.0

        # If no factors were obtained from configuration, mark configurations as effectively disabled for factor calculation
        if not self.found_in_configuration and self._plugin_enabled:
            Logger.log("w", f"[{self.script_key}] configuration enabled, but failed to calculate any skew factors from configuration measurements.")
            self._plugin_enabled = False # Treat as disabled for factor calculation purposes
        elif not self._plugin_enabled:
             # Ensure factors are zero if configurations were disabled from the start
             self._calculated_factors = {"xy": 0.0, "xz": 0.0, "yz": 0.0}

    def getSettingDataString(self):
        
        # Base settings structure
        settings = {
            "name": "Print Skew Compensation CKM",
            "key": "PrintSkewCompensationCKM",
            "metadata": {},
            "version": 2,
            "settings": {
                "enable_print_skew_comp": {
                    "label": "Enable Print Skew Comp",
                    "description": "This script is used by the 'Print Skew Compensation' Plugin and the settings it uses are the Plugin settings.  It is added into the post processing list when 'Cura Mode' is selected in the plugin.  If you disable the script here then the gcode will not be altered. NOTE:  This script should be first in the post-processing list.",
                    "type": "bool",
                    "default_value": True,
                    "enabled": True
                }
            }
        }

        return json.dumps(settings, indent=4)

    def execute(self, data: list) -> list:
        if self._plugin_enabled is False:
            Message(text="Print Skew Compensation plugin is not enabled, the post processing script will not run.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
            return data
        
        # Exit if the post processor is not enabled via script setting
        if not bool(self.getSettingValueByKey("enable_print_skew_comp")):
            data[0] += ";[Print Skew Compensation] not enabled via script setting\n"
            Message(text="Script was not enabled via script settings. The script will not run.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
            return data

        # Exit if the gcode has already been post-processed
        if ";POSTPROCESSED" in data[0]:
            Message(text="Already post-processed. The script will not run again.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.WARNING).show()
            return data

        # Notify the user that this script should run first
        post_processing_plugin = Application.getInstance().getPluginRegistry().getPluginObject("PostProcessingPlugin")
        active_script_keys = post_processing_plugin.scriptList
        for idx, script in enumerate(active_script_keys):
            if script == self.script_key:
                if idx != 0:
                    Message(
                            text="Script Should be first in the Post-Processor list. It will run if it's not first, " \
                            "but any following post-processors should act on the changes made by Print Skew Compensation",
                            title=catalog.i18n("[Print Skew Compensation]"),
                            message_type=Message.MessageType.WARNING).show()
                break           
        
        # Load settings from the plugin configuration file
        self._calculate_factors_from_configuration()
        enable_xy_skew = False
        enable_xz_skew = False
        enable_yz_skew = False

        if self.found_in_configuration is True:
            if self._calculated_factors["xy"] != 0:
                enable_xy_skew = True
            if self._calculated_factors["xz"] != 0:
                enable_xz_skew = True
            if self._calculated_factors["yz"] != 0:
                enable_yz_skew = True
            if enable_xy_skew or enable_xz_skew or enable_yz_skew:
                Logger.log("i", f"[{self.script_key}] Using factors calculated from configuration: XY={self._calculated_factors['xy']:.8f}, XZ={self._calculated_factors['xz']:.8f}, YZ={self._calculated_factors['yz']:.8f}")
            else:
                Logger.log("i", f"[{self.script_key}] configuration enabled, but no factors applied (Zero skew factor).")
                Message(text="The post processor did not receive a non-zero value from the plugin.",
                        title=catalog.i18n("[Print Skew Compensation]"),
                        message_type=Message.MessageType.WARNING).show()
                return data
        else:
            Logger.log("w",f"[{self.script_key}] The Print Skew post script was unable to get the settings from the Cura plugin.")
            Message(text="The post processor did not receive the settings from the Plugin.",
                    title=catalog.i18n("[Print Skew Compensation]"),
                    message_type=Message.MessageType.ERROR).show()
            return data

        data[0] += f";  [Print Skew Compensation] Applying skew compensation using values from: {self._settings_source}\n"

        data = self.cura_compensation(data)

        # Add the skew factors to the end of the gcode
        setting_string = (
            f";  Print Skew Compensation Settings:\n"
            f";    xy_ac_measurement: {self._plugin_settings.get('xy_ac_measurement')}\n"
            f";    xy_bd_measurement: {self._plugin_settings.get('xy_bd_measurement')}\n"
            f";    xy_ad_measurement: {self._plugin_settings.get('xy_ad_measurement')}\n"
            f";        XY skew factor:    {round(self._calculated_factors['xy'], 8)}\n"
            f";    xz_ac_measurement: {self._plugin_settings.get('xz_ac_measurement')}\n"
            f";    xz_bd_measurement: {self._plugin_settings.get('xz_bd_measurement')}\n"
            f";    xz_ad_measurement: {self._plugin_settings.get('xz_ad_measurement')}\n"
            f";        XZ skew factor:    {round(self._calculated_factors['xz'], 8)}\n"
            f";    yz_ac_measurement: {self._plugin_settings.get('yz_ac_measurement')}\n"
            f";    yz_bd_measurement: {self._plugin_settings.get('yz_bd_measurement')}\n"
            f";    yz_ad_measurement: {self._plugin_settings.get('yz_ad_measurement')}\n"
            f";        YZ skew factor:    {round(self._calculated_factors['yz'], 8)}\n"
        )
        data.append(setting_string)

        return data

    def calculate_skew_factor(self, ac: float, bd: float, ad:float) -> float:
        if ac <= 0 or bd <= 0 or ad <= 0:
            Logger.log("w", f"[Print Skew Compensation] Invalid measurement(s) for calculation: AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
            return 0.0
        try:
            term_sqrt = 2*ac*ac + 2*bd*bd - 4*ad*ad
            if term_sqrt < 0:
                 Logger.log("w", f"[Print Skew Compensation] Invalid measurements leading to negative sqrt term ({term_sqrt}). Check calibration print measurements. AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
                 return 0.0
            ab = math.sqrt(term_sqrt) / 2

            denominator_acos = 2 * ab * ad
            if denominator_acos == 0:
                Logger.log("w", f"[Print Skew Compensation] Invalid measurements leading to zero denominator in acos. Check calibration print measurements. AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
                return 0.0

            arg_acos = (ac*ac - ab*ab - ad*ad) / denominator_acos
            if not (-1 <= arg_acos <= 1):
                 Logger.log("w", f"[Print Skew Compensation] Invalid measurements leading to acos argument out of range ({arg_acos}). Check calibration print measurements. AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
                 return 0.0

            skew_comp = math.tan(math.pi/2 - math.acos(arg_acos))
            return skew_comp
        except ValueError as e:
            Logger.log("e", f"[Print Skew Compensation] Math error during skew calculation: {e}. Measurements: AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
            return 0.0
        except Exception as e:
             Logger.log("e", f"[Print Skew Compensation] Unexpected error during skew calculation: {e}. Measurements: AC={ac}, BD={bd}, AD={ad}. Returning 0 skew factor.")
             return 0.0

    def cura_compensation(self, cura_data: str) -> str:
        # z_input is cummulative
        z_input = 0
        cur_x = 0
        cur_y = 0
        cur_z = 0
        for layer_index, layer in enumerate(cura_data):
            lines = layer.split("\n")

            # Get the X, Y, Z locations
            for index, line in enumerate(lines):
                if line.startswith(("G0", "G1")):
                    cur_x = self.getValue(line, "X", None)
                    cur_y = self.getValue(line, "Y", None)
                    cur_z = self.getValue(line, "Z", None)

                    # Reset x_input and y_input every time through
                    x_input = 0
                    y_input = 0

                    # Equivalencies to avoid confusion
                    if cur_x != None:
                        x_input = cur_x
                    if cur_y != None:
                        y_input = cur_y
                    if cur_z != None:
                        z_input = cur_z

                    # Calculate the skew compensation
                    x_out = round(x_input - y_input * self._calculated_factors["xy"], 3)
                    x_out = round(x_out - z_input * self._calculated_factors["xz"], 3)
                    y_out = round(y_input - z_input * self._calculated_factors["yz"], 3)

                    # If the first layer hasn't started then jump out (after tracking the XYZ).
                    if layer_index < 2:
                        continue

                    # Alter the current line
                    if cur_x != None:
                        lines[index] = lines[index].replace(f"X{cur_x}", f"X{x_out}")
                    if cur_y != None:
                        lines[index] = lines[index].replace(f"Y{cur_y}", f"Y{y_out}")
            cura_data[layer_index] = "\n".join(lines)
        return cura_data
