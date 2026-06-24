# BCRY Exporter for Blender

BCRY Exporter is a Blender add-on designed to export geometries, skeletal armatures, physics proxies, and animations from Blender directly to CryEngine (and Lumberyard) via the COLLADA (DAE) format and the Resource Compiler (RC).

## Key Features
* **Geometry Export**: Supports CGF (static) and CGA (animated) mesh compilation.
* **Skeletal Rigging**: Resolves standard CHR (character) and SKIN (skinned render mesh) formats.
* **Animations**: Timeline, value, and marker-based ranges mapped to I_CAF and ANM tracks.
* **Material & Texture Pipeline**: Automated `.mtl` material file generation and asynchronous DDS texture conversion.
* **Diagnostics**: Built-in helpers to detect degenerate faces, multi-face lines, and unassigned/weightless vertices.

## Installation
1. Download the repository folder as a `.zip` archive.
2. In Blender, go to `Edit > Preferences > Add-ons > Install...`.
3. Select the downloaded `.zip` file and enable **Import-Export: BCRY Exporter**.

## Configuration
Before exporting, configure the paths in the Sidebar panel (**BCry Exporter** tab):
1. **Find RC**: Locate your CryEngine Resource Compiler (`rc.exe`).
2. **Select Game Directory**: Define your target project's asset root directory (needed to build relative texture paths).

## License
This project is licensed under the GPLv2+ License.
