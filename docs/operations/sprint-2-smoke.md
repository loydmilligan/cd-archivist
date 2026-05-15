# Sprint-2 manual smoke test

End-to-end hardware test for the archivist on the real CM4 + real
USB CD-ROM + real webcam + real Tasmota LED panel. The unit test
suite covers everything fake-able; this checklist covers what only
the rig can prove.

Run through all six sections in order. Record the resulting
`CD_NNNN` id and the state-transition wall-clock in the Activity Log
entry that closes sprint-2.

> **Postponed for sprint-3+** — neither a systemd unit (`D-systemd-defer`)
> nor Docker packaging (`D-docker-postpone`) ships this sprint. The
> archivist runs from ssh as a foregrounded `python -m archivist`.
> If it crashes mid-cycle, the sudoers + cdplay invariants in the
> code are what protect the rig — not a supervisor.

---

## 1. Preflight

Run each check on the CM4 over ssh. Each must pass before starting
the archivist; **do not skip ahead** if any fails.

- [ ] `/srv/cd-archivist/discs` exists and is writable by the user
  the archivist will run as.

  ```sh
  test -w /srv/cd-archivist/discs && echo OK || echo FAIL
  ```

- [ ] `cdplay.service` is `active` and serving audio (so we can
  verify the stop/restart pairing later).

  ```sh
  systemctl is-active cdplay.service     # → active
  ```

- [ ] Webcam responds to `v4l2-ctl --list-devices`. Expect at least
  one entry under `/dev/video0`.

  ```sh
  v4l2-ctl --list-devices
  ```

- [ ] Tasmota LED panel responds. Expect JSON `{"POWER":"OFF"}` or
  `{"POWER":"ON"}`.

  ```sh
  curl -s "http://192.168.5.186/cm?cmnd=Power"
  ```

- [ ] NOPASSWD sudo fragment is installed at
  `/etc/sudoers.d/cd-archivist` per `docs/operations/cm4-setup.md`
  § "NOPASSWD sudo fragment". Verify the four rules exist for the
  run-as user.

  ```sh
  sudo -l -U $(whoami) | grep -E "systemctl|tee"   # → 4 NOPASSWD lines
  ```

- [ ] No previous `python -m archivist` process is already running
  (would race on the drive).

  ```sh
  pgrep -fa "python -m archivist"   # → no output
  ```

---

## 2. Start the archivist

Foreground over ssh. Defaults match `docs/operations/cm4-setup.md`;
override via env vars if your rig differs.

```sh
ssh cm4
cd /opt/cd-archivist   # or wherever the repo is checked out
python -m archivist
```

Expected first-second log lines (on stderr):

- `starting archivist — device=/dev/sr0 discs_root=/srv/cd-archivist/discs port=8228`
- One of:
  - `camera usb bus path: 1-1.2.2` (or similar — the resolved bus path), OR
  - `camera USB path not resolved — captures will be skipped...`
    (acceptable for the smoke if the cam isn't on the documented
    `0c45:6366` vendor:product; record the actual `lsusb` line in
    the close-out note and update the default in `usb_discovery.py`)
- `Uvicorn running on http://0.0.0.0:8228` (from the uvicorn thread)

Leave the ssh session open. The state-machine log lines will print
here as the cycle advances.

---

## 3. Browse to the status page

From a phone (or laptop) on the same subnet:

- [ ] Open `http://cm4:8228/` (or `http://<cm4-ip>:8228/`).
- [ ] Page renders. **Looks like Mash Co.**:
  - Dark slate background (`#07090c`-ish), not pure black.
  - Page title `cd-archivist` in the Bricolage Grotesque display
    font, large, off-white (`--fg`).
  - Eyebrow labels (`STATUS`, `DRIVE`, `LOG TAIL`) in ALL CAPS,
    small, with letter-spacing — **and ≤2 words each**.
  - Pulp-orange (`#ff5b2e`) shows as the left-border accent on the
    state card. The card has a full 1px border around it as well
    (not the bare-left-stripe trope).
  - Sentence case throughout body copy. **No emoji anywhere.**
- [ ] Initial state shows `IDLE`. `disc`, `last rip`, and `updated`
  show `—` placeholders until a cycle runs.
- [ ] Log tail in the lower card is non-empty (the startup lines
  from §2 are visible there).

If any of the above fails, stop and file the regression before
proceeding — the UI dressing is not load-bearing for the hardware
path but it's the visible-progress scope and we want to know.

---

## 4. Insert a CD and observe the cycle

- [ ] Pick a known audio CD (something with a printed track listing
  helps for the sanity check in §5).
