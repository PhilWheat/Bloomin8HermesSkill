---
name: bloomin8-ble-wake
description: "Wake and control a BLOOMIN8 E-Ink Canvas smart picture frame via BLE wake pulse + HTTP API. Requires bleak library and local Bluetooth access."
version: 2.0.0
author: Hermes Agent + user
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [smart-home, e-ink, hardware, display, ble]
    related_skills: []
---

# BLOOMIN8 E-Ink Canvas — BLE Wake + HTTP

Control a BLOOMIN8 E-Ink Canvas smart picture frame. The device sleeps deeply and **must be woken via BLE** before any HTTP command works. The `/whistle` HTTP endpoint does nothing on sleeping devices — BLE wake is the only way.

## Quick Start

```bash
# 1. Install deps
pip install bleak Pillow requests

# 2. Set device config
export BLOOMIN8_IP="192.168.1.XXX"
export BLOOMIN8_MAC="AA:BB:CC:DD:EE:FF"

# 3. Wake the frame
python3 ~/.hermes/scripts/bloomin8_ble_wake.py

# 4. Upload an image (automated, with scaling)
python3 ~/.hermes/scripts/bloomin8_upload.py /path/to/photo.jpg
```

Or skip the env vars and let `bloomin8_upload.py` read config from an Obsidian vault note (it auto-finds BLOOMIN8 notes by filename).

## The Wake Sequence

The device sleeps deeply. BLE wake is a **pulse** sent over Bluetooth GATT:

1. Connect to the frame via BLE (using its MAC address)
2. Write `0x01` (assert) to characteristic `0000f001-0000-1000-8000-00805f9b34fb`
3. Wait 1ms
4. Write `0x00` (release) to same characteristic
5. Wait ~4 seconds for Wi-Fi/HTTP stack to come up
6. HTTP endpoints are now reachable

**Important:** the frame drops the BLE connection immediately after the wake pulse. The GATT writes complete before disconnect — the disconnect error is **expected behavior**, not a failure.

## BLE Wake Script

Installed as `~/.hermes/scripts/bloomin8_ble_wake.py`. Handles the full BLE wake + HTTP verification:

```bash
export BLOOMIN8_IP="192.168.1.XXX"
export BLOOMIN8_MAC="AA:BB:CC:DD:EE:FF"
python3 ~/.hermes/scripts/bloomin8_ble_wake.py
```

Returns JSON:

```json
{
  "ok": true,
  "wake_dt": 5.23,
  "device": {
    "name": "BLOOMIN8 Canvas",
    "version": "1.0.0",
    "battery": 87,
    "ip": "192.168.1.123",
    "screen": "1200x1600"
  }
}
```

Set `BLOOMIN8_BY_NAME=true` if you prefer using the device name instead of MAC (useful on macOS where bleak uses UUIDs). Set `BLOOMIN8_SETTLE` to override the default 4-second HTTP wait.

### Handling Stale BLE Connections

If you see `BleakError: Client is already connected`, a previous connection wasn't released cleanly. The script handles this automatically by scanning for devices first, then connecting fresh. If it persists, restart Bluetooth:

```bash
# No sudo needed — just toggle the adapter
bluetoothctl power off && sleep 1 && bluetoothctl power on
```

## Image Upload

### Automated Upload (Preferred)

`~/.hermes/scripts/bloomin8_upload.py` handles everything end-to-end:

```bash
# From Obsidian vault (auto-detects IP, MAC, resolution from BLOOMIN8 note)
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg

# Override config via CLI flags (no vault needed)
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg \
  --ip 192.168.1.123 --mac AA:BB:CC:DD:EE:FF \
  --resolution 1200x1600

# Dry run to verify config
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --dry-run

# Upload without triggering display
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --no-show

# Custom gallery
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --gallery my-gallery
```

The script:
1. BLE-wakes the frame
2. Scales the image to fill the display (letterbox, no crop)
3. Uploads via the correct API pattern (see API Pattern below)
4. Triggers display automatically

### Manual Upload

The critical detail: **metadata (`filename`, `gallery`, `show_now`) goes in the URI query string. Only `image` is the multipart file field.** Do NOT use curl — send metadata as form data and the server rejects it.

