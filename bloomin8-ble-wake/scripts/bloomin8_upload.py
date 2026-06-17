#!/usr/bin/env python3
"""
Upload an image to a BLOOMIN8 E-Ink Canvas frame.

Steps:
  1. Read device config from Obsidian vault (IP, BLE MAC, resolution)
  2. BLE-wake the frame
  3. Keep-alive with /whistle
  4. Scale the image to fit the display (letterbox to fill without cropping)
  5. Upload via /upload (filename/gallery/show_now in URI query, image as multipart file)
  6. Trigger display if needed

Usage:
  python3 ~/.hermes/scripts/bloomin8_upload.py <image_path>
  python3 ~/.hermes/scripts/bloomin8_upload.py <image_path> --gallery <name>
  python3 ~/.hermes/scripts/bloomin8_upload.py <image_path> --no-show

Dependencies:
  pip install bleak Pillow requests
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Obsidian vault config reader
# ---------------------------------------------------------------------------

def resolve_vault_path() -> str:
    """Resolve the Obsidian vault path from env or known locations."""
    from_env = os.environ.get("OBSIDIAN_VAULT_PATH")
    if from_env and Path(from_env).is_dir():
        return from_env

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Documents", "Obsidian Vault"),
        os.path.join(home, ".obsidian-vault"),
        os.path.join(home, "Obsidian"),
    ]
    for c in candidates:
        if Path(c).is_dir():
            return c

    print("ERROR: Could not find Obsidian vault. Set OBSIDIAN_VAULT_PATH or place vault at ~/Documents/Obsidian Vault or ~/.obsidian-vault", file=sys.stderr)
    sys.exit(1)


def read_bloomin8_config() -> dict:
    """Read BLOOMIN8 config from the Obsidian vault."""
    vault = resolve_vault_path()

    # Search for the BLOOMIN8 note
    target_name = None
    for root, dirs, files in os.walk(vault):
        for f in files:
            if "bloomin8" in f.lower() and f.endswith(".md"):
                target_name = os.path.join(root, f)
                break
        if target_name:
            break

    if not target_name:
        print(f"ERROR: Could not find BLOOMIN8 note in vault at {vault}", file=sys.stderr)
        print(f"  Search directory: {vault}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading config from: {target_name}")
    with open(target_name, encoding="utf-8") as f:
        content = f.read()

    config = {}

    # Extract IP address — handles "**IP Address:**" (colon inside bold) and "IP Address:" (normal)
    m = re.search(r"(?:\*\*IP Address:\*\*|IP Address:)\s*(\d+\.\d+\.\d+\.\d+)", content)
    if m:
        config["ip"] = m.group(1)
        print(f"  IP: {config['ip']}")
    else:
        print("ERROR: Could not find IP Address in BLOOMIN8 note", file=sys.stderr)
        sys.exit(1)

    # Extract BLE MAC — try several formats the vault might use
    ble_patterns = [
        r"(?:\*\*)?(?:BLE )?(?:Bluetooth )?MAC Address(?:\*\*)?\s*:\s*([A-Fa-f0-9:]+)",
        r"(?:\*\*)?MAC Address(?:\*\*)?\s*:\s*([A-Fa-f0-9:]+)",
    ]
    config["ble_mac"] = None
    for pat in ble_patterns:
        m = re.search(pat, content)
        if m:
            config["ble_mac"] = m.group(1)
            print(f"  BLE MAC: {config['ble_mac']}")
            break
    if not config["ble_mac"]:
        print("ERROR: Could not find MAC address in BLOOMIN8 note", file=sys.stderr)
        sys.exit(1)

    # Extract resolution — match "1200 wide x 1600 high" from Device Details section
    # Use a more specific pattern to avoid matching code blocks like "0x01"
    m = re.search(r"Resolution is (\d+)\s+wide\s+x\s+(\d+)\s+high", content, re.IGNORECASE)
    if m:
        config["width"] = int(m.group(1))
        config["height"] = int(m.group(2))
        print(f"  Resolution: {config['width']}x{config['height']}")
    else:
        print("WARNING: Could not find resolution in BLOOMIN8 note. Defaulting to 1200x1600.")
        config["width"] = 1200
        config["height"] = 1600

    return config


# ---------------------------------------------------------------------------
# BLE wake
# ---------------------------------------------------------------------------

async def ble_wake(mac: str) -> bool:
    """Send BLE wake pulse to the BLOOMIN8 frame."""
    try:
        from bleak import BleakClient, BleakError
    except ImportError:
        print("ERROR: bleak not installed. Run: pip install bleak", file=sys.stderr)
        sys.exit(1)

    WAKE_CHAR = "0000f001-0000-1000-8000-00805f9b34fb"

    print("BLE wake: scanning and connecting...")
    try:
        async with BleakClient(mac) as client:
            await asyncio.wait_for(client.connect(), timeout=15)
            print("  Connected via BLE")

            print("  Sending wake pulse (assert)...")
            await client.write_gatt_char(WAKE_CHAR, b"\x01", response=False)
            await asyncio.sleep(0.001)

            print("  Releasing wake pulse...")
            await client.write_gatt_char(WAKE_CHAR, b"\x00", response=False)
            print("  Wake pulse sent.")

            return True
    except BleakError as e:
        print(f"BLE error: {e}", file=sys.stderr)
        return False
    except asyncio.TimeoutError:
        print("BLE connection timed out.", file=sys.stderr)
        return False
    except (EOFError, OSError) as e:
        # Disconnect error after successful wake is expected — the device closes the BLE connection
        print(f"  (BLE disconnect error after wake is expected: {e})")
        return True
    except Exception as e:
        print(f"Unexpected BLE error: {e}", file=sys.stderr)
        return False


async def wait_for_http(ip: str, timeout: float = 15) -> bool:
    """Wait until the frame's HTTP API responds."""
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://{ip}/deviceInfo", timeout=3) as resp:
                resp.read()
                print("  Frame HTTP is online.")
                return True
        except Exception:
            await asyncio.sleep(0.5)
    print("ERROR: Frame did not respond over HTTP after BLE wake.", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Image scaling
# ---------------------------------------------------------------------------

def scale_image(input_path: str, target_w: int, target_h: int, output_path: str) -> str:
    """
    Scale an image to fit within target_w x target_h.

    The image is scaled to fill the largest dimension possible while
    maintaining aspect ratio. The result may have letterbox/pillarbox
    bars (the image is centered in a black background matching the
    target dimensions). This ensures no part of the image is cropped
    and no distortion occurs.
    """
    img = Image.open(input_path)

    # Ensure RGB (frame only supports JPEG in RGB mode)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Calculate scaling factor to fit within target without cropping
    scale = min(target_w / img.width, target_h / img.height)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Create target-size canvas and paste centered
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(img_resized, (offset_x, offset_y))

    canvas.save(output_path, "JPEG", quality=85)
    return output_path


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_image(ip: str, image_path: str, filename: str, gallery: str = "default", show_now: bool = True) -> dict:
    """
    Upload an image to the BLOOMIN8 frame.

    API pattern (matching the C# CanvasApiClient):
    - filename, gallery, show_now go in URI query parameters
    - image is the only multipart file field
    """
    # Keep frame alive
    try:
        requests.get(f"http://{ip}/whistle", timeout=5)
    except Exception as e:
        print(f"WARNING: /whistle failed: {e}", file=sys.stderr)

    with open(image_path, "rb") as f:
        image_data = f.read()

    files = {"image": (filename, image_data, "image/jpeg")}
    params = {
        "filename": filename,
        "gallery": gallery,
        "show_now": "1" if show_now else "0",
    }

    print(f"Uploading {image_path} -> http://{ip}/upload (gallery={gallery})")
    r = requests.post(
        f"http://{ip}/upload",
        files=files,
        params=params,
        timeout=30,
    )

    if r.status_code == 200:
        result = r.json()
        print(f"  Upload OK: {result}")
        return result

    print(f"  Upload FAILED: HTTP {r.status_code} — {r.text[:200]}", file=sys.stderr)
    return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}


