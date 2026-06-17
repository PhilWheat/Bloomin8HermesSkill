# BLOOMIN8 Upload API Pattern

## The Critical Pattern

The BLOOMIN8 `/upload` endpoint uses a **hybrid API pattern** — metadata in URI query parameters, image file as the only multipart field.

**Correct (C# CanvasApiClient pattern):**
```
POST /upload?filename=test.jpg&gallery=default&show_now=1
Content-Type: multipart/form-data; boundary=...

--boundary
Content-Disposition: form-data; name="image"; filename="test.jpg"
Content-Type: image/jpeg

[binary JPEG data]
--boundary--
```

**Wrong (common curl pattern — DOES NOT WORK):**
```
POST /upload?gallery=default&show_now=1
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="image"; filename="test.jpg"
Content-Type: image/jpeg

[binary JPEG data]
--boundary
Content-Disposition: form-data; name="filename"

test.jpg
--boundary--
```

## Why curl Fails

Using `curl -F "image=@file.jpg" -F "filename=test.jpg"` sends both fields as form data. The server expects `filename` in the URI query string only, so it rejects the request with `{"status":"fail","msg":"Invalid filename or extension"}`.

Additionally, curl's HTTP/1.1 handling of the server's malformed response (duplicate Content-Type headers, mismatched Content-Length) causes curl to report "Invalid Content-Length: value" even when the upload succeeded on the server side.

## Python `requests` Correct Pattern

```python
import requests

# filename, gallery, show_now in URI query params
params = {
    'filename': 'test.jpg',
    'gallery': 'default',
    'show_now': '1'
}

# image is the only multipart file field
files = {'image': ('test.jpg', open('test.jpg', 'rb'), 'image/jpeg')}

r = requests.post("http://IP/upload", files=files, params=params, timeout=30)
```

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/deviceInfo` | GET | Device status, battery, resolution |
| `/state` | GET | Brief task processor status |
| `/upload` | POST | Upload single JPEG (params: filename, gallery, show_now) |
| `/image/uploadMulti` | POST | Upload multiple images (JSON body with base64 data) |
| `/image/dataUpload` | POST | Upload pre-dithered raw image data (JSON body) |
| `/image/delete` | DELETE | Delete image from gallery (params: filename, gallery) |
| `/gallery/list` | GET | List all galleries |
| `/gallery` | PUT | Create gallery (body: JSON string with name) |
| `/gallery` | GET | List images in gallery |
| `/show` | POST | Display image/gallery/playlist (JSON body with play_type, image/gallery/playlist) |
| `/sleep` | POST | Put frame to sleep |
| `/reboot` | POST | Software reboot |
| `/clearScreen` | POST | Clear screen to white |
| `/whistle` | GET | Keep-alive (keep frame awake) |
| `/settings` | POST | Apply new configuration |

## Image Scaling Notes

- Frame resolution: **1200×1600 portrait** (EL133UF1 display)
- Images should be letterboxed (centered on black background) to fill without cropping
- Use PIL's `thumbnail()` or manual scaling with `Image.LANCZOS` for best quality
- Save as JPEG, quality 85-90 recommended
