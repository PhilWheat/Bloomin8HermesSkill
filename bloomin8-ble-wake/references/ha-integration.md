# BLOOMIN8 Home Assistant Integration

## Feature Branch: BLE Wake

The BLE wake feature is in the `feature/ble-wake` branch:
https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component/tree/feature/ble-wake

**Not yet merged** into main. This is why the standard HA integration can't wake the frame — the BLE wake code is still in a feature branch.

### HA Integration Config Options

- `mac_address` — BLE MAC address of the frame (required for BLE wake)
- `ble_auto_wake` — If `true`, the integration automatically sends BLE wake before HTTP commands (default: `false`)
- `ble_wake_wait_seconds` — How long to wait after BLE pulse before probing HTTP (default: 10)

### HA Services (from feature branch)

All services support entity_id and device_id targeting:

| Service | Description |
|---------|-------------|
| `show_next` | Show next image in queue |
| `sleep` | Put device to sleep |
| `reboot` | Reboot device |
| `clear_screen` | Clear screen to white |
| `whistle` | Send keep-alive (NOT a wake — only works on already-online devices) |
| `refresh_device_info` | Refresh cached device info |
| `update_settings` | Update device settings (sleep_duration, max_idle, etc.) |
| `upload_image_url` | Upload image from URL |
| `upload_image_data` | Upload image from base64 data |
| `upload_images_multi` | Upload multiple images |
| `upload_dithered_image_data` | Upload pre-dithered raw data |
| `delete_image` | Delete image from gallery |
| `create_gallery` | Create a new gallery |
| `delete_gallery` | Delete gallery and images |
| `list_galleries` | List all galleries |
| `show_playlist` | Play a playlist |
| `list_playlists` | List playlists |
| `get_playlist` | Get playlist details |
| `put_playlist` | Create/overwrite a playlist |
| `delete_playlist` | Delete a playlist |

### BLE Wake Implementation Details

The HA integration uses:
- `bluetooth.async_ble_device_from_address(hass, mac, connectable=True)` to find the device
- `bleak` (via `bleak_retry_connector` if available, falling back to plain `BleakClient`)
- Write `0x01` (assert) then `0x00` (release) with 1ms gap to char `0000f001-0000-1000-8000-00805f9b34fb`
- `withoutResponse` writes (no ACK expected)
- 5-second max_idle cooldown between wake attempts
- 4-second initial delay + polling up to 30 seconds for HTTP to come up

### Why /whistle Doesn't Wake

The `/whistle` endpoint is a keep-alive that resets the idle timer on an **already-online** device. The device's Wi-Fi stack is completely shut down in sleep mode — no HTTP requests can reach it. Only the BLE radio remains active, and it only responds to the specific GATT write sequence described above.
