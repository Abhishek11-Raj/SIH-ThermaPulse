with open("frontend/index.html", "r", encoding="utf-8") as f:
    text = f.read()

print("File size:", len(text))
print("card-threat-gauge in text:", "card-threat-gauge" in text)
print("banner-warning-pulse in text:", "banner-warning-pulse" in text)
print("lg:text-[4.25rem] in text:", "lg:text-[4.25rem]" in text)
print("tailwind.cdn.js in text:", "tailwind.cdn.js" in text)
print("cdn.tailwindcss.com in text:", "cdn.tailwindcss.com" in text)
