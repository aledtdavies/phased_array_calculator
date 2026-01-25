import numpy as np
import csv
import os
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

def generate_sector_scan(delay_law_solver, depth, start_angle, end_angle, step):
    """
    Generates laws for a sector scan.
    """
    angles = np.arange(start_angle, end_angle + step, step) # Include end? usually yes
    # Adjust arange to be inclusive if float logic allows, or use linspace if count is known
    # Let's simple iterate
    if step > 0 and angles[-1] < end_angle:
        angles = np.append(angles, end_angle)
    elif step < 0 and angles[-1] > end_angle:
        angles = np.append(angles, end_angle)
        
    results = []
    
    print(f"Generating {len(angles)} laws for Sector Scan...")
    
    # 1. Probe Center Logic
    elements = delay_law_solver.wedge.get_transformed_elements(delay_law_solver.probe)
    center_x = np.mean(elements[:, 0])
    center_z = np.mean(elements[:, 1])
    h_wedge = abs(center_z)
    
    v_wedge = delay_law_solver.wedge.velocity
    v_mat = delay_law_solver.material.velocity_longitudinal # Default L-wave for main.py script
    
    for ang_deg in angles:
        beta_rad = np.radians(ang_deg)
        
        # 2. Snell's Law Back-Trace
        sin_alpha = (v_wedge / v_mat) * np.sin(beta_rad)
        
        if abs(sin_alpha) > 1.0:
            print(f"Angle {ang_deg} Exceeds Critical Angle")
            continue
            
        alpha_rad = np.arcsin(sin_alpha)
        
        # 3. Entry Point
        x_int = center_x + h_wedge * np.tan(alpha_rad)
        
        # 4. Focal Point (Constant Depth)
        # fz = depth
        # fx calculated from x_int
        fz = depth
        fx = x_int + fz * np.tan(beta_rad)
        
        law = delay_law_solver.calculate_law(fx, fz, wave_type='longitudinal')
        
        results.append({
            'angle': ang_deg,
            'focal_point': (fx, fz),
            'delays': law['delays']
        })
        
    return results

def main():
    # 1. Define Setup
    # Example: 5 MHz, 16 Elements, 0.6mm pitch
    probe = Probe(num_elements=16, pitch=0.6e-3, frequency=5e6)
    
    # Material: Steel
    steel = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)
    
    # Wedge: Rexolite, 36 degree angle, 2330 m/s
    # Height @ El.1: Distance from El.1 center to interface. Say 15mm.
    wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0, probe_offset_x=0.0)

    # 2. Initialize Solver
    solver = DelayLaw(probe, wedge, steel)
    
    # Export Element Positions
    solver.export_element_positions("element_positions.csv")
    
    # 3. Run Sector Scan
    # 40 to 70 degrees, 1 degree step, Focus at 50mm depth
    scan_data = generate_sector_scan(solver, depth=50e-3, start_angle=40, end_angle=70, step=1)
    
    # 4. Export to CSV
    output_file = "focal_laws.csv"
    print(f"Exporting to {output_file}...")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        # LawID, Angle, Fx, Fz, Element_1_Delay, Element_2_Delay, ...
        header = ['LawID', 'Angle_Deg', 'Fx_mm', 'Fz_mm'] + [f'El_{i+1}_us' for i in range(probe.num_elements)]
        writer.writerow(header)
        
        for i, res in enumerate(scan_data):
            row = [i+1, res['angle'], res['focal_point'][0]*1000, res['focal_point'][1]*1000]
            # Convert delays to microseconds
            delays_us = res['delays'] * 1e6
            row.extend(delays_us)
            writer.writerow(row)
            
    print("Done.")

if __name__ == "__main__":
    main()
