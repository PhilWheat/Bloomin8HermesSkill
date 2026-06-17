# BLOOMIN8 E-Ink Canvas — Hermes Skill

Wake and upload images to a [BLOOMIN8 E-Ink Canvas](https://bloomin8.readme.io/) smart picture frame from Hermes Agent.

## Quick Install

```bash
git clone https://github.com/PhilWheat/Bloomin8HermesSkill.git
mkdir -p ~/.hermes/skills/smart-home
cp -r Bloomin8HermesSkill/bloomin8-ble-wake/* ~/.hermes/skills/smart-home/bloomin8-ble-wake/
```

Then restart Hermes.

## What It Does

1. **BLE Wake** — The frame sleeps deeply. A BLE pulse wakes it so HTTP commands work.
2. **Auto-scaling Upload** — Resizes and letterboxes any image to fit the 1200×1600 display.
3. **Config from Vault** — Reads your frame's IP, BLE MAC, and resolution from an Obsidian note. No env vars needed.

## Prerequisites

- Python 3.10+
- Linux with a Bluetooth adapter
- Hermes Agent installed

### Install Dependencies

```bash
pip install Pillow requests bleak
```

### Grant Bluetooth Access (Linux)

Add your user to the bluetooth group (no sudo needed after):

```bash
sudo usermod -aG bluetooth $USER
# Then log out and back in
```

### Create a Vault Note

Create `BLOOMIN8 E-Ink Canvas.md` in your Obsidian vault with:

```markdown
# BLOOMIN8 E-Ink Canvas

## Device Details

- **IP Address:** 192.168.x.x
- **Bluetooth MAC Address:** XX:XX:XX:XX:XX:XX
- Resolution is 1200 wide x 1600 high
```

Find the BLE MAC in the BLOOMIN8 app or `bluetoothctl list`. **It's different from the Wi-Fi MAC.**

## Usage

```bash
# Upload and display
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg

# To a custom gallery
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --gallery myart

# Upload without triggering display
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --no-show

# Dry run (verify config)
python3 ~/.hermes/scripts/bloomin8_upload.py photo.jpg --dry-run
```

## How It Works

The script reads your vault note, BLE-wakes the frame, scales your image to fill the 1200×1600 display (letterbox, no crop), and uploads via the correct API pattern (metadata in URI query params, image as the sole multipart file field).

## Structure

```
bloomin8-ble-wake/
├── SKILL.md                    # Skill definition
├── scripts/
│   ├── bloomin8_ble_wake.py    # BLE wake only
│   └── bloomin8_upload.py      # Full upload with scaling
└── references/
    ├── ha-integration.md       # Home Assistant integration notes
    ├── upload-api-pattern.md   # Upload API details
    └── setup-guide.md          # Full installation guide
```

## License

MIT
