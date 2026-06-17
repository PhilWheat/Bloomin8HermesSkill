#!/usr/bin/env python3
"""BLE wake + HTTP check for BLOOMIN8 E-Ink Canvas.

Usage: set BLOOMIN8_IP and BLOOMIN8_MAC env vars, then run:
  python3 bloomin8_ble_wake.py

Returns JSON: {"ok": true/false, "device": {...}, ...}

PITFALL: The frame drops the BLE connection immediately after the wake
pulse, causing an EOFError on disconnect. This is EXPECTED behavior —
catch it and treat as success if GATT writes completed.
"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request


async def ble_wake(mac_or_name: str, host: str, by_name: bool = False) -> dict:
    from bleak import BleakScanner, BleakClient

    # Step 1: Discover device
    if by_name:
        devices = await BleakScanner.discover(timeout=6)
        chosen = None
        for d in devices:
            if d.name and d.name == mac_or_name:
                chosen = d
                break
        if chosen is None:
            for d in devices:
                if d.name and mac_or_name.lower() in d.name.lower():
                    chosen = d
                    break
        if chosen is None:
            return {"ok": False, "error": f"no device found matching '{mac_or_name}'"}
        mac_or_name = chosen.address

    # Step 2-5: Connect + send BLE wake pulse (assert 0x01, release 0x00)
    WAKE_CHAR = "0000f001-0000-1000-8000-00805f9b34fb"
    t0 = time.monotonic()
    woke = False
    try:
        async with BleakClient(mac_or_name) as client:
            await asyncio.wait_for(client.connect(), timeout=15)
            await client.write_gatt_char(WAKE_CHAR, b"\x01", response=False)
            await asyncio.sleep(0.001)
            await client.write_gatt_char(WAKE_CHAR, b"\x00", response=False)
            woke = True
    except BleakError as e:
        return {"ok": False, "error": f"BLE error: {e}", "dt": time.monotonic() - t0}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "BLE connection timed out", "dt": time.monotonic() - t0}
    except (EOFError, OSError):
        # Frame drops BLE connection immediately after wake pulse — expected
        if not woke:
            return {"ok": False, "error": "BLE connect failed", "dt": time.monotonic() - t0}
        # woke is True, disconnect error is expected — continue

    # Step 6: Wait for Wi-Fi/HTTP stack to come up (~4 seconds)
    settle = min(4.0, float(os.environ.get("BLOOMIN8_SETTLE", "4")))
    await asyncio.sleep(settle)

    # Step 7: Check HTTP is reachable
    result = {"ok": True, "wake_dt": time.monotonic() - t0}
    url = f"http://{host}/deviceInfo"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            result["device"] = {
                "name": data.get("name"),
                "version": data.get("version"),
                "battery": data.get("battery"),
                "ip": data.get("sta_ip"),
                "screen": f"{data.get('width')}x{data.get('height')}",
            }
    except Exception as e:
        result["ok"] = False
        result["http_error"] = str(e)

    return result


async def main():
    host = os.environ.get("BLOOMIN8_IP", "")
    mac = os.environ.get("BLOOMIN8_MAC", "")
    by_name = os.environ.get("BLOOMIN8_BY_NAME", "false") == "true"

    if not host or not mac:
        print(json.dumps({"ok": False, "error": "set BLOOMIN8_IP and BLOOMIN8_MAC env vars"}))
        sys.exit(1)

    result = await ble_wake(mac, host, by_name)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
