import json
with open("openapi.json") as f:
    d = json.load(f)
paths = d["paths"]
# Check specific endpoints
for p in ["/", "/openapi.json"]:
    print(f"{p}: {'FOUND' if p in paths else 'NOT FOUND'}")
# Check /api/v1/health
print(f"/api/v1/health: {'FOUND' if '/api/v1/health' in paths else 'NOT FOUND'}")
# Check /api/v1/system/info
print(f"/api/v1/system/info: {'FOUND' if '/api/v1/system/info' in paths else 'NOT FOUND'}")
# List all route names with alert
print("\nAll routes containing 'alert' or 'Alert':")
for k, v in paths.items():
    kl = k.lower()
    if 'alert' in kl:
        print(f"  {k}")