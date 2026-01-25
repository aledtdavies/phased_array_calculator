import PyInstaller.__main__
import os
import shutil

# Define the main script and output directory
main_script = os.path.join("python", "app.py")
output_name = "PhasedArrayCalculator"
output_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "phased_array_calculator_executable"))

# Clean up previous build if exists
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)

# PyInstaller arguments
args = [
    main_script,
    f"--name={output_name}",
    "--onedir",  # Create a directory with executable and dependencies
    "--windowed",  # No console window
    "--clean",
    f"--distpath={output_dir}",
    "--workpath=build",
    "--specpath=.",
    "--add-data=UserManual.html;.", # Include UserManual.html in the root of the output
    "--add-data=python/*.csv;python", # Include CSV files if they are needed by app.py
    "--add-data=python/*.json;python", # Include JSON files if they are needed by app.py
]

# Run PyInstaller
print(f"Building executable in {output_dir}...")
PyInstaller.__main__.run(args)

print("Build complete.")
print(f"Executable is located at: {os.path.join(output_dir, output_name, output_name + '.exe')}")
