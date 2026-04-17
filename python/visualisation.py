import numpy as np
import matplotlib.pyplot as plt
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

def plot_setup(solver, focal_point_x, focal_point_z, filename="visual_check.png"):
    """
    Plots the Probe, Wedge, Ray Paths, and Focal Point.
    """
    # 1. Calculate Rays
    law = solver.calculate_law(focal_point_x, focal_point_z)
    
    elements = solver.wedge.get_transformed_elements(solver.probe)
    interfaces = law['interface_points']
    target = law['focal_point']
    
    plt.figure(figsize=(10, 6))
    
    # 2. Draw Geometry
    # Wedge Profile (Approximate visualization)
    # 0,0 is interface below reference.
    # Wedge is typically a block.
    # Let's just draw the Interface Line (z=0)
    plt.axhline(0, color='k', linestyle='-', linewidth=2, label='Interface')
    
    # Draw Component Area (>0)
    plt.fill_between([-0.1, 0.1], 0, 0.1, color='gray', alpha=0.1, label='Component')
    
    # Draw Wedge Area (<0)
    # This is tricky without full wedge dimensions, but we know the angle.
    # We'll just infer a visual region
    plt.fill_between([-0.1, 0.1], -0.05, 0, color='cyan', alpha=0.1, label='Wedge')

    # 3. Draw Elements
    plt.plot(elements[:, 0], elements[:, 1], 'rs', markersize=5, label='Elements')
    
    # 4. Draw Rays
    # Element -> Interface -> Target
    for i in range(solver.probe.num_elements):
        p_el = elements[i]
        p_int = interfaces[i]
        
        # Segment 1: Wedge
        plt.plot([p_el[0], p_int[0]], [p_el[1], p_int[1]], 'b-', alpha=0.3)
        
        # Segment 2: Component
        plt.plot([p_int[0], target[0]], [p_int[1], target[1]], 'g-', alpha=0.3)
        
    # 5. Draw Target
    plt.plot(target[0], target[1], 'rx', markersize=10, markeredgewidth=2, label='Focal Point')
    
    # Formatting
    plt.gca().invert_yaxis()
    
    plt.xlabel('X Position (m)')
    plt.ylabel('Z Depth (m)')
    plt.title(f'Phased Array Ray Tracing\nTarget: ({focal_point_x*1000:.1f}, {focal_point_z*1000:.1f}) mm')
    plt.legend()
    plt.grid(True)
    plt.axis('equal')
    
    plt.savefig(filename, dpi=100)
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
    
    center = wedge.get_probe_center(probe)
    center_x = center[0]
    center_z = center[1]
    h_wedge = abs(center_z)
    
    x_int = center_x + h_wedge * np.tan(alpha_rad)
    
    fz = depth # Constant depth
    fx = x_int + fz * np.tan(beta_rad)
    
    plot_setup(solver, fx, fz, "visual_check.png")

if __name__ == "__main__":
    main()
