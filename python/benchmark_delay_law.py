import time
import numpy as np
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

def benchmark():
    probe = Probe(num_elements=64, pitch=0.6e-3, frequency=5e6)
    steel = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)
    wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0, probe_offset_x=0.0)

    solver = DelayLaw(probe, wedge, steel)

    start_time = time.time()

    # Simulate a sector scan calculation loop
    for angle in range(30, 71, 1):
        # some dummy focal points
        solver.calculate_law(0.05, 0.0, 0.05)

    end_time = time.time()

    print(f"Time taken: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark()
