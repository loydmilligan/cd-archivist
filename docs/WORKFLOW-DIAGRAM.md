# WORKFLOW-DIAGRAM.md

> Mermaid diagrams of the disc-to-library pipeline. For the component
> map and data model, see `docs/ARCHITECTURE.md`. For commit/deploy
> workflow, see `docs/WORKFLOW.md`.

---

## Disc-to-library pipeline

```mermaid
flowchart TD
    INSERT([Disc inserted\ninto drive]) --> DETECT

    DETECT[Drive detects disc\n/dev/sr0 CDROM_DRIVE_STATUS] --> STABILIZE

    STABILIZE[2-second stabilize timer\nKanban: card appears in Capture] --> PARALLEL

    PARALLEL{Parallel: rip + capture}
    PARALLEL --> RIP_START
    PARALLEL --> CAM_START

    RIP_START[cdparanoia -B\nstreams stderr progress] --> FLAC
    FLAC[flac --best\nper WAV → FLAC] --> RIP_DONE

    CAM_START[LED off\nambient burst ×3] --> LED_ON
    LED_ON[LED on\nlit burst ×3] --> LED_OFF
    LED_OFF[LED off in finally] --> CAM_DONE

    RIP_DONE --> JOIN
    CAM_DONE --> JOIN

    JOIN{All audio + photos\nwritten to inbox/}

    JOIN --> CHECK_RIP{Rip status?}

    CHECK_RIP -->|success / partial| DISC_ID
    CHECK_RIP -->|fail — no audio| FAILED

    FAILED[Move to failed/\nsource.json status.partial=false\nKanban: Capture — red shadow]
    FAILED --> EJECT_FAIL[Eject drive]
    EJECT_FAIL --> IDLE_FAIL([IDLE])

    DISC_ID[libdiscid\nTOC hash → musicbrainz_disc_id] --> ACOUSTID
    ACOUSTID[AcoustID fingerprint\nchroma fingerprint per track] --> MB_LOOKUP

    MB_LOOKUP[musicbrainzngs\ndisc-id lookup] --> MB_CHECK{Match found?}

    MB_CHECK -->|no match| AID_LOOKUP
    MB_CHECK -->|match| CONFIDENCE

    AID_LOOKUP[AcoustID lookup\nfingerprint query] --> CONFIDENCE

    CONFIDENCE{Beets confidence\nhigh / low?}

    CONFIDENCE -->|high confidence\nauto-apply threshold| AUTO_APPLY
    CONFIDENCE -->|low confidence\nno match / weak| REVIEW

    AUTO_APPLY[beets import --quiet\nvia docker exec\nKanban: Beets ID] --> LIBRARY
    LIBRARY[Move to library/\nnavidrome picks up hourly\nKanban: In Library]
    LIBRARY --> EJECT_OK[Eject drive]
    EJECT_OK --> IDLE_OK([IDLE])

    REVIEW[Write beets_review_reason\nMove to review/\nKanban: Review — card surfaces why]

    REVIEW --> OP_BRANCH{Operator action\nin kanban UI}

    OP_BRANCH -->|Accept top candidate| TOP_CAND
    OP_BRANCH -->|Manual MB search\npaste MBID| MBID_PASTE
    OP_BRANCH -->|Supply hints\nVA / Burned / Artist / Tracks| HINTS
    OP_BRANCH -->|Use as-is\nno tags| USE_AS_IS
    OP_BRANCH -->|Skip| SKIP

    TOP_CAND[POST accept-top-candidate\nwith picked MBID\nbeets import --mbid] --> LIBRARY

    MBID_PASTE[POST accept-top-candidate\nwith operator MBID] --> LIBRARY

    HINTS[PATCH hints\noperator_hints in source.json\nRe-run beets with hints] --> CONFIDENCE

    USE_AS_IS[POST use-as-is\ncopy to library/ untagged] --> LIBRARY

    SKIP[Mark skipped\nstay in review/] --> REVIEW_LONG

    REVIEW_LONG([In review\nlong-term — no auto-advance])

    CHECK_RIP -->|partial — some tracks failed| PARTIAL_BRANCH

    PARTIAL_BRANCH[Kanban: Capture\nred shadow — partial rip indicator]

    PARTIAL_BRANCH --> OP_DAMAGE{Operator action\nDamaged-Disc controls}

    OP_DAMAGE -->|Process partial as-is| PARTIAL_LIBRARY
    OP_DAMAGE -->|Redo entire capture| STABILIZE
    OP_DAMAGE -->|Pick tracks to re-rip| RERIP

    PARTIAL_LIBRARY[beets import partial\ncopy to review/ or library/] --> LIBRARY

    RERIP[cdparanoia selected tracks\nmerge with existing audio/] --> RIP_DONE
```

---

## State machine

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> WAITING : disc inserted\n(drive status = no_disc → has_disc)

    WAITING --> STABILIZE : disc confirmed\n(2s stabilize timer expires)

    STABILIZE --> RIP : cdparanoia starts\n+ camera burst fires

    RIP --> EJECT : rip complete\n(success OR partial)

    RIP --> STABILIZE_PARTIAL : rip failed\n(no WAVs — unreadable disc)

    STABILIZE_PARTIAL --> EJECT : partial folder written\nto failed/

    EJECT --> IDLE : drive.eject() called\n+ 3s settle timer

    note right of RIP
        post_rip_hook fires here:
        docker exec beet import
        → auto-apply or review/
    end note

    note right of EJECT
        cdplay.service decoupled
        (D-cdplay-decouple-not-install)
        Tray opens on its own
    end note
```

---

## Kanban UI surface annotations

Each state machine transition corresponds to a column or visual change
in the kanban at `cda.mattmariani.com`:

| State / Event                     | Kanban surface                                             |
| --------------------------------- | ---------------------------------------------------------- |
| STABILIZE → RIP                   | Card appears in **Capture** column; per-track bar starts filling |
| Active rip in progress            | Poll interval drops to 1 s; header shows "ripping · DISC-XXXX" |
| RIP complete — auto-apply         | Card moves to **Beets ID** column (briefly) → **In Library** |
| RIP complete — routed to review   | Card moves to **Review** column with reason chip           |
| Partial rip                       | Card stays in **Capture** with red-shadow treatment; 3 action buttons appear |
| Card clicked                      | Inline expansion with Hints / Manual Steps / Damaged-Disc sections |
| Drawer open — no card selected    | Right-side drawer shows live drive status (track / sector / retries / elapsed) |
| Drawer open — card selected       | Right-side drawer shows rip-log tail + source.json highlight + disc photo |
| Disc in library                   | Card in **In Library**; album art replaces disc-photo placeholder |
| Idle                              | Poll interval rises to 5 s; header shows "idle"            |
