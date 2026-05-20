// cd-archivist — mock data
// Six discs spread across the four pipeline stages, covering every state
// called out in the project overview: active rip, damaged/partial, queued,
// monitoring (beets-id), weak match in review, VA hint applied,
// confirmed-in-library, mix CD with operator-entered per-track titles.

// Per-track rip state per the doc:
//   "ok"     — ripped clean (green)
//   "recovered" — read errors recovered with retries (blue)
//   "error"  — unrecoverable sector errors (red)
//   "pending" — not yet ripped or skipped (gray/empty)
// + `identified: true` adds an outline once beets confirms the track.

const NOW = "Sat May 16 · 4:08 PM";

const DISCS = [
  // ===================================================== CAPTURE ===========
  {
    id: "disc-a4f2",
    slug: "DISC-A4F2",
    column: "capture",
    state: "ripping",
    title: "(disc · ripping track 7/12)",
    artistGuess: "—",
    trackCount: 12,
    chips: [],
    tracks: [
      { n: 1,  status: "ok",        identified: false, dur: "3:42" },
      { n: 2,  status: "ok",        identified: false, dur: "4:18" },
      { n: 3,  status: "ok",        identified: false, dur: "3:55" },
      { n: 4,  status: "recovered", identified: false, dur: "5:02" },
      { n: 5,  status: "ok",        identified: false, dur: "4:31" },
      { n: 6,  status: "ok",        identified: false, dur: "3:48" },
      { n: 7,  status: "ripping",   identified: false, dur: "—",  progress: 0.62 },
      { n: 8,  status: "pending",   identified: false, dur: "—" },
      { n: 9,  status: "pending",   identified: false, dur: "—" },
      { n: 10, status: "pending",   identified: false, dur: "—" },
      { n: 11, status: "pending",   identified: false, dur: "—" },
      { n: 12, status: "pending",   identified: false, dur: "—" },
    ],
    statusLine: "ripping track 7 · sector 24,318 · 1 retry · 04:12 elapsed",
    photo: "label", // shows label photo
    sourceLogTail: [
      "cdparanoia: track 6 done · 0 errors · 26.4 MB",
      "cdparanoia: track 7 begin",
      "cdparanoia: track 7 · sector 24316 · retry 1",
    ],
  },

  {
    id: "disc-7c1b",
    slug: "DISC-7C1B",
    column: "capture",
    state: "damaged",
    title: "(disc · damaged · 3 unrecoverable sectors)",
    artistGuess: "—",
    trackCount: 10,
    chips: [{ label: "PARTIAL", level: "ember" }],
    tracks: [
      { n: 1,  status: "ok",        identified: false, dur: "3:12" },
      { n: 2,  status: "ok",        identified: false, dur: "2:58" },
      { n: 3,  status: "recovered", identified: false, dur: "4:01" },
      { n: 4,  status: "error",     identified: false, dur: "—" },
      { n: 5,  status: "error",     identified: false, dur: "—" },
      { n: 6,  status: "ok",        identified: false, dur: "3:44" },
      { n: 7,  status: "ok",        identified: false, dur: "4:18" },
      { n: 8,  status: "error",     identified: false, dur: "—" },
      { n: 9,  status: "ok",        identified: false, dur: "3:36" },
      { n: 10, status: "ok",        identified: false, dur: "4:02" },
    ],
    statusLine: "halted · 3 unrecoverable sectors on tracks 4, 5, 8",
    photo: "label",
    damaged: true,
  },

  // ===================================================== BEETS ID =========
  {
    id: "disc-9e34",
    slug: "DISC-9E34",
    column: "beets",
    state: "looking-up",
    title: "(disc · fingerprinting)",
    artistGuess: "—",
    trackCount: 11,
    chips: [{ label: "VA?", level: "muted", asserted: true }],
    tracks: Array.from({ length: 11 }, (_, i) => ({
      n: i + 1, status: "ok", identified: false, dur: "—",
    })),
    statusLine: "running acoustid on 11 tracks · disc-id MqfRq... · 00:34 elapsed",
    photo: "label",
  },

  {
    id: "disc-3b81",
    slug: "DISC-3B81",
    column: "beets",
    state: "looking-up",
    title: "(disc · fingerprinting)",
    artistGuess: "(operator entered)",
    artistAsserted: true,
    albumGuess: "Coltrane Plays the Blues",
    albumAsserted: true,
    trackCount: 6,
    chips: [{ label: "ARTIST · ASSERTED", level: "pulp", asserted: true }],
    tracks: Array.from({ length: 6 }, (_, i) => ({
      n: i + 1, status: "ok", identified: false, dur: "—",
    })),
    statusLine: "running mbid lookup with operator hint · 00:08 elapsed",
    photo: "label",
  },

  // ===================================================== REVIEW ===========
  {
    id: "disc-5d2e",
    slug: "DISC-5D2E",
    column: "review",
    state: "weak-match",
    title: "Vibes & Things vol. 4",
    titleAsserted: true,
    artistGuess: "Various Artists",
    artistAsserted: true,
    trackCount: 14,
    chips: [
      { label: "MIX", level: "sky", asserted: true },
      { label: "VA", level: "sky", asserted: true },
      { label: "WEAK MATCH · 0.42", level: "amber" },
    ],
    tracks: [
      { n: 1,  status: "ok", identified: true,  dur: "3:42", title: "intro / bell" },
      { n: 2,  status: "ok", identified: true,  dur: "4:18", title: "trickster" },
      { n: 3,  status: "ok", identified: false, dur: "3:55" },
      { n: 4,  status: "ok", identified: false, dur: "5:02" },
      { n: 5,  status: "ok", identified: true,  dur: "4:31", title: "low country" },
      { n: 6,  status: "ok", identified: false, dur: "3:48" },
      { n: 7,  status: "ok", identified: false, dur: "4:22" },
      { n: 8,  status: "ok", identified: false, dur: "3:18" },
      { n: 9,  status: "ok", identified: false, dur: "4:55" },
      { n: 10, status: "ok", identified: false, dur: "3:31" },
      { n: 11, status: "ok", identified: false, dur: "4:08" },
      { n: 12, status: "ok", identified: false, dur: "3:48" },
      { n: 13, status: "ok", identified: false, dur: "5:14" },
      { n: 14, status: "ok", identified: true,  dur: "2:36", title: "outro / bell" },
    ],
    statusLine: "3 of 14 tracks identified · VA mix · no full MB release matches",
    photo: "label",
    why: "no_full_match",
    candidates: [
      { score: 0.42, release: "Various — Friends of the Family vol. 2 (Mute, 2003)", tracks: "10 of 14 titles match", mbid: "b3...91" },
      { score: 0.31, release: "Various — Loungin' (Verve, 2001)", tracks: "6 of 14 titles match", mbid: "f7...c2" },
      { score: 0.28, release: "Various — Mood Music vol. 3 (Ninja Tune, 1998)", tracks: "4 of 14 titles match", mbid: "a1...0e" },
    ],
    expanded: true,
  },

  {
    id: "disc-1f08",
    slug: "DISC-1F08",
    column: "review",
    state: "no-match",
    title: "(disc · no match)",
    artistGuess: "—",
    trackCount: 8,
    chips: [
      { label: "BURNED", level: "amber", asserted: true },
      { label: "NO MATCH", level: "ember" },
    ],
    tracks: Array.from({ length: 8 }, (_, i) => ({
      n: i + 1, status: "ok", identified: false, dur: ["3:42","4:18","2:58","5:02","3:31","4:08","3:48","2:36"][i],
    })),
    statusLine: "no acoustid match · no mb release · operator marked as burned CD",
    photo: "label",
    why: "burned_no_meta",
  },

  // ===================================================== IN LIBRARY ======
  {
    id: "disc-8a0c",
    slug: "DISC-8A0C",
    column: "library",
    state: "in-library",
    title: "Mule Variations",
    artistGuess: "Tom Waits",
    trackCount: 16,
    chips: [
      { label: "MUSICBRAINZ · 0.97", level: "moss" },
      { label: "ALBUM · CONFIRMED", level: "moss" },
    ],
    tracks: Array.from({ length: 16 }, (_, i) => ({
      n: i + 1, status: "ok", identified: true,
      dur: ["3:11","5:32","4:55","5:08","3:42","4:18","4:01","6:14","3:48","4:22","3:18","5:14","4:08","3:36","4:02","5:42"][i],
    })),
    statusLine: "imported to /srv/music/library/Tom Waits/Mule Variations/ · 14:02 ago",
    photo: "art",
    art: { artist: "Tom Waits", album: "Mule Variations" },
  },

  {
    id: "disc-c2ff",
    slug: "DISC-C2FF",
    column: "library",
    state: "in-library",
    title: "Kind of Blue",
    artistGuess: "Miles Davis",
    trackCount: 5,
    chips: [
      { label: "MUSICBRAINZ · 1.00", level: "moss" },
      { label: "ALBUM · CONFIRMED", level: "moss" },
    ],
    tracks: Array.from({ length: 5 }, (_, i) => ({
      n: i + 1, status: "ok", identified: true,
      dur: ["9:22","9:45","5:30","11:32","9:24"][i],
    })),
    statusLine: "imported · 1h 14m ago",
    photo: "art",
    art: { artist: "Miles Davis", album: "Kind of Blue" },
  },
];

