# Beam field against a full-wave FE solve (plan step 6)

The finish check of plan step 6: the calculator's beam field (`python/beam_field.py`, 2D,
pulsed) against a full-wave FE solve (Pogo) of the same beam, both measured by one rule
(`python/beam_metrics.py`, ported from buildFE's beam-map measurement). The tolerances were
fixed in `docs/plans/PLAN-2026-11-qt-vtk-migration.md` (commit bb9a730) before the comparison
was first run.

## Reference

A defect-free beam through the wedge, solved by FE (returned 2026-10-07):

- 2.25L64-A2 on SA2-N55S, all 64 elements, `steer` law at 45° shear;
- 3-cycle Hann toneburst at 2.25 MHz; 2D plane strain; wedge bonded to the steel (shared nodes);
- steel 7900 kg/m³, 5900/3230 m/s; Rexolite 1049 kg/m³, 2337/1157 m/s.

The FE field products (`field_products.h5`, buildFE's field-products format) are not part of
this repository.

## Running

```
pip install h5py matplotlib          # only this check needs h5py
python validation/beam_field/compare_buildfe.py <field_products.h5> [out_dir]
```

It prints the metric table with pass or fail per row, and writes an image and `.json` to
`out_dir` (default `validation/beam_field/out`, not committed). The exit status is 0 only if
every row passes. It runs in about 30 s on the dev laptop.

## Steps

1. `fe_reference.py` forms the FE map by buildFE's rule: the displacement envelope from the
   returned frames, gated to the first arrival at each point, up-going points blanked, 2 mm
   left out under the surface and above the backwall.
2. The port is checked against buildFE: on the FE map, `beam_metrics.beam_axis` gives angle
   45.2708°, exit 44.586 mm and widths 37.886 / 37.669 / 37.453 / 37.020 mm; buildFE's own
   measurement gives 45.2708°, 44.588 mm and 37.886 / 37.669 / 37.453 / 37.020 mm.
3. The calculator runs the same case: element geometry from the catalogue mapping (plate
   X = calculator X + 10 mm), the FE model's steer delays, on the FE grid.

## Result (2026-11-20): pass

See the step 6 status in the plan for the table and what the case does and does not test.

## Further cases (waiting for their FE solve)

`--case focused_sv55` (elements 1-32, 55 degree shear focused at 25 mm depth) and `--case steer_l60`
(64 elements, 60 degree longitudinal, 3.2 degrees below the first critical angle). Their tolerances
were fixed in the plan (commit 183ed1f) before the solve.

```
python validation/beam_field/compare_buildfe.py <focused_sv55 field_products.h5> --case focused_sv55
python validation/beam_field/compare_buildfe.py <steer_l60 field_products.h5> --case steer_l60
```

Not staged yet: a couplant layer and 3D with a wedge (the FE builder does not build them yet).
