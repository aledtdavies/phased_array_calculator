
import numpy as np
import matplotlib.pyplot as plt
from probe import Probe
from wedge import Wedge
from material import Material
from delay_law import DelayLaw

def calculate_target_delays(solver, x_int, depth, angle_rad, field_name):
    fx = x_int + depth * np.tan(angle_rad)
    fz = depth
    print(f"Calculating {field_name} Law...")
    law = solver.calculate_law(fx, fz, 'longitudinal')
    return law['delays'] * 1e6

def plot_delay_curve(delays_us, depth, label, subplot_idx, show_ylabel=False):
    plt.subplot(1, 2, subplot_idx)
    plt.plot(delays_us, 'o-', label='Calculated')
    x = np.arange(len(delays_us))
    fit = np.poly1d(np.polyfit(x, delays_us, 1))(x)
    plt.plot(fit, 'r--', label='Linear Fit')
    plt.title(f'Focused at {depth*1000}mm ({label})')
    plt.xlabel('Element')
    if show_ylabel:
        plt.ylabel('Delay (us)')
        plt.legend()
    plt.grid(True)

def check_curvature():
    # Setup
    probe = Probe(num_elements=32, pitch=0.5e-3, frequency=5e6) # 32 Elements for clearer curve
    wedge = Wedge(angle_degrees=36.0, height_at_element1=10e-3, velocity=2330.0, probe_offset_x=20e-3)
    mat = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)
    
    solver = DelayLaw(probe, wedge, mat)
    
    # Configuration
    angle_deg = 45.0
    angle_rad = np.radians(angle_deg)
    
    # 1. Near Field Focus (Strong Curvature Expected)
    depth_near = 15e-3 # 15mm
    
    # Calculate target x roughly (ignoring exact interface for simple target gen)
    # We just need physical points.
    # Let's use the solver's own method to find a valid beam path for the Center element
    elements = wedge.get_transformed_elements(probe)
    center_el_idx = probe.num_elements // 2
    p_center = elements[center_el_idx]
    
    # Approximate ray to finding a valid target
    # Snell's law at interface
    v1 = wedge.velocity
    v2 = mat.velocity_longitudinal
    sin_a = (v1/v2)*np.sin(angle_rad)
    alpha = np.arcsin(sin_a)
    
    # Distance to interface (vertical)
    dist_to_int = abs(p_center[1])
    x_int = p_center[0] + dist_to_int * np.tan(alpha)
    
    # Target 2: Far (Plane wave approximation)
    depth_far = 5000e-3 # 5 meters

    delays1_us = calculate_target_delays(solver, x_int, depth_near, angle_rad, "Near Field")
    delays2_us = calculate_target_delays(solver, x_int, depth_far, angle_rad, "Far Field")

    # Plotting
    plt.figure(figsize=(10, 6))

    plot_delay_curve(delays1_us, depth_near, 'Near', 1, show_ylabel=True)
    plot_delay_curve(delays2_us, depth_far, 'Far', 2)
    
    plt.suptitle(f'Delay Laws for {angle_deg} Deg Beam')
    plt.tight_layout()
    plt.savefig('curvature_check.png')
    print("Plot saved to curvature_check.png")

if __name__ == "__main__":
    check_curvature()
