# Beam field against buildFE's FE solve (plan step 6)

The finish check of plan step 6: the calculator's beam field (`python/beam_field.py`, 2D,
pulsed) against buildFE's Pogo FE solve of the same beam, measured by one rule
(`python/beam_metrics.py`, ported from buildFE `examples/fe-ref-field/make_field_figures.m`,
commit 9febff0). The tolerances were fixed in `docs/plans/PLAN-2026-11-qt-vtk-migration.md`
(commit fb37a6a) before the comparison was first run.

## Reference

buildFE Task 125, case `(case ID withheld)` (`examples/fe-ref-wedge/beam.json`), returned 2026-10-07:

- 2.25L64-A2 on SA2-N55S, all 64 elements, `steer` law at 45° shear;
- 3-cycle Hann toneburst at 2.25 MHz; 2D plane strain; wedge bonded to the steel (shared nodes);
- steel 7900 kg/m³, 5900/3230 m/s; Rexolite 1049 kg/m³, 2337/1157 m/s.

Its field products are in buildFE's returned bundle and are not copied here:
`transfer/RETURN_fe-ref_wedge_beam_20261007_20261007_103843/results.zip`,
member `fe-ref_wedge_beam/cases/(case ID withheld)/field_products.h5` (58 MB).

## Running

```
pip install h5py matplotlib          # only this check needs h5py
python validation/beam_field/compare_buildfe.py <field_products.h5> [out_dir]
```

It prints the metric table with pass or fail per row, and writes `step6_beam_vs_buildfe.png` and
`.json` to `out_dir` (default `validation/beam_field/out`). The exit status is 0 only if every
row passes. It runs in about 30 s on the dev laptop.

## Steps

1. `fe_reference.py` forms the FE map as buildFE does: the displacement envelope from the
   returned frames, gated to the first arrival at each point, up-going points blanked, 2 mm
   left out under the surface and above the backwall.
2. The port is checked against buildFE: on the FE map, `beam_metrics.beam_axis` gives angle
   45.2708°, exit 44.586 mm and widths 37.886 / 37.669 / 37.453 / 37.020 mm; buildFE's
   `beam_metrics.csv` gives 45.2708°, 44.588 mm and 37.886 / 37.669 / 37.453 / 37.020 mm.
3. The calculator runs the same case: element geometry from the catalogue mapping (plate
   X = calculator X + 10 mm), buildFE's steer delays, on the FE grid.

## Result (2026-11-20): pass

See the step 6 status in the plan for the table and what the case does and does not test.

## Further cases (buildFE Task 204, waiting for the cluster run)

`--case focused_sv55` (elements 1-32, 55 degree shear focused at 25 mm depth) and `--case steer_l60`
(64 elements, 60 degree longitudinal, 3.2 degrees below the first critical angle). Their tolerances
were fixed in the plan (commit 5ded4b8) before the cluster run. Their reference is buildFE bundle
`fe-ref_wedge_laws_20261121`; each case's `field_products.h5` comes back in its `results.zip`.

```
python validation/beam_field/compare_buildfe.py <focused_sv55 field_products.h5> --case focused_sv55
python validation/beam_field/compare_buildfe.py <steer_l60 field_products.h5> --case steer_l60
```

Not staged, because buildFE does not build them yet: a couplant layer (`contact: "couplant"` is
reserved) and 3D (wedges are refused in 3D until the Task 189 follow-on).
