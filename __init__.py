import os
import shutil
from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Resources import Resources
from UM.Logger import Logger
from UM.Message import Message

from .PluginConstants import PluginConstants

catalog = i18nCatalog("cura")

def getMetaData():
    """
    Provides metadata for the plugin.

    Returns:
        dict: A dictionary containing plugin metadata, specifically its view information.
    """
    return {
        "view": {
            "name": "Print Skew Compensation",
            "weight": 1
        }
    }

def _install_post_processing_script():
    """
    Copies the post-processing script to Cura's global scripts directory if not present or outdated.

    This function checks if the post-processing script, defined by POST_PROCESSING_SCRIPT_NAME,
    exists in the user's Cura scripts directory. If it doesn't, or if the existing script
    is different from the one bundled with the plugin (based on file size and modification time),
    it copies the bundled script to the destination.
    """
    source_script_file_path = os.path.join(PluginConstants.PLUGIN_PATH, "scripts", f"{PluginConstants.POST_PROCESSING_SCRIPT_NAME}.py")
    
    try:
        user_data_path = Resources.getDataStoragePath()
        if not user_data_path:
            Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Could not determine Cura's data storage directory.")
            return
        scripts_dir = os.path.join(user_data_path, "scripts")
    except Exception as e:
        Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Error getting Cura's data storage directory path: {e}")
        return

    if not os.path.exists(source_script_file_path):
        Logger.log("e", f"{PluginConstants.PLUGIN_ID}: Post-processing script not found at {source_script_file_path}")
        Message(text=f"Post-processing script '{PluginConstants.POST_PROCESSING_SCRIPT_NAME}' was not found within the plugin files. It will not be installed.",
                lifetime=10,
                title=catalog.i18n("Plugin Script Missing"),
                message_type=Message.MessageType.ERROR
                ).show()
        return
    
    current_script_file_path = os.path.join(scripts_dir, f"{PluginConstants.POST_PROCESSING_SCRIPT_NAME}.py")
    try:
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir)
            Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Created scripts directory at {scripts_dir}")
        
        if os.path.exists(current_script_file_path):
            # Check if the file already exists and compare sizes and modification times
            # to avoid unnecessary copying
            source_stat = os.stat(source_script_file_path)
            dest_stat = os.stat(current_script_file_path)
            if source_stat.st_size == dest_stat.st_size and int(source_stat.st_mtime) == int(dest_stat.st_mtime):
                return
        
        shutil.copy2(source_script_file_path, scripts_dir)
        Logger.log("i", f"{PluginConstants.PLUGIN_ID}: Successfully copied {PluginConstants.POST_PROCESSING_SCRIPT_NAME} to {scripts_dir}")
    except Exception as e:
        Logger.logException("e", f"{PluginConstants.PLUGIN_ID}: Error copying post-processing script: {e}")

def register(app: Application):
    """
    Registers the plugin with the Cura application.

    This function is called by Cura to initialize the plugin. It performs necessary setup,
    such as installing the post-processing script, and then creates and returns the
    main plugin controller.

    Args:
        app (Application): The main Cura application instance.

    Returns:
        dict: A dictionary containing the extension instance, mapping "extension" to the PluginController.
    """
    from .PluginController import PluginController
    # Call the script installation function
    _install_post_processing_script()
    return { "extension": PluginController() }
