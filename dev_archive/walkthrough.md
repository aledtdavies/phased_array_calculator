# Walkthrough - Normalized Delay Plots

## Changes
The delay histogram plots significantly improved for comparing delay laws across different angles.

### Normalized Axis
- **Previous Behavior**: The Y-axis (Delay) autoscaled for each individual focal law. This made it difficult to compare the relative magnitude of delays between different steering angles.
- **New Behavior**: The Y-axis is now fixed for a given calculation run. It scales to the **Global Maximum Delay** found across all generated laws.
- **Benefit**: You can now visually see how the required delay magnitude changes as you steer the beam (e.g., larger delays for steeper angles).

### Files Modified
1. **`app.py`**:
   - Calculates `global_max_delay` by inspecting all generated results.
   - Passes this value to the histogram panel.
2. **`plotting.py`**:
   - `DelayHistogramPanel` now accepts `global_max_delay`.
   - Sets the Y-axis limit: `ax.set_ylim(0, global_max_delay * 1.1)`.

## Verification Results
- **Logic**: confirmed by code review.
- **Visuals**: The plots now maintain a stable scale when using the slider to scrub through different angles.
