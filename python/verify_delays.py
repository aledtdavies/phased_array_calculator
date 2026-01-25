
import numpy as np
import matplotlib.pyplot as plt
from probe import Probe
from wedge import Wedge
from material import Material
from delay_law import DelayLaw

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
    
    # Target 1: Near
    fx1 = x_int + depth_near * np.tan(angle_rad)
    fz1 = depth_near
    
    # Target 2: Far (Plane wave approximation)
    depth_far = 5000e-3 # 5 meters
    fx2 = x_int + depth_far * np.tan(angle_rad)
    fz2 = depth_far
    
    print("Calculating Near Field Law...")
    law1 = solver.calculate_law(fx1, fz1, 'longitudinal')
    delays1_us = law1['delays'] * 1e6
    
    print("Calculating Far Field Law...")
    law2 = solver.calculate_law(fx2, fz2, 'longitudinal')
    delays2_us = law2['delays'] * 1e6
    
    # Plotting
    plt.figure(figsize=(10, 6))
    
    # Plot 1
    plt.subplot(1, 2, 1)
    plt.plot(delays1_us, 'o-', label='Calculated')
    
    # Linear Fit
    x = np.arange(len(delays1_us))
    fit1 = np.poly1d(np.polyfit(x, delays1_us, 1))(x)
    plt.plot(fit1, 'r--', label='Linear Fit')
    plt.title(f'Focused at {depth_near*1000}mm (Near)')
    plt.xlabel('Element')
    plt.ylabel('Delay (us)')
    plt.legend()
    plt.grid(True)
    
    # Plot 2
    plt.subplot(1, 2, 2)
    plt.plot(delays2_us, 'o-', label='Calculated')
    
    # Linear Fit
    fit2 = np.poly1d(np.polyfit(x, delays2_us, 1))(x)
    plt.plot(fit2, 'r--', label='Linear Fit')
    plt.title(f'Focused at {depth_far*1000}mm (Far)')
    plt.xlabel('Element')
    plt.grid(True)
    
    plt.suptitle(f'Delay Laws for {angle_deg} Deg Beam')
    plt.tight_layout()
    plt.savefig('curvature_check.png')
    print("Plot saved to curvature_check.png")

if __name__ == "__main__":
    check_curvature()
