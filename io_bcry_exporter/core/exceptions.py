# ------------------------------------------------------------------------------
# Name:        core/exceptions.py
# Purpose:     Custom exception definitions used throughout the exporter
# ------------------------------------------------------------------------------


class BCryException(RuntimeError):
    """Base exception class for all custom errors in the BCRY Exporter."""

    def __init__(self, message):
        self._message = message

    def __str__(self):
        return self.what()

    def what(self):
        return self._message


class BlendNotSavedException(BCryException):
    """Raised when an export is attempted on a newly created, unsaved Blend file."""

    def __init__(self):
        super().__init__("The Blend file must be saved before you can export assets.")


class TextureAndBlendDiskMismatchException(BCryException):
    """Raised when textures and the Blend file reside on different disk drives.

    This makes resolving relative paths for materials and .mtl configuration impossible.
    """

    def __init__(self, blend_path, texture_path):
        message = (
            f"\nThe Blend file and its assigned textures must be on the same disk drive.\n"
            f"Relative path generation is impossible across different drives.\n"
            f"Blend file: {blend_path!r}\n"
            f"Texture file: {texture_path!r}"
        )
        super().__init__(message)


class NoRcSelectedException(BCryException):
    """Raised when operations requiring the Resource Compiler (rc.exe) are run without it."""

    def __init__(self):
        message = (
            "\nPlease configure the Resource Compiler path first.\n"
            "Typically located in '[CryEngine_Root]\\Bin64\\rc\\rc.exe' or 'Bin32\\rc\\rc.exe'."
        )
        super().__init__(message)


class NoGameDirectorySelected(BCryException):
    """Raised when the game root folder is required to build relative engine assets."""

    def __init__(self):
        super().__init__("A valid Game Directory must be configured in settings!")


class MarkersNotFound(BCryException):
    """Raised when timeline markers used to delimit an animation export are missing."""

    def __init__(self):
        super().__init__(
            "The configured start or end animation timeline marker was not found!"
        )
