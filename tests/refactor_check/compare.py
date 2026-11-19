import json, os, sys
import numpy as np
from matplotlib.image import imread
a, b = sys.argv[1], sys.argv[2]
names = sorted(set(os.listdir(a)) | set(os.listdir(b)))
same, diff = 0, []
for n in names:
    if n == "table.json":
        continue
    pa, pb = os.path.join(a, n), os.path.join(b, n)
    if not (os.path.exists(pa) and os.path.exists(pb)):
        diff.append((n, "missing in " + ("after" if os.path.exists(pa) else "before")))
        continue
    ia, ib = imread(pa), imread(pb)
    if ia.shape == ib.shape and np.array_equal(ia, ib):
        same += 1
    else:
        frac = np.mean(np.any(ia != ib, axis=-1)) if ia.shape == ib.shape else 1.0
        diff.append((n, f"{frac*100:.2f}% pixels differ"))
print(f"images identical: {same}; different: {len(diff)}")
for d in diff:
    print("  ", *d)
ta, tb = json.load(open(os.path.join(a, "table.json"))), json.load(open(os.path.join(b, "table.json")))
for k in ta:
    if ta[k] != tb.get(k):
        ra, rb = ta[k], tb.get(k, [])
        print(f"table {k}: {len(ra)} -> {len(rb)} rows")
        for x, y in zip(ra, rb):
            if x != y:
                print("    before", x, "\n    after ", y)
        for y in rb[len(ra):]:
            print("    extra after", y)
print("tables identical" if ta == tb else "tables differ")
