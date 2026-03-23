#!/usr/bin/env python3
"""Direct string replacement for the French badge line."""

filepath = "src/pages/HomePage.tsx"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# The problematic line currently reads (after previous fix):
#   badge: 'Moteur fiscal IA pour l'Autriche',
# We need to change it to:
#   badge: `Moteur fiscal IA pour l'Autriche`,

old = "badge: 'Moteur fiscal IA pour l'Autriche',"
new = "badge: `Moteur fiscal IA pour l'Autriche`,"

if old in content:
    content = content.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed French badge line")
else:
    print("Pattern not found, checking what's there...")
    idx = content.find("Moteur fiscal")
    if idx >= 0:
        print(repr(content[idx-15:idx+60]))
    else:
        print("'Moteur fiscal' not found at all")