- [ ] Insert it into the USB CD-ROM. The tray closes automatically
  on most drives; if yours doesn't, push it in by hand.
- [ ] Watch the state card in the browser. Within ~4 seconds the
  state value should advance through:

  | State        | What's happening on the rig                                                  |
  |--------------|------------------------------------------------------------------------------|
  | `WAITING`    | drive reports `disc-ok`, archivist sees it next tick                         |
  | `STABILIZE`  | 2s settle while the drive stops spinning up                                  |
  | `CAPTURE`    | `cdplay.service` stops; LED panel goes off→on→off; ffmpeg fires twice        |
  | `RIP`        | `cdparanoia` runs (the long one — minutes per CD); `flac` follows            |
  | `EJECT`      | drive ejects; `cdplay.service` restarts                                      |
  | `IDLE`       | back to standby                                                              |

- [ ] The card's left-border accent **should swap semantic colors**
  as the state advances (the impl uses `--accent` throughout in
  sprint-2; if the dressing-up to swap colors per state hasn't
  landed yet, note "card stays pulp-orange across all states" in
  the close-out and add a follow-up — not a sprint-2 blocker).
- [ ] LED panel: visible-eye check that it pulses off→on→off during
  CAPTURE. The lit burst should be obviously brighter than ambient.
- [ ] After EJECT, the disc pops out. Take it out so the cycle can
  finish back to IDLE.
- [ ] Record the assigned id from the status card: `CD_NNNN = ____`.
- [ ] Record wall-clock from insert → IDLE: `____ minutes`.

---

## 5. Verify on-disk artifact

Back on the CM4 shell:

```sh
DISC=/srv/cd-archivist/discs/CD_0001    # substitute the actual id
ls -la "$DISC"
```

- [ ] Expect: `manifest.json`, `captures/`, `audio/`, `logs/`,
  `review/`.

- [ ] Captures directory has exactly 6 JPGs:

  ```sh
  ls "$DISC/captures/"
  # → disc_front_ambient_001.jpg disc_front_ambient_002.jpg
  #   disc_front_ambient_003.jpg disc_front_lit_001.jpg
  #   disc_front_lit_002.jpg     disc_front_lit_003.jpg
  ```

  Open one ambient + one lit JPG. They should be the same framing,
  just under different lighting. If both are black or both are
  blown out, the LED logic is wrong — capture the JPGs and file a
  bug.

- [ ] Audio directory has FLACs matching the CD's track count
  (printed on the case, or counted in your player).

  ```sh
  ls "$DISC/audio/" | wc -l
  ```

- [ ] Manifest parses and reflects reality:

  ```sh
  jq . "$DISC/manifest.json"
  ```

  Required fields:
  - `schema_version`: `"0.2"`
  - `disc_id`: matches the dir name
  - `media_type`: `"audio_cd"`
  - `status`: `"ripped"`
  - `captures`: array of 2 entries (`lighting: "ambient"` and
    `lighting: "lit"`), each with 3 entries in `image_paths`
  - `rips`: array of 1 entry with `status` in `{"success", "partial"}`;
    `tracks` lists the FLACs as `audio/trackNN.flac`
  - `pairings`: array of 1 entry with `method: "single_session"` and
    `confidence: "high"`
  - `errors`: probably `[]`; non-empty is fine if rip was partial,
    just note it

- [ ] Quick audio sanity: play one of the FLACs. It should be
  recognizable as the right track at the right pitch.

  ```sh
  mpv "$DISC/audio/track01.flac"   # ctrl-c after a few seconds
  ```

---

## 6. Verify `cdplay.service` is back

- [ ] cdplay restarted cleanly post-eject:

  ```sh
  systemctl is-active cdplay.service   # → active
  ```

- [ ] Insert another CD via cdplay's normal flow (or just verify
  playback works on the rig's normal audio path). The archivist
  must not have left the player permanently down.

- [ ] If `cdplay.service` is **not** active here, that is a
  blocking regression — the cdplay invariant is the load-bearing
  protection against the archivist breaking the rig's day job.
  Restart by hand, capture the archivist log, and file before
  closing sprint-2.

---

## Close-out

Once all six sections pass, append an Activity Log entry to
`docs/coordination/sprint-2.md` that records:

- the `CD_NNNN` id from §4
- the wall-clock cycle time
- the actual camera USB bus path (or "not resolved")
- any field that drifted from this checklist (cam vendor:product
  ID, file paths, timing) so the next sprint's smoke catches the
  drift early
- whether `smoke-camera-recovery` (the long-idle VIDIOC_STREAMON
  test) was attempted and what happened

After that and after the `smoke-camera-recovery` task closes,
sprint-2 is ready for `gsd-complete-milestone`.
