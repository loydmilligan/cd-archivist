// cd-archivist — DiscCard + ExpandedBody + RightDrawer
const { useState: useS } = React;

/* ============================================================ Card */
function DiscCard({ disc, isFocused, onFocus, onExpand }) {
  const stateClass =
    disc.state === "ripping"     ? "is-ripping"     :
    disc.state === "damaged"     ? "is-damaged"     :
    disc.state === "looking-up"  ? "is-monitoring"  :
    disc.state === "weak-match"  ? "is-weak"        :
    disc.state === "no-match"    ? "is-no-match"    :
    disc.state === "in-library"  ? "is-library"     : "";

  return (
    <article
      className={"cda-card " + stateClass + (disc.expanded ? " is-expanded" : "") + (isFocused ? " is-focused" : "")}
      onClick={onFocus}
    >
      <div className="cda-card-head">
        <DiscThumb disc={disc} />
        <div className="cda-card-meta">
          <div className="cda-card-slug">{disc.slug}</div>
          <div className={"cda-card-title " + (disc.titleAsserted ? "is-asserted" : "")}>{disc.title}</div>
          <div className={"cda-card-artist " + (disc.artistAsserted ? "is-asserted" : "")}>
            {disc.artistGuess} {disc.albumGuess ? `· ${disc.albumGuess}` : ""} · {disc.trackCount} tracks
          </div>
        </div>
      </div>

      <TrackSegments tracks={disc.tracks} size={disc.expanded ? "lg" : "sm"} />

      <div className="cda-card-status">{disc.statusLine}</div>

      <ChipsRow chips={disc.chips} />

      {disc.expanded ? <ExpandedBody disc={disc} /> : null}
    </article>
  );
}