# ---------------------------------------------------------------------------
# Show image (if show_now didn't work)
# ---------------------------------------------------------------------------

def show_image(ip: str, image_path: str) -> bool:
    """Explicitly tell the frame to display an image."""
    data = {"play_type": 0, "image": image_path}
    try:
        r = requests.post(
            f"http://{ip}/show",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            print(f"  Display triggered: {image_path}")
            return True
        else:
            print(f"  /show returned HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  /show error: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload an image to a BLOOMIN8 E-Ink Canvas frame.",
    )
    parser.add_argument("image", help="Path to the image file to upload")
    parser.add_argument("--gallery", default="default", help="Gallery name (default: default)")
    parser.add_argument("--no-show", action="store_true", help="Upload but don't trigger display")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without uploading")
    args = parser.parse_args()

    # Resolve image path
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    filename = image_path.name
    print(f"Image: {image_path}")
    print(f"Filename: {filename}")

    # Read config from Obsidian vault
    config = read_bloomin8_config()
    ip = config["ip"]
    ble_mac = config["ble_mac"]
    target_w = config["width"]
    target_h = config["height"]

    # Scale image
    import tempfile
    scaled_path = os.path.join(tempfile.gettempdir(), f"bloomin8_{filename}")
    scaled_path = scale_image(str(image_path), target_w, target_h, scaled_path)
    print(f"Scaled: {scaled_path} (original: {image_path})")

    if args.dry_run:
        print(f"\nWould upload to http://{ip}/upload?filename={filename}&gallery={args.gallery}&show_now={'1' if not args.no_show else '0'}")
        sys.exit(0)

    # Wake the frame
    print(f"\nWaking frame via BLE ({ble_mac})...")
    woke = asyncio.run(ble_wake(ble_mac))
    if not woke:
        print("ERROR: BLE wake failed. Is the frame in range and powered on?", file=sys.stderr)
        sys.exit(1)

    # Wait for HTTP
    print("Waiting for HTTP API...")
    http_ok = asyncio.run(wait_for_http(ip))
    if not http_ok:
        print("ERROR: Frame not reachable over HTTP after BLE wake.", file=sys.stderr)
        sys.exit(1)

    # Upload
    result = upload_image(ip, scaled_path, filename, args.gallery, show_now=not args.no_show)

    if not result.get("path") and not result.get("success"):
        # Try explicit show
        print("\nTrying explicit /show...")
        show_image(ip, f"/gallerys/{args.gallery}/{filename}")

    print("\nDone.")


if __name__ == "__main__":
    main()
