# Power Mac G4 Setup Notes (DEPRECATED)

> **Status: deprecated 2026-05-14.** The two-machine design (G4 ripper + Pi brain) was retired before any code shipped. The CD-ROM moved to a USB drive directly attached to the Raspberry Pi CM4. See `cm4-setup.md` for the current setup.

This file is retained for historical context only. The original concept was:

- G4 acts as the optical drive host and CDDA ripper (iTunes or XLD).
- G4 syncs ripped audio to the Pi over rsync.
- Pi handles camera, metadata, review, and library publication.

The pivot to a single-CM4 architecture eliminated:

- The G4 itself (and its OS/iTunes/rsync setup work).
- Network sync between machines and its failure modes.
- The HTTP capture contract that was going to coordinate the two.
- The two-agent split in `sprint-1.md`.

The pieces that survived the pivot: the manifest schema, the disc-folder layout, the Pydantic models, the disc-id allocator, the timestamp-pairing primitive, and the capture-ambient/lit convention.
