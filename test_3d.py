import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python'))
import numpy as np

from python.probe import Probe, DualProbe, create_probe_assembly
from python.wedge import Wedge
from python.material import Material
from python.delay_law import DelayLaw

def test_regression_2d():
    print("Running Regression Test (2D vs 3D path - Legacy Linear Mode)")
    # Test through the factory to ensure it works
    probe = create_probe_assembly("Linear", num_elements=16, pitch=0.5e-3, freq=5e6)
    wedge = Wedge(angle_degrees=36.0, height_at_element1=10e-3, velocity=2330.0, probe_offset_x=20e-3)
    mat = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)
    
    solver = DelayLaw(probe, wedge, mat)
    
    # Force 2D
    law_2d = solver.calculate_law(50e-3, 0.0, 30e-3, 'longitudinal')
    
    # Temporarily set to act like 3D to force Newton path
    probe.num_elements_y = 2
    law_3d = solver.calculate_law(50e-3, 0.0, 30e-3, 'longitudinal')
    probe.num_elements_y = 1
    
    # We only care about the elements at y=y0 (which are every 2nd element due to flattening)
    delays_2d = law_2d['delays']
    delays_3d = law_3d['delays'][::2]
    print(f"Delays 2D: {delays_2d}")
    print(f"Delays 3D: {delays_3d}")
    
    diff = np.max(np.abs(delays_2d - delays_3d))
    print(f"Max difference between Quartic and Newton solvers: {diff:.2e} seconds")
    assert diff < 1e-9, "Regression test failed: solvers disagree"
    print("Regression test passed.")

def test_symmetry():
    print("Running Symmetry Test (4x4 Matrix directly below)")
    probe = Probe(num_elements=4, pitch=1e-3, frequency=5e6, num_elements_y=4, pitch_y=1e-3)
    # Wedge angle 0 to make it symmetric
    wedge = Wedge(angle_degrees=0.0, height_at_element1=10e-3, velocity=2330.0, probe_offset_x=20e-3)
    mat = Material(velocity_longitudinal=5900.0)
    
    solver = DelayLaw(probe, wedge, mat)
    
    # Target straight down from the center of the array
    elements = wedge.get_transformed_elements(probe)
    c_x, c_y = np.mean(elements[:,0]), np.mean(elements[:,1])
    
    law = solver.calculate_law(c_x, c_y, 50e-3, 'longitudinal')
    delays = law['delays'].reshape(4, 4)
    
    # Delays should be symmetric across horizontal and vertical center
    diff_x = np.max(np.abs(delays - delays[::-1, :]))
    diff_y = np.max(np.abs(delays - delays[:, ::-1]))
    diff_diag = np.max(np.abs(delays - delays.T))
    
    print(f"Symmetry Differences: X={diff_x:.2e}, Y={diff_y:.2e}, Diag={diff_diag:.2e}")
    assert diff_x < 1e-9 and diff_y < 1e-9 and diff_diag < 1e-9, "Symmetry test failed"
    print("Symmetry test passed.")

def test_dual_linear_element_count():
    print("Running Dual Linear Element Count Test")
    probe = create_probe_assembly("Dual Linear", 16, 1e-3, 5e6, array_separation=5e-3)
    assert probe.total_elements == 32, f"Expected 32 elements, got {probe.total_elements}"
    pos = probe.get_element_positions(center_at_origin=True)
    assert pos.shape == (32, 3), f"Expected shape (32, 3), got {pos.shape}"
    # Verify Y coordinates are split properly (+- 2.5mm)
    y_coords = pos[:, 1]
    assert np.allclose(y_coords[:16], -2.5e-3), "Array 1 Y coords wrong"
    assert np.allclose(y_coords[16:], 2.5e-3), "Array 2 Y coords wrong"
    print("Dual Linear Element Count Test passed.")

def test_dual_linear_symmetry():
    print("Running Dual Linear Symmetry Test")
    probe = create_probe_assembly("Dual Linear", 16, 1e-3, 5e6, array_separation=5e-3)
    wedge = Wedge(angle_degrees=0.0, height_at_element1=10e-3, velocity=2330.0, roof_angle_degrees=0.0)
    mat = Material(velocity_longitudinal=5900.0)
    solver = DelayLaw(probe, wedge, mat)
    
    # Target straight down from center
    elements = wedge.get_transformed_elements(probe)
    c_x, c_y = np.mean(elements[:,0]), np.mean(elements[:,1])
    
    law = solver.calculate_law(c_x, c_y, 50e-3, 'longitudinal')
    delays = law['delays']
    
    # Delays for array 1 should match array 2 exactly
    diff = np.max(np.abs(delays[:16] - delays[16:]))
    assert diff < 1e-9, "Dual linear symmetry failed"
    print("Dual Linear Symmetry Test passed.")

def test_roof_angle_effect():
    print("Running Roof Angle Effect Test")
    probe = create_probe_assembly("Dual Linear", 16, 1e-3, 5e6, array_separation=10e-3)
    wedge_flat = Wedge(angle_degrees=0.0, height_at_element1=10e-3, velocity=2330.0, roof_angle_degrees=0.0)
    wedge_roof = Wedge(angle_degrees=0.0, height_at_element1=10e-3, velocity=2330.0, roof_angle_degrees=10.0)
    
    pos_flat = wedge_flat.get_transformed_elements(probe)
    pos_roof = wedge_roof.get_transformed_elements(probe)
    
    # The Z coordinates should differ because of the roof angle tilt
    z_diff = np.max(np.abs(pos_flat[:, 2] - pos_roof[:, 2]))
    assert z_diff > 1e-4, "Roof angle did not affect Z coordinates"
    print("Roof Angle Effect Test passed.")

def test_dual_matrix_defaults():
    print("Running Dual Matrix Defaults Test")
    # A dual matrix with 0 separation should have the exact same element coordinates
    # as a standard matrix (just doubled). But realistically, if we compare the first half...
    mat_probe = create_probe_assembly("Matrix", 4, 1e-3, 5e6, 4, 1e-3)
    dual_probe = create_probe_assembly("Dual Matrix", 4, 1e-3, 5e6, 4, 1e-3, array_separation=0.0)
    
    mat_pos = mat_probe.get_element_positions(center_at_origin=True)
    dual_pos = dual_probe.get_element_positions(center_at_origin=True)
    
    assert np.allclose(mat_pos, dual_pos[:16]), "Dual Matrix with 0 separation failed to match standard matrix"
    print("Dual Matrix Defaults Test passed.")

if __name__ == "__main__":
    test_regression_2d()
    print("-" * 40)
    test_symmetry()
    print("-" * 40)
    test_dual_linear_element_count()
    print("-" * 40)
    test_dual_linear_symmetry()
    print("-" * 40)
    test_roof_angle_effect()
    print("-" * 40)
    test_dual_matrix_defaults()
    print("-" * 40)
    print("All functional tests passed.")
