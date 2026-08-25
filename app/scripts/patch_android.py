from pathlib import Path

manifest = Path("android/app/src/main/AndroidManifest.xml")
text = manifest.read_text(encoding="utf-8")

if "android:usesCleartextTraffic=" not in text:
    text = text.replace(
        "<application",
        '<application android:usesCleartextTraffic="true"',
        1,
    )

manifest.write_text(text, encoding="utf-8")
print("AndroidManifest patched for HTTP API testing.")
