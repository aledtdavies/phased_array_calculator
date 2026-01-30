# Phased Array Focal Law Calculator

A Python-based tool for calculating focal laws (delay logic) for phased array ultrasonic testing. Supports linear probes, wedges, and planar interfaces.

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

## 2. Documentation

For a detailed explanation of the physics, mathematics (Fermat's Principle), and step-by-step usage guide, please open the **User Manual**:

[**Open UserManual.html**](UserManual.html)

*(This HTML manual is provided to ensure all mathematical formulas render correctly in your browser).*


## 3. Building the Executable

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

## 4. Directory Structure
```
phased_array_calculator/
├── python/               # Python source code + GUI
├── matlab/               # Equivalent MATLAB source code + GUI
├── UserManual.html       # Combined Theory & Instructions
├── build_executable.py   # Script to build the standalone executable
└── README.md             # This file
```
