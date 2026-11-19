# Refactor check: same pictures before and after

For refactors that must not change what the views show (plan steps 1–4): render a fixed set of
scenes and GUI tabs at two commits and compare them pixel for pixel, with the data table's text.

```
git worktree add ../pac-base <base commit>
python tests/refactor_check/render_reference.py ../pac-base/python  out/before  <buildFE/catalog>
python tests/refactor_check/render_reference.py python              out/after   <buildFE/catalog>
python tests/refactor_check/compare.py out/before out/after
```

- `render_reference.py` draws seven probe/wedge setups (catalogue wedge, schematic, flat delay line,
  long toe, matrix row-first, dual linear with roof, dual matrix in contact) in both projections,
  single law and Show All, the 3D view and the delay maps. It then drives the Tk GUI through eight
  scan cases: every focus mode, skew, the three Y modes and a dual sub-aperture.
- `compare.py` reports identical images, the share of pixels that differ, and table rows that changed.

The output is not committed: it is a check between two commits on one machine (fonts and
matplotlib versions change pixels), not a stored reference.
