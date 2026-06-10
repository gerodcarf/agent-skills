import sqlite3, os, json
p = os.path.expanduser("~/OmniRoute/data/storage.sqlite")
con = sqlite3.connect(p)
cols = con.execute("PRAGMA table_info(provider_connections)").fetchall()
col_names = [c[1] for c in cols]
print("Provider columns:", col_names)
prov_select = ",".join(c[1] for c in cols if c[1] in ("id", "name", "provider_type", "provider_id"))
providers = con.execute("SELECT {} FROM provider_connections".format(prov_select)).fetchall()
prov_col_names = [c[1] for c in cols if c[1] in ("id", "name", "provider_type", "provider_id")]
for prow in providers:
    d = dict(zip(prov_col_names, prow))
    print("Provider: {} (type={}, provider_id={})".format(d.get("name"), d.get("provider_type"), d.get("provider_id")))
    # Check if it has credentials
    has_key = con.execute("SELECT COUNT(*) FROM key_value WHERE entity_id = ? AND entity_type = 'provider'".format(), (d.get("id"),)).fetchone()
    if has_key and has_key[0] > 0:
        print("  Has credentials: YES")
    else:
        print("  Has credentials: NO")
    print()
con.close()
