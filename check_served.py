import urllib.request

res = urllib.request.urlopen('http://127.0.0.1:8000/dashboard/')
content = res.read().decode('utf-8')
print("Status:", res.status)
print("Content length:", len(content))
with open("downloaded_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
print("Saved downloaded_dashboard.html")
