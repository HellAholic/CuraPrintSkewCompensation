from UM.Application import Application
from UM.Logger import Logger
from UM.Settings.InstanceContainer import InstanceContainer # Added import

from .PluginConstants import PluginConstants
from .SkewCalculator import SkewCalculator # Add this import

class GCodeManager:
    """Manages modifications to G-code, particularly for syncing skew compensation commands."""
    def __init__(self, application: "Application", logger: "Logger"):
        """
        Initializes the GCodeManager.

        Args:
            application (Application): The main Cura application instance.
            logger (Logger): The logger instance for logging messages.
        """
        self._application = application
        self._logger = logger
        self._plugin_id = PluginConstants.PLUGIN_ID
        self._starg_gcode_key = PluginConstants.START_GCODE_KEY

    def _find_current_settings_container(self, global_stack):
        """Helper to find the user-specific settings container."""
        active_printer_display_id = global_stack.getId()
        settings_container = None

        # Try finding printer settings container by "<global stack id>_settings" ID convention
        printer_settings_container_id = f"{active_printer_display_id}_settings"
        found_container = global_stack.findContainer(criteria={"id": printer_settings_container_id})
        if found_container and isinstance(found_container, InstanceContainer):
            settings_container = found_container
            Logger.log("i", f"PrintSkewCompensation: Found settings container by ID: {printer_settings_container_id}")
        
        if not settings_container: # Fallback to top if no settings container found (less ideal but safe in terms of functionality)
            self._logger.log("w", f"{self._plugin_id}: No specific settings container found, falling back to global stack top.")
            top_container = global_stack.getTop()
            if isinstance(top_container, InstanceContainer):
                settings_container = top_container
            else:
                self._logger.log("w", f"{self._plugin_id}: Top container in stack is not an InstanceContainer.")
                return None
        
        return settings_container

    def sync_start_gcode(self, skew_calculator: "SkewCalculator", method: str, marlin_add: bool, klipper_add: bool):
        """
        Ensures the correct skew command (or none) is in the start G-code
        based on the current plugin settings.

        Args:
            skew_calculator (SkewCalculator): The calculator instance to get skew commands.
            method (str): The firmware type ("marlin", "klipper", or "none").
            marlin_add (bool): Whether to add the Marlin command.
            klipper_add (bool): Whether to add the Klipper command.
        """

        global_stack = self._application.getGlobalContainerStack()
        if not global_stack:
            self._logger.log("w", f"{self._plugin_id}: Could not get global container stack for G-code sync.")
            return

        settings_container = self._find_current_settings_container(global_stack)
        if not settings_container:
            self._logger.log("w", f"{self._plugin_id}: Could not find a suitable settings container for G-code sync.")
            return

        try:
            # Get property from the global stack to ensure we get inherited values
            current_start_gcode = global_stack.getProperty(self._starg_gcode_key, "value")
            if current_start_gcode is None:
                self._logger.log("w", f"{self._plugin_id}: '{self._starg_gcode_key}' is None in the global stack. Using empty string.")
                current_start_gcode = ""
        except Exception as e:
             self._logger.logException("e", f"{self._plugin_id}: Error getting current start G-code from global stack: {e}")
             return

        # Get potential commands based on current calculator state
        try:
            marlin_command = skew_calculator.get_marlin_command()
            klipper_command = skew_calculator.get_klipper_command()
        except Exception as e:
            self._logger.logException("e", f"{self._plugin_id}: Error generating skew commands: {e}")
            return # Don't modify G-code if commands can't be generated

        marlin_prefix = "M852"
        klipper_prefix = "SET_SKEW"
        plugin_comment = f"; {self._plugin_id}"

        # Determine which command *should* be present based on current settings
        command_to_ensure = None
        if method == "marlin" and marlin_add:
            command_to_ensure = marlin_command
        elif method == "klipper" and klipper_add:
            command_to_ensure = klipper_command

        # Filter existing lines, removing *any* skew commands previously added by this plugin
        new_gcode_lines = []
        command_removed = False
        lines_changed = False # Track if any line was added or removed
        existing_command_found_and_correct = False

        for line in current_start_gcode.splitlines():
            stripped_line = line.strip()
            # Check if the line starts with the prefix AND contains the plugin comment
            is_marlin_skew = stripped_line.startswith(marlin_prefix) and plugin_comment in stripped_line
            is_klipper_skew = stripped_line.startswith(klipper_prefix) and plugin_comment in stripped_line

            if not is_marlin_skew and not is_klipper_skew:
                new_gcode_lines.append(line) # Keep non-plugin lines
            else:
                # It's a skew command from this plugin
                if command_to_ensure and stripped_line == command_to_ensure:
                    # This is the command we want, and it's already here. Keep it.
                    new_gcode_lines.append(line)
                    existing_command_found_and_correct = True
                else:
                    # This is an old/incorrect skew command from this plugin, or no command should be present. Remove it.
                    command_removed = True
                    lines_changed = True # Mark that a line was removed

        # Add the required command if it wasn't already present and correct
        command_added = False
        if command_to_ensure and not existing_command_found_and_correct:
            # Double-check it's not somehow present without the comment (unlikely but safe)
            already_present_exact = any(line.strip() == command_to_ensure for line in new_gcode_lines)
            if not already_present_exact:
                new_gcode_lines.append(command_to_ensure)
                command_added = True
                lines_changed = True # Mark that a line was added
            else:
                 self._logger.log("w", f"{self._plugin_id}: Required skew command '{command_to_ensure}' was found but potentially missing plugin comment. Not adding duplicate.")


        # Only set property if the gcode actually changed
        if lines_changed:
            new_start_gcode = "\n".join(new_gcode_lines)
            # Final check against original content, just in case logic above resulted in no net change
            if new_start_gcode != current_start_gcode:
                self._logger.log("i", f"{self._plugin_id}: Synchronizing start G-code skew command. Added={command_added}, Removed={command_removed}")
                try:
                    # Set the property in the found settings_container
                    settings_container.setProperty(self._starg_gcode_key, "value", new_start_gcode)
                    self._logger.log("i", f"{self._plugin_id}: Successfully set start G-code in container '{settings_container.getId()}'.")
                except Exception as e:
                    self._logger.logException("e", f"{self._plugin_id}: Error setting start G-code in container '{settings_container.getId()}': {e}")
            else:
                 self._logger.log("i", f"{self._plugin_id}: Start G-code content did not change after sync logic.")
        else:
            self._logger.log("i", f"{self._plugin_id}: Start G-code already correctly synchronized for skew command.")
