from pathlib import Path
p = Path("c:/GamC/.vscode/SIH/kado_agent/kado_agent/backend/app/main.py").resolve()
print("file:", p)
print("parent:", p.parent)
print("parent.parent:", p.parent.parent)
print("parent.parent.parent:", p.parent.parent.parent)
print("frontend_dir:", p.parent.parent.parent / "frontend")
print("exists:", (p.parent.parent.parent / "frontend").exists())
print("is_dir:", (p.parent.parent.parent / "frontend").is_dir())
if (p.parent.parent.parent / "frontend").exists():
    for f in (p.parent.parent.parent / "frontend").iterdir():
        print("  -", f.name, f.stat().st_size)
