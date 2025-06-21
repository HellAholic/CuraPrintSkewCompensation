import os
from enum import Enum

class OperatingSystem(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    OTHER = "other"

class PluginConstants:
    PLUGIN_ID = "PrintSkewCompensation"
    POST_PROCESSING_SCRIPT_NAME = "PrintSkewCompensationCKM"
    PLUGIN_PATH = os.path.dirname(os.path.abspath(__file__))
    CALIBRATION_MODEL_PATH = os.path.join(PLUGIN_PATH, "calibration_model")
    PLUGIN_CONFIGURATION_PATH = os.path.join(PLUGIN_PATH, "configuration")
    START_GCODE_KEY = "machine_start_gcode"

    # --- Operating System ---
    CURRENT_OS = None

    @staticmethod
    def get_operating_system():
        if PluginConstants.CURRENT_OS is None:
            os_name = os.name
            if os_name == "nt":
                PluginConstants.CURRENT_OS = OperatingSystem.WINDOWS
            elif os_name == "posix":
                try:
                    # uname provides more detailed information on POSIX systems
                    uname_info = os.uname()
                    if uname_info.sysname == "Darwin":
                        PluginConstants.CURRENT_OS = OperatingSystem.MACOS
                    elif uname_info.sysname == "Linux":
                        PluginConstants.CURRENT_OS = OperatingSystem.LINUX
                    else:
                        PluginConstants.CURRENT_OS = OperatingSystem.OTHER
                except AttributeError:
                    # Fallback to a generic LINUX if uname fails on a posix system.
                    PluginConstants.CURRENT_OS = OperatingSystem.LINUX
            else:
                PluginConstants.CURRENT_OS = OperatingSystem.OTHER # e.g., 'java'
        return PluginConstants.CURRENT_OS

    # --- Theme Colors ---
    DARK_BACKGROUND_COLOR = "#2d2d2d"
    TEXT_COLOR_LIGHT_GRAY = "#E0E0E0"
    TEXT_INPUT_BG_COLOR_DARK_GRAY = "#3c3c3c"
    TEXT_INPUT_BORDER_COLOR_GRAY = "#505050"
    TEXT_COLOR_HIGHLIGHTED_BG = "#1B1B1B"
    ERROR_TEXT_COLOR_LIGHT_RED = "#FF6B6B"
    GROUPBOX_BORDER_COLOR = "#BBBBBB"

    # --- Dialog sizes ---
    MINIMUM_DIALOG_WIDTH = 800 if CURRENT_OS == OperatingSystem.WINDOWS else 900
    MINIMUM_DIALOG_HEIGHT = 500
    MAXIMUM_DIALOG_WIDTH = 1000
    MAXIMUM_DIALOG_HEIGHT = 650 if CURRENT_OS == OperatingSystem.WINDOWS else 720

    HELP_PAGE_SPLIT_SIZE = [200, 500] if CURRENT_OS == OperatingSystem.WINDOWS else [250, 550]

    # --- Button Colors ---
    BUTTON_PRIMARY_BG = "#0078d7"
    BUTTON_PRIMARY_HOVER_BG = "#005a9e"
    BUTTON_PRIMARY_TEXT = "#FFFFFF"
    BUTTON_PRIMARY_BORDER = "#FFFFFF"

    BUTTON_CLOSE_BG = "#FFFFFF"
    BUTTON_CLOSE_TEXT = "#e81123"
    BUTTON_CLOSE_BORDER = "#e81123"
    BUTTON_CLOSE_HOVER_BG = "#f4f4f4"

    BUTTON_SECONDARY_BORDER = "#cccccc"
    BUTTON_SECONDARY_BG = "#f9f9f9"
    BUTTON_SECONDARY_TEXT = "#333333"
    BUTTON_SECONDARY_HOVER_BG = "#e0e0e0"
    HIGHLIGHT_COLOR = "#006cc4"

    # --- General Styles ---
    TITLE_STYLE = f"font-size: 13px; font-weight: bold; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    DESCRIPTION_STYLE_MENU = f"font-size: 12px; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    DESCRIPTION_STYLE_FORM = f"font-size: 12px; margin-bottom: 3px; color: {TEXT_COLOR_LIGHT_GRAY};"
    INPUT_TEXT_STYLE = f"background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY}; color: {TEXT_COLOR_LIGHT_GRAY}; border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY}; border-radius: 3px; padding: 2px;"
    LABEL_STYLE_FORM = f"color: {TEXT_COLOR_LIGHT_GRAY}; font-size: 13px"
    RESULT_LABEL_STYLE_FORM = f"color: {TEXT_COLOR_LIGHT_GRAY}; font-size: 13px"
    DIALOG_BACKGROUND_STYLE = f"background-color: {DARK_BACKGROUND_COLOR};"

    GROUPBOX_STYLE = f'''
        QGroupBox {{
            border: 1px solid {GROUPBOX_BORDER_COLOR};
            border-radius: 5px;
        }}
    '''

    GROUPBOX_STYLE_MEASUREMENT = f'''
        QGroupBox {{
            border: 1px solid {GROUPBOX_BORDER_COLOR};
            border-radius: 5px;
            margin-top: 20px;
        }}
        QGroupBox::title {{
            color: {TEXT_COLOR_LIGHT_GRAY};
            font-size: 13px;
            font-weight: bold;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0px 5px;
            left: 10px; /* Offset to align title within the border */
        }}
    '''

    # --- Tooltip Style ---
    CHECKBOX_STYLE = f'''
        QCheckBox {{
            background-color: {DARK_BACKGROUND_COLOR};
            color: {TEXT_COLOR_LIGHT_GRAY};
        }}
        QToolTip {{
            background-color: {DARK_BACKGROUND_COLOR};
            color: {TEXT_COLOR_LIGHT_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            padding: 5px;
            border-radius: 3px;
            font-size: 13px
        }}
    '''

    # --- Button Styles ---
    SELECT_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 10px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_PRIMARY_BG}; border: 1px solid {BUTTON_PRIMARY_BORDER};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; min-width: 80px;
        }} QPushButton:hover {{ background-color: {BUTTON_PRIMARY_HOVER_BG}; }}
    '''
    CLOSE_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 10px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_CLOSE_BG}; border: 1px solid {BUTTON_CLOSE_BORDER};
            color: {BUTTON_CLOSE_TEXT}; border-radius: 3px; min-width: 80px;
        }} QPushButton:hover {{ background-color: {BUTTON_CLOSE_HOVER_BG}; }}
    '''
    MEASURE_BUTTON_STYLE = f'''
        QPushButton {{
            padding: 5px 15px; margin-left: 5px; margin-right: 5px;
            background-color: {BUTTON_PRIMARY_BG}; border: 1px solid {BUTTON_PRIMARY_BORDER};
            color: {BUTTON_PRIMARY_TEXT}; border-radius: 3px; font-size: 14px
        }} QPushButton:hover {{ background-color: {BUTTON_PRIMARY_HOVER_BG}; }}
    '''

    HELP_PAGE_STYEL = f'''
        QListWidget {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            color: {TEXT_COLOR_LIGHT_GRAY};
            border: 1px solid {GROUPBOX_BORDER_COLOR};
            padding: 5px;
        }}
        QListWidget:focus {{
            outline: none;
        }}
        QListWidget::item {{
            padding: 5px;
        }}
        QListWidget::item:selected {{
            background-color: {HIGHLIGHT_COLOR};
            color: {BUTTON_PRIMARY_TEXT};
        }}
        QTextEdit {{
            background-color: {TEXT_INPUT_BG_COLOR_DARK_GRAY};
            color: {TEXT_COLOR_LIGHT_GRAY};
            border: 1px solid {TEXT_INPUT_BORDER_COLOR_GRAY};
            padding: 5px;
            font-size: 12px;
        }}
    '''

    GROUP_TITLE_LABEL_STYLE = f"color: {TEXT_COLOR_LIGHT_GRAY};"
    HELP_BUTTON_STYLE = f'''
        QPushButton {{
            background-color: {BUTTON_PRIMARY_BG};
            color: {BUTTON_PRIMARY_TEXT};
            border: 1px solid {BUTTON_PRIMARY_BORDER};
            border-radius: 7.5px;
            min-width: 15px;
            max-width: 15px;
            min-height: 15px;
            max-height: 15px;
        }}
        QPushButton:hover {{
            background-color: {BUTTON_PRIMARY_HOVER_BG};
        }}
    '''
