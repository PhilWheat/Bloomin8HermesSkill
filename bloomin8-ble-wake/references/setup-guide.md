---
name: bloomin8-setup-guide
description: "Complete installation and setup guide for the BLOOMIN8 E-Ink Canvas skill — from zero to first image on the frame."
version: 1.0.0
tags: [setup, getting-started, smart-home, hardware]
---

# BLOOMIN8 E-Ink Canvas — Setup & Usage Guide

Complete guide for installing and using the BLOOMIN8 E-Ink Canvas skill. Covers everything from first install to uploading your first image.

## Overview

The BLOOMIN8 E-Ink Canvas is a smart picture frame with a 6-color E-Ink display (typically 1200×1600 on the 13.3" model). It sleeps deeply to conserve battery — you must **wake it via Bluetooth Low Energy (BLE)** before any HTTP commands work.

This skill provides:
- **BLE wake** — wake the frame from deep sleep
- **Image upload with auto-scaling** — scale images to fit the display perfectly
- **Display control** — single images, galleries, playlists

## What You'll Need

| Item | Details |
|------|---------|
| BLOOMIN8 frame | Powered on, connected to Wi-Fi |
| Computer | Running Hermes Agent, with Bluetooth adapter |
| Python 3.10+ | With `pip` available |
| Obsidian vault | (Optional but recommended) For storing device config |

## Step 1: Install Python Dependencies

```bash
pip install Pillow requests bleak
```

| Package | Purpose |
|---------|---------|
| `Pillow` | Image resizing and letterboxing |
| `requests` | HTTP calls to the frame |
| `bleak` | BLE communication for wake pulse |

## Step 2: Grant Bluetooth Access (Linux)

BLE operations require Bluetooth permissions. On Linux, add your user to the `bluetooth` group instead of using `sudo`:

```bash
sudo usermod -aG bluetooth $USER
```

**Then log out and log back in** (or reboot). After that, BLE works without sudo.

Verify:
```bash
id -Gn | grep bluetooth
# Should output: youruser ... bluetooth ...
```

## Step 3: Create the Obsidian Vault Note

The upload script reads device config from your Obsidian vault. Create a note named `BLOOMIN8 E-Ink Canvas.md` (any location in the vault) with this content:

```markdown
---
created: 2026-06-17
tags:
  - smart-home
  - BLOOMIN8
---

# BLOOMIN8 E-Ink Canvas

## Device Details

- **IP Address:** 192.168.50.177
- **Bluetooth MAC Address:** F4:90:52:22:4F:5A
- Resolution is 1200 wide x 1600 high
```

### Finding Your Values

| Field | Where to Find It |
|-------|-----------------|
| **IP Address** | Your router's admin panel, or the BLOOMIN8 app |
| **BLE MAC** | BLOOMIN8 app → device info, or `bluetoothctl list` (look for a device named "Medium1" or similar) |
| **Resolution** | 1200×1600 for 13.3" models (EL133UF1 display) |

**Important:** The BLE MAC is different from the Wi-Fi MAC. The frame has separate addresses for each radio. Use the **Bluetooth MAC**, not the Wi-Fi one.

### Where Is Your Vault?

The script searches in this order:
1. `$OBSIDIAN_VAULT_PATH` (environment variable)
2. `~/Documents/Obsidian Vault/`
3. `~/.obsidian-vault/`
4. `~/Obsidian/`

Set `OBSIDIAN_VAULT_PATH` to point to your vault if it's elsewhere.

## Step 4: Verify the Script Is Installed

The script lives at `~/.hermes/scripts/bloomin8_upload.py`. Check it's there:

```bash
ls -la ~/.hermes/scripts/bloomin8_upload.py
```

If it's missing, create it from the skill's `scripts/bloomin8_upload.py` file.

## Step 5: Run a Dry Run

Test the config reading without actually uploading:

```bash
python3 ~/.hermes/scripts/bloomin8_upload.py /tmp/test.jpg --dry-run
```

Expected output:
```
Image: /tmp/test.jpg
Filename: test.jpg
Reading config from: /home/username/.obsidian-vault/BLOOMIN8 E-Ink Canvas.md
  IP: 192.168.50.177
  BLE MAC: F4:90:52:22:4F:5A
  Resolution: 1200x1600
Scaled: /tmp/bloomin8_test.jpg (original: /tmp/test.jpg)

Would upload to http://192.168.50.177/upload?filename=test.jpg&gallery=default&show_now=1
```

If this works, your config is correct and you're ready to upload.

## Step 6: Upload Your First Image

```bash
python3 ~/.hermes/scripts/bloomin8_upload.py /path/to/photo.jpg
```

The script will:
1. Read config from your vault
2. BLE-wake the frame
3. Scale the image to fill the display (letterbox, no cropping)
4. Upload via HTTP
5. Trigger display

## CLI Reference

```
python3 bloomin8_upload.py <image> [OPTIONS]

Positional arguments:
  image           Path to the image to upload

Options:
  --gallery NAME  Gallery name (default: default)
  --no-show       Upload but don't trigger display
  --dry-run       Show what would happen without uploading
  --help          Show this help message
```

### Examples

```bash
# Upload and display
python3 ~/.hermes/scripts/bloomin8_upload.py ~/Photos/vacation.jpg

# Upload to a custom gallery
python3 ~/.hermes/scripts/bloomin8_upload.py ~/art/logo.jpg --gallery myart

# Upload without triggering display (add to gallery for later)
python3 ~/.hermes/scripts/bloomin8_upload.py ~/art/logo.jpg --no-show

# Preview config reading
python3 ~/.hermes/scripts/bloomin8_upload.py ~/image.jpg --dry-run
```

## How Image Scaling Works

The script reads the resolution from your vault note (e.g., 1200×1600) and scales every image to fit:

1. **Calculate scale factor** — fits the image within the display while maintaining aspect ratio
2. **Resize** — uses Lanczos resampling (highest quality)
3. **Letterbox** — centers the resized image on a black background matching the display resolution

Result: no cropping, no stretching, no aspect-ratio changes. The image fills the largest dimension possible, with black bars on the others.

## API Pattern (Important)

The BLOOMIN8 upload endpoint uses a **hybrid API pattern**:

- **URI query parameters**: `filename`, `gallery`, `show_now`
- **Multipart form body**: only the `image` file field

```
POST /upload?filename=photo.jpg&gallery=default&show_now=1
Content-Type: multipart/form-data; boundary=...

[image JPEG data]
```

This is why `curl` doesn't work well — sending metadata as form fields instead of URI params causes a 500 error. The script handles this correctly.

## Troubleshooting

### "BLE wake failed"

| Cause | Fix |
|-------|-----|
| Not in `bluetooth` group | `sudo usermod -aG bluetooth $USER`, then log out and back in |
| Wrong MAC address | Check BLOOMIN8 app or `bluetoothctl list` — use the **Bluetooth MAC**, not Wi-Fi MAC |
| Frame out of range | Move within ~3 meters of the Bluetooth adapter |
| Bluetooth adapter missing | Check `bluetoothctl list` shows an adapter |

### "Frame not reachable over HTTP"

- The BLE wake pulse takes ~4 seconds for Wi-Fi to come up (the script waits automatically)
- Check the frame is connected to Wi-Fi and powered on
- Check battery level in the BLOOMIN8 app

### Upload returns 500 error

- Don't use `curl` — use the script or Python `requests`
- Ensure the image is JPEG format
- Let the script handle scaling (don't try to pre-resize manually)

### Image doesn't display after upload

- The script triggers `/show` automatically as a fallback
- If it still doesn't show, check battery level (frame may refuse to display if too low)
- Send a `/whistle` keep-alive before upload to prevent sleep mid-transfer

### "Invalid Content-Length" with curl

This is a client-side issue — the frame's HTTP server sends duplicate `Content-Type` headers and mismatched `Content-Length`. Use Python `requests` instead.

## Pitfalls to Remember

1. **BLE MAC ≠ Wi-Fi MAC** — separate addresses, use the Bluetooth one for wake
2. **BLE is local only** — must use a machine with a Bluetooth adapter on the same network
3. **4-second wait is mandatory** — the Wi-Fi stack takes ~4 seconds after the BLE pulse
4. **`/whistle` is not a wake** — it only keeps an already-online device from sleeping
5. **BLE disconnect is normal** — the frame drops the BLE connection right after the wake pulse
6. **Only JPEG supported** — convert PNG/BMP/etc. before uploading
7. **Image is portrait** — 1200×1600, landscape images need rotation for best fill

## Maintenance

### Restart Bluetooth (if stale connections occur)

```bash
bluetoothctl power off && sleep 1 && bluetoothctl power on
```

No `sudo` needed.

### Keep the Frame Alive

If you're doing multiple uploads in sequence, send periodic `/whistle` calls:

```bash
curl -s "http://192.168.50.177/whistle"
```

Or let the script handle it — it sends one before each upload.

### Frame Goes Offline After Upload

Sometimes the frame processes the upload and goes back to sleep. The next script run will wake it again automatically.
