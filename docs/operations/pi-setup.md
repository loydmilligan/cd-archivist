# Raspberry Pi Setup Notes

## Responsibilities

The Pi should:

- Control the camera
- Detect tray state or respond to trigger
- Store captures
- Receive rips
- Pair captures and rips
- Generate metadata
- Host review UI
- Host or feed music library

## Recommended folders

```text
/srv/cd-archivist/
  captures/
  incoming-rips/
  discs/
  review/
  logs/

/srv/music/
```

## Camera

Start with a simple command-line capture.

Later add:

- Tray detection
- Image burst capture
- Glare detection
- Auto-cropping
