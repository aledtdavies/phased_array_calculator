"""
Standalone visual check: renders one focal-law scene to a PNG using the
same scene-drawing code as the GUI (plotting.draw_projection).
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw
from scene import draw_projection


def plot_setup(solver, focal_point_x, focal_point_z, filename="visual_check.png",
               wave_type="longitudinal", component_thickness_mm=0.0):
    """
    Plots the Probe, Wedge, Ray Paths, and Focal Point for a single law.
    """
    law = solver.calculate_law(focal_point_x, 0.0, focal_point_z,
                               wave_type=wave_type)

    def get_law(idx):
        return law['interface_points'] * 1000, law['focal_point'] * 1000

    fig = Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    draw_projection(ax, solver, get_law, [0], dim_idx=0, wave_type=wave_type,
                    show_all=False, component_thickness_mm=component_thickness_mm)
    ax.set_title(f"Phased Array Ray Tracing\n"
                 f"Target: ({focal_point_x*1000:.1f}, {focal_point_z*1000:.1f}) mm")

    fig.tight_layout()
    fig.savefig(filename, dpi=100)
    print(f"Plot saved to {filename}")


def main():
    # Setup similar to main.py
    probe = Probe(num_elements=16, pitch=0.6e-3, frequency=5e6)
    steel = Material(velocity_longitudinal=5900.0)
    wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0, probe_offset_x=0.0)
    solver = DelayLaw(probe, wedge, steel)

    # Plot a specific law (e.g. 55 degrees, 50mm depth)
    angle_deg = 55
    depth = 50e-3

    # Logic: Refracted Angle = 55.
    v_wedge = wedge.velocity
    v_mat = steel.velocity_longitudinal

    beta_rad = np.radians(angle_deg)
    sin_alpha = (v_wedge / v_mat) * np.sin(beta_rad)
    alpha_rad = np.arcsin(sin_alpha)

    elements = wedge.get_transformed_elements(probe)
    center_x = np.mean(elements[:, 0])
    center_z = np.mean(elements[:, 2])
    h_wedge = abs(center_z)

    x_int = center_x + h_wedge * np.tan(alpha_rad)

    fz = depth  # Constant depth
    fx = x_int + fz * np.tan(beta_rad)

    plot_setup(solver, fx, fz, "visual_check.png")


if __name__ == "__main__":
    main()