/* ============================================================ Expanded */
function ExpandedBody({ disc }) {
  const showCandidates = disc.state === "weak-match" && disc.candidates;
  const showDamaged    = disc.state === "damaged" || disc.column === "capture";
  return (
    <div className="cda-expanded">
      {showCandidates ? (
        <div className="cda-section">
          <div className="cda-section-title">Beets candidates · {disc.candidates.length}</div>
          <div className="cda-candidates">
            {disc.candidates.map((c, i) => (
              <div key={i} className={"cda-candidate " + (i === 0 ? "is-top" : "")}>
                <span className="score">{c.score.toFixed(2)}</span>
                <div className="cda-candidate-meta">
                  <span className="cda-candidate-release">{c.release}</span>
                  <span className="cda-candidate-detail">{c.tracks} · mbid <code className="t-code">{c.mbid}</code></span>
                </div>
                <button className="cda-btn cda-btn--ghost cda-btn--sm">Apply</button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="cda-section">
        <div className="cda-section-title">Hints · operator-asserted</div>
        <div className="cda-hints-grid">
          <button className={"cda-hint-toggle " + (disc.chips.some(c => c.label.includes("VA")) ? "is-on" : "")}>
            <span className="cda-hint-box" />
            Various artists
          </button>
          <button className={"cda-hint-toggle " + (disc.chips.some(c => c.label.includes("BURNED")) ? "is-on" : "")}>
            <span className="cda-hint-box" />
            Burned cd
          </button>
          <button className={"cda-hint-toggle " + (disc.chips.some(c => c.label.includes("MIX")) ? "is-on" : "")}>
            <span className="cda-hint-box" />
            Mix cd
          </button>
          <button className="cda-hint-toggle">
            <span className="cda-hint-box" />
            Demo / unreleased
          </button>
        </div>
        <div className="cda-input-row">
          <span className="lbl">Album</span>
          <input className="cda-input" defaultValue={disc.title === "(disc · no match)" ? "" : disc.title} placeholder="title goes to source.json" />
        </div>
        <div className="cda-input-row">
          <span className="lbl">Artist</span>
          <input className="cda-input" defaultValue={disc.artistGuess === "—" ? "" : disc.artistGuess} placeholder="leave empty if mix" />
        </div>
      </div>

      <div className="cda-section">
        <div className="cda-section-title">Manual steps</div>
        <div className="cda-actions">
          <button className="cda-btn cda-btn--primary">Paste mbid → re-id</button>
          <button className="cda-btn cda-btn--secondary">Run beets search</button>
          <button className="cda-btn cda-btn--ghost">Edit source.json</button>
          <button className="cda-btn cda-btn--ghost">Skip · move to failed</button>
        </div>
      </div>

      {showDamaged ? (
        <div className="cda-section">
          <div className="cda-section-title" style={{ color: "var(--ember)" }}>Damaged-disc actions</div>
          <div className="cda-actions">
            <button className="cda-btn cda-btn--secondary">Process partial as-is</button>
            <button className="cda-btn cda-btn--ember">Redo entire capture</button>
            <button className="cda-btn cda-btn--ember">Pick tracks to re-rip…</button>
          </div>
          <p className="cda-gate-hint">Destructive actions require a second click to confirm. The partial flac files stay on disk until you choose.</p>
        </div>
      ) : null}
    </div>
  );
}

/* ============================================================ Drawer modes */
function DriveStatus({ status, rig }) {
  return (
    <div className="cda-drawer-body">
      <div className="cda-disc-photo">
        <div className="cda-disc-photo-glow" />
      </div>

      <div className="cda-drawer-section">
        <span className="t">Drive</span>
        <dl className="cda-kv">
          <dt>device</dt><dd>{status.device}</dd>
          <dt>state</dt><dd className="moss">{status.state}</dd>
          <dt>loaded</dt><dd>{status.loadedDisc} · {status.loadedAt}</dd>
          <dt>rpm</dt><dd>{status.rpm}</dd>
          <dt>temp</dt><dd>{status.tempC} °C</dd>
        </dl>
      </div>

      <div className="cda-drawer-section">
        <span className="t">Active rip</span>
        <dl className="cda-kv">
          <dt>track</dt><dd>{status.currentTrack} / 12</dd>
          <dt>sector</dt><dd>{status.currentSector.toLocaleString()}</dd>
          <dt>retries</dt><dd className="warn">{status.retries}</dd>
          <dt>elapsed</dt><dd>{status.elapsed}</dd>
          <dt>est remaining</dt><dd>{status.estRemaining}</dd>
          <dt>photo</dt><dd className="moss">{status.photoState}</dd>
        </dl>
      </div>

      <div className="cda-drawer-section">
        <span className="t">Cache</span>
        <dl className="cda-kv">
          <dt>inbox</dt><dd>3</dd>
          <dt>review</dt><dd>{rig.inReview}</dd>
          <dt>library</dt><dd>{rig.discsRipped}</dd>
          <dt>failed</dt><dd className="ember">{rig.failed}</dd>
          <dt>archive</dt><dd>0</dd>
        </dl>
      </div>

      <div className="cda-drawer-section">
        <span className="t">Poll cadence</span>
        <p style={{ margin: 0, font: "500 12px/1.5 var(--font-mono)", color: "var(--fg-2)" }}>
          1s during active rip · 5s when idle. Adaptive to keep the CM4 quiet.
        </p>
      </div>
    </div>
  );
}

function CardDetail({ disc, rig }) {
  if (!disc) {
    return (
      <div className="cda-drawer-body">
        <p style={{ font: "500 12px/1.5 var(--font-mono)", color: "var(--fg-quiet)" }}>
          No card focused. Click a card to load its rip log, source.json, and disc photo.
        </p>
      </div>
    );
  }
  const sourceJson = `{
  "slug": "${disc.slug}",
  "disc_id": "MqfRq9CqWLF8vTwzL...",
  "acoustid": "${disc.state === "in-library" ? "0.97" : disc.state === "weak-match" ? "0.42" : "—"}",
  "musicbrainz_id": "${disc.state === "in-library" ? "e4a8...91" : "null"}",
  "asserted": {
    "various_artists": ${disc.chips.some(c => c.label.includes("VA"))},
    "burned": ${disc.chips.some(c => c.label.includes("BURNED"))},
    "mix": ${disc.chips.some(c => c.label.includes("MIX"))},
    "album": ${disc.titleAsserted ? `"${disc.title}"` : "null"}
  },
  "track_count": ${disc.trackCount},
  "captured_at": "2026-05-16T16:04:12Z"
}`;
  return (
    <div className="cda-drawer-body">
      <div className="cda-disc-photo">
        <div className="cda-disc-photo-glow" />
      </div>

      <div className="cda-drawer-section">
        <span className="t">Disc</span>
        <dl className="cda-kv">
          <dt>slug</dt><dd>{disc.slug}</dd>
          <dt>title</dt><dd>{disc.title}</dd>
          <dt>artist</dt><dd>{disc.artistGuess}</dd>
          <dt>tracks</dt><dd>{disc.trackCount}</dd>
          <dt>column</dt><dd>{disc.column}</dd>
        </dl>
      </div>

      <div className="cda-drawer-section">
        <span className="t">Rip log · tail</span>
        <pre className="cda-rip-log">{disc.sourceLogTail ? disc.sourceLogTail.join("\n") : "no recent log lines\nuse expanded card to scroll the full log"}</pre>
      </div>

      <div className="cda-drawer-section">
        <span className="t">source.json</span>
        <pre className="cda-json" dangerouslySetInnerHTML={{
          __html: sourceJson
            .replace(/"([a-z_]+)":/g, '<span class="k">"$1"</span>:')
            .replace(/: ("[^"]*")/g, ': <span class="s">$1</span>')
            .replace(/: (true|false)/g, ': <span class="b">$1</span>')
            .replace(/: ([0-9.]+)/g, ': <span class="n">$1</span>'),
        }} />
      </div>
    </div>
  );
}

function RightDrawer({ mode, focusedDisc, rig, status }) {
  return (
    <aside className="cda-drawer">
      <header className="cda-drawer-head">
        <span className="cda-drawer-mode">
          {mode === "drive" ? "▸ drive · live" : "▸ card · " + (focusedDisc?.slug || "none")}
        </span>
        <button className="cda-btn cda-btn--ghost cda-btn--sm">pin</button>
      </header>
      {mode === "drive" ? <DriveStatus status={status} rig={rig} /> : <CardDetail disc={focusedDisc} rig={rig} />}
    </aside>
  );
}

/* ============================================================ Column */
function Column({ stage, label, lamp, count, children }) {
  return (
    <div className="cda-col">
      <div className="cda-col-head">
        <div className="cda-col-title">
          <span className="cda-col-stage">stage {stage}</span>
          <span className="cda-col-name">
            <span className={"cda-col-headlamp cda-col-headlamp--" + lamp} />
            {label}
            <span className="num">{count}</span>
          </span>
        </div>
      </div>
      <div className="cda-col-body">
        {children}
      </div>
    </div>
  );
}

Object.assign(window, { DiscCard, ExpandedBody, RightDrawer, Column });
