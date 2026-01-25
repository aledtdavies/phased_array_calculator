# Phased Array Focal Law Calculator

A Python and MATLAB-based tool for calculating focal laws (delay logic) for ultrasonic phased array testing. Supports linear probes, wedges, and planar interfaces.

## 1. Quick Start (Python)

**Requirements**: Python 3.x, `numpy`, `matplotlib`, `tkinter`.

1.  **Launch GUI**:
    ```bash
    python python/app.py
    ```
2.  **Configure**:
    - Set Probe parameters (Elements, Pitch).
    - Set Wedge geometry and velocity.
    - Choose Focus Mode (Depth, Vertical, Sound Path).
3.  **Run**: Click "Calculate". Visualize in the "Ray Tracing" tab.
4.  **Export**: Save results to CSV or save the configuration (`.json`).

## 2. Quick Start (MATLAB)

1.  Open MATLAB.
2.  Navigate to `matlab/` folder.
3.  Run `PhasedArrayGUI` in the command window.

## 3. Documentation

For a detailed explanation of the physics, mathematics (Fermat's Principle), and step-by-step usage guide, please open the **User Manual**:

[**Open UserManual.html**](UserManual.html)

*(This HTML manual is provided to ensure all mathematical formulas render correctly in your browser).*


## 4. Building the Executable

This project includes a script to build a standalone executable folder using PyInstaller.

1.  **Install PyInstaller**:
    ```bash
    pip install pyinstaller
    ```
2.  **Run the Build Script**:
    ```bash
    python build_executable.py
    ```
3.  **Locate the Output**:
    The executable and its dependencies will be created in a folder named `phased_array_calculator_executable` located next to the project directory.

## 5. Directory Structure
```
phased_array_calculator/
├── python/               # Python source code + GUI
├── matlab/               # Equivalent MATLAB source code + GUI
├── UserManual.html       # Combined Theory & Instructions
├── build_executable.py   # Script to build the standalone executable
└── README.md             # This file
```