// ====================================================== RIG STATE =========
const RIG = {
  hostname: "cda-pi",
  ip: "192.168.6.38:8228",
  uptime: "11d 4h",
  discsRipped: 142,
  inReview: 5,
  partial: 2,
  failed: 1,
  storage: { used: "412 GB", total: "1.8 TB", pct: 23 },
};

// Drive status — what the right drawer shows when no card is selected
const DRIVE_STATUS = {
  device: "/dev/sr0 · TSSTcorp SE-208GB",
  state: "ripping",
  loadedDisc: "DISC-A4F2",
  loadedAt: "4:04 PM",
  currentTrack: 7,
  currentSector: 24318,
  retries: 1,
  photoState: "captured · 1280×960 · 8.4 KB",
  elapsed: "04:12",
  estRemaining: "~12:30",
  tempC: 38,
  rpm: "6,200",
};

// Daemon log tail for the bottom drawer
const DAEMON_LOG = [
  { t: "16:08:12", level: "info",  msg: "cdparanoia track 6 done · 0 errors · 26.4 MB" },
  { t: "16:08:12", level: "info",  msg: "flac encode track 6 · -V8 · 3.8s" },
  { t: "16:08:09", level: "info",  msg: "cdparanoia track 7 begin" },
  { t: "16:07:58", level: "warn",  msg: "cdparanoia track 7 · sector 24316 · retry 1" },
  { t: "16:07:54", level: "info",  msg: "photo captured · disc-a4f2.label.jpg · 8.4 KB" },
  { t: "16:07:48", level: "info",  msg: "disc-id resolved · MqfRq...vTwzL · libdiscid 0.6.4" },
  { t: "16:07:01", level: "info",  msg: "DISC-A4F2 inserted · TOC parsed · 12 tracks · 51:38" },
  { t: "16:06:55", level: "info",  msg: "tray closed · drive ready" },
  { t: "16:04:22", level: "info",  msg: "DISC-9E34 → beets-id · fingerprinting" },
  { t: "16:03:48", level: "info",  msg: "DISC-8A0C → library · /srv/music/library/Tom Waits/..." },
  { t: "16:03:46", level: "info",  msg: "beets auto-apply DISC-8A0C · acoustid 0.97 · mb e4a...91" },
  { t: "16:02:11", level: "warn",  msg: "DISC-7C1B halted · 3 unrecoverable sectors" },
  { t: "16:01:55", level: "error", msg: "cdparanoia track 4 · sector 12044 · giving up after 8 retries" },
];

Object.assign(window, { DISCS, RIG, DRIVE_STATUS, DAEMON_LOG, NOW });
