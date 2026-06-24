# ------------------------------------------------------------------------------
# Name:        utils/paths.py
# Purpose:     Path manipulation, absolute/relative conversions, and validations
# ------------------------------------------------------------------------------

import os
import re
import sys
import bpy

# Import core dependencies safely to maintain hierarchical structure
from ..core import exceptions
from ..core.logger import bcPrint


def get_absolute_path(file_path):
    """Converts a Blender relative or system path into an absolute file system path."""
    is_relative, file_path = strip_blender_path_prefix(file_path)

    if is_relative:
        blend_file_path = os.path.dirname(bpy.data.filepath)
        file_path = f"{blend_file_path}/{file_path}"

    return os.path.abspath(file_path)


def get_absolute_path_for_rc(file_path):
    """Prepares absolute paths for the Windows-based Resource Compiler.

    Prepends Wine's default drive letter 'z:' on Unix/Linux systems.
    """
    WINE_DEFAULT_DRIVE_LETTER = "z:"

    file_path = get_absolute_path(file_path)

    if sys.platform != "win32":
        file_path = f"{WINE_DEFAULT_DRIVE_LETTER}{file_path}"

    return file_path


def get_relative_path(filepath, start=None):
    """Converts a system path into a relative path starting from the specified root directory."""
    blend_file_directory = os.path.dirname(bpy.data.filepath)
    is_relative_to_blend_file, filepath = strip_blender_path_prefix(filepath)

    if not start:
        if is_relative_to_blend_file:
            return filepath

        # Path is not relative, so construct a path relative to the active blend file
        start = blend_file_directory

        if not start:
            raise exceptions.BlendNotSavedException()

    else:
        # Construct absolute path to ensure accurate relative resolution
        if is_relative_to_blend_file:
            filepath = os.path.normpath(os.path.join(blend_file_directory, filepath))

    return make_relative_path(filepath, start)


def strip_blender_path_prefix(path):
    """Removes Blender's relative path prefix '//' and returns prefix existence boolean."""
    is_relative = False
    BLENDER_RELATIVE_PATH_PREFIX = "//"
    prefix_length = len(BLENDER_RELATIVE_PATH_PREFIX)

    if path.startswith(BLENDER_RELATIVE_PATH_PREFIX):
        path = path[prefix_length:]
        is_relative = True

    return is_relative, path


def make_relative_path(filepath, start):
    """Low-level relative resolver checking for disk/partition mismatches."""
    try:
        relative_path = os.path.relpath(filepath, start)
        return relative_path

    except ValueError:
        raise exceptions.TextureAndBlendDiskMismatchException(start, filepath)


def get_path_with_new_extension(path, extension):
    """Swaps the active extension of a path with a new specified extension."""
    return f"{os.path.splitext(path)[0]}.{extension}"


def strip_extension_from_path(path):
    """Removes the extension from a given system file path."""
    return os.path.splitext(path)[0]


def get_extension_from_path(path):
    """Extracts and returns the extension of a given path."""
    return os.path.splitext(path)[1]


def normalize_path(path):
    """Normalizes path delimiters to standard forward slashes, stripping duplicate bounds."""
    path = path.replace("\\", "/")

    multiple_paths = re.compile("/{2,}")
    path = multiple_paths.sub("/", path)

    if path and path[0] == "/":
        path = path[1:]

    if path and path[-1] == "/":
        path = path[:-1]

    return path


def build_path(*components):
    """Aggregates system path components, normalizing standard separator delimiters."""
    path = "/".join(components)
    path = path.replace("/.", ".")  # Accounts for floating extension dots
    return normalize_path(path)


def get_filename(path):
    """Extracts and returns the raw filename without the extension or path headers."""
    path_normalized = normalize_path(path)
    components = path_normalized.split("/")
    name = os.path.splitext(components[-1])[0]
    return name


def trim_path_to(path, trim_to):
    """Trims directories preceding a specified substring in a normalized path layout."""
    path_normalized = normalize_path(path)
    components = path_normalized.split("/")
    index = 0
    for index, component in enumerate(components):
        if component == trim_to:
            bcPrint("FOUND AN INSTANCE")
            break

    bcPrint(index)
    components_trimmed = components[index:]
    bcPrint(components_trimmed)
    path_trimmed = build_path(*components_trimmed)
    bcPrint(path_trimmed)
    return path_trimmed