```python
import requests
from PIL import Image
import io

# Keep frame alive first
requests.get("http://192.168.50.177/whistle", timeout=5)

# Resize image to fit 1200x1600 display
img = Image.open("photo.jpg").convert("RGB")
scale = min(1200 / img.width, 1600 / img.height)
img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
canvas = Image.new("RGB", (1200, 1600), (0, 0, 0))
canvas.paste(img, ((1200 - img.width) // 2, (1600 - img.height) // 2))
buf = io.BytesIO()
img.save(buf, format="JPEG", quality=85)
buf.seek(0)

# Upload — params in URI, image as file field
files = {"image": ("photo.jpg", buf, "image/jpeg")}
params = {"filename": "photo.jpg", "gallery": "default", "show_now": "1"}
r = requests.post("http://192.168.50.177/upload", files=files, params=params, timeout=30)
print(r.json())
```

### Triggering Display

If `show_now=1` doesn't work, explicitly trigger display:

```bash
curl -s -X POST "http://192.168.50.177/show" \
  -H "Content-Type: application/json" \
  -d '{"play_type":0,"image":"/gallerys/default/photo.jpg"}'
```

## Other HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/deviceInfo` | GET | Device status, battery, resolution |
| `/state` | GET | Brief task processor status |
| `/show` | POST | Display image, gallery slideshow, or playlist |
| `/sleep` | POST | Put frame to sleep |
| `/reboot` | POST | Software reboot |
| `/clearScreen` | POST | Clear screen to white |
| `/whistle` | GET | Keep-alive (already-online only) |

## Gallery Management

```bash
# List galleries
curl -s "http://IP/gallery/list"

# Create gallery
curl -s -X PUT "http://IP/gallery" -d '"gallery_name"' \
  -H "Content-Type: text/plain"

# List images in gallery
curl -s "http://IP/gallery?gallery=default"

# Delete gallery
curl -s -X DELETE "http://IP/gallery?name=gallery_name"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| BLE wake fails — "Device not found" | You're using the Wi-Fi MAC. The frame has a separate BLE MAC — check BLOOMIN8 app or HA integration for "Bluetooth MAC" |
| BLE wake fails — "Client already connected" | Stale connection. Run `bluetoothctl power off && sleep 1 && bluetoothctl power on` |
| BLE wake fails — timeout | Frame not on same network, or Bluetooth adapter not accessible |
| Upload returns 500 | Metadata went in form data instead of URI query params. Use `requests.post(url, files=files, params=params)` |
| curl reports "Invalid Content-Length" | The server sends malformed response headers. Use Python `requests` instead of curl |
| `/whistle` doesn't wake frame | It's a keep-alive, not a wake. Must use BLE first |
| Image not showing after upload | Trigger `/show` explicitly, or use `--no-show` then run show command |
| Frame unresponsive after reboot | Wait ~30 seconds after reboot before calling endpoints |

## Pitfalls

1. **BLE MAC ≠ Wi-Fi MAC** — the frame has separate addresses. Wi-Fi MAC won't work for BLE wake.
2. **BLE is local only** — wake pulse must come from a machine with a Bluetooth adapter on the same network.
3. **4-second wait is mandatory** — the Wi-Fi stack takes ~4 seconds to come up after the BLE pulse.
4. **`/whistle` is not a wake** — it only resets the idle timer on already-online devices.
5. **Upload API pattern** — `filename`, `gallery`, `show_now` in URI query params. Only `image` in the multipart body.
6. **Image format** — only JPEG is supported. Convert PNG/BMP/etc. first.
7. **Screen is 1200×1600 portrait** — scale and letterbox images to fill without cropping.
8. **BLE disconnect is expected** — the frame drops the connection right after the wake pulse. Treat disconnect errors as success if the GATT writes completed.

## References

- BLE wake PR: https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component/tree/feature/ble-wake
- Home Assistant integration: https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component
- Official API docs: https://bloomin8.readme.io/llms.txt
- Upload API detail: `references/upload-api-pattern.md`
