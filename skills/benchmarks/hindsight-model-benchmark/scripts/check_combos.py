import sqlite3, os, json
p = os.path.expanduser("~/OmniRoute/data/storage.sqlite")
con = sqlite3.connect(p)
cols = con.execute("PRAGMA table_info(combos)").fetchall()
col_names = [c[1] for c in cols]
print("Combo columns:", col_names)
col_select = ",".join(c[1] for c in cols)
combos = con.execute("SELECT {} FROM combos".format(col_select)).fetchall()
for row in combos:
    d = dict(zip(col_names, row))
    print("Combo: {}".format(d.get("name")))
    for k, v in d.items():
        if k != "name" and v is not None and len(str(v)) > 0:
            print("  {}: {}".format(k, str(v)[:200]))
    print()
con.close()
