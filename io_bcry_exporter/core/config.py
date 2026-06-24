# ------------------------------------------------------------------------------
# Name:        core/config.py
# Purpose:     Stores BCRY Exporter configuration settings
# ------------------------------------------------------------------------------

import json
import os
import bpy

from .logger import bcPrint


def _get_filename(path):
    """Helper to extract filename without extension.

    This avoids importing from 'utils' package, preventing circular dependency issues.
    """
    base = os.path.basename(path.replace("\\", "/"))
    return os.path.splitext(base)[0]


class __Configuration:
    _CONFIG_PATH = bpy.utils.user_resource("CONFIG", path="scripts", create=True)
    _CONFIG_FILENAME = "bcry.json"
    _CONFIG_FILEPATH = os.path.join(_CONFIG_PATH, _CONFIG_FILENAME)

    # Dictionary containing all default configurable key-value pairs
    _DEFAULT_CONFIGURATION = {
        "RC_PATH": r"",
        "TEXTURE_RC_PATH": r"",
        "GAME_DIR": r"",
        "LEGACY_RC": False,
        "APPLY_MODIFIERS": True,
        "MERGE_ALL_NODES": False,
        "EXPORT_SELECTED_NODES": False,
        "CUSTOM_NORMALS": True,
        "USE_F32_VERTEX_FORMAT": False,
        "EIGHT_WEIGHTS_PER_VERTEX": False,
        "VCLOTH_PRE_PROCESS": False,
        "GENERATE_MATERIALS": False,
        "CONVERT_TEXTURES": False,
        "MAKE_CHRPARAMS": False,
        "MAKE_CDF": False,
        "FIX_WEIGHTS": False,
        "EXPORT_FOR_LUMBERYARD": False,
        "MAKE_LAYER": False,
        "DISABLE_RC": False,
        "SAVE_DAE": False,
        "SAVE_TIFFS": False,
        "RUN_IN_PROFILER": False,
    }

    def __init__(self):
        super().__init__()
        # Assign configuration dict explicitly via super().__setattr__ to bypass
        # dynamic overrides during initialization
        super().__setattr__("_config", self.__load({}))

    @property
    def rc_path(self):
        return self._config["RC_PATH"]

    @rc_path.setter
    def rc_path(self, value):
        self._config["RC_PATH"] = value

    @property
    def texture_rc_path(self):
        if not self._config["TEXTURE_RC_PATH"]:
            return self.rc_path

        return self._config["TEXTURE_RC_PATH"]

    @texture_rc_path.setter
    def texture_rc_path(self, value):
        self._config["TEXTURE_RC_PATH"] = value

    @property
    def game_dir(self):
        return self._config["GAME_DIR"]

    @game_dir.setter
    def game_dir(self, value):
        self._config["GAME_DIR"] = value

    def __getattr__(self, name):
        # Dynamic reading of exporter properties from JSON settings
        upper_name = name.upper()
        if upper_name in self._DEFAULT_CONFIGURATION:
            return self._config.get(upper_name, self._DEFAULT_CONFIGURATION[upper_name])
        raise AttributeError(f"__Configuration object has no attribute {name!r}")

    def __setattr__(self, name, value):
        upper_name = name.upper()
        if upper_name in self._DEFAULT_CONFIGURATION:
            self._config[upper_name] = value
        else:
            super().__setattr__(name, value)

    def configured(self):
        """Checks if the Resource Compiler executable path is set and valid."""
        path = self._config["RC_PATH"]
        if len(path) > 0 and _get_filename(path).lower() == "rc":
            return True

        return False

    def save(self):
        """Saves current configuration parameters to a persistent JSON file."""
        bcPrint("Saving configuration file.", "debug")

        if os.path.isdir(self._CONFIG_PATH):
            try:
                with open(self._CONFIG_FILEPATH, "w", encoding="utf-8") as f:
                    json.dump(self._config, f, indent=4, ensure_ascii=False)
                    bcPrint("Configuration file saved.")

                bcPrint(f"Saved {self._CONFIG_FILEPATH}")

            except Exception as e:
                bcPrint(f"[IO] Can not write {self._CONFIG_FILEPATH!r}: {e}", "error")

        else:
            bcPrint(
                f"Configuration file path is missing {self._CONFIG_PATH}",
                "error",
            )

    def __load(self, current_configuration):
        """Loads persistent JSON configuration with legacy pickle (.cfg) file migration fallback."""
        new_configuration = {}
        new_configuration.update(self._DEFAULT_CONFIGURATION)
        new_configuration.update(current_configuration)

        # Migrate legacy pickle-based configuration (.cfg) if it exists
        legacy_path = os.path.join(self._CONFIG_PATH, "bcry.cfg")
        if os.path.isfile(legacy_path):
            try:
                import pickle

                with open(legacy_path, "rb") as f:
                    legacy_data = pickle.load(f)
                    new_configuration.update(legacy_data)
                    bcPrint("Legacy configuration (.cfg) migrated to JSON format.")
                os.remove(legacy_path)
            except Exception as e:
                bcPrint(f"[IO] Failed to migrate legacy configuration: {e}", "warning")

        if os.path.isfile(self._CONFIG_FILEPATH):
            try:
                with open(self._CONFIG_FILEPATH, encoding="utf-8") as f:
                    new_configuration.update(json.load(f))
                    bcPrint("Configuration file loaded.")
            except Exception as e:
                bcPrint(f"[IO] Can not read {self._CONFIG_FILEPATH!r}: {e}", "error")

        return new_configuration


# Singleton instance shared throughout the modules
Configuration = __Configuration()

# Expose the VERSION constant to resolve import errors in operator submodules
VERSION = "1.3.0"
