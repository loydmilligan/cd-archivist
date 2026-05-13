# Power Mac G4 Setup Notes

## Responsibilities

The G4 should:

- Read CDs
- Rip audio
- Eject discs
- Sync completed rips to the Raspberry Pi

The G4 should not:

- Run AI/OCR
- Own the camera
- Be the main metadata database
- Host the final music library

## iTunes baseline

Configure iTunes to:

- Import CD automatically
- Eject CD after import
- Use error correction if available
- Import to a predictable folder

Example rip folder:

```text
/Users/grandpa/Music/Ripped CDs/
```

## Sync to Pi

Example rsync:

```bash
rsync -av --ignore-existing "/Users/grandpa/Music/Ripped CDs/" pi@raspberrypi.local:/srv/cd-archivist/incoming-rips/
```

## Future improvement

The G4 may send simple event triggers to the Pi:

```bash
ssh pi@raspberrypi.local "cd-archivist capture start"
```

Avoid requiring this for the base system.
