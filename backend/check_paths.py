import json
with open("openapi.json") as f:
    d = json.load(f)
paths = d["paths"]
keys = list(paths.keys())
print("Number of paths:", len(keys))
for k in keys:
    print(k)