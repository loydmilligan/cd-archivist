// cd-archivist — shared chrome + atoms (header, drawer, log, atoms)
const { useState, useEffect } = React;

/* =============================================================== Header */
function Header({ rightMode, onRightModeChange, logOpen, onLogToggle, rigStats }) {
  return (
    <header className="cda-header">
      <div className="cda-brand">
        <span className="cda-brand-mark">cd/a</span>
        <span className="cda-brand-slug">cd-archivist</span>
        <span className="cda-brand-host">{rigStats.hostname} · {rigStats.ip}</span>
      </div>

      <span className="cda-live">ripping · DISC-A4F2</span>

      <div className="cda-rig-stats">
        <div className="cda-rig-stat">
          <span className="lbl">Ripped</span>
          <span className="val">{rigStats.discsRipped}</span>
        </div>
        <div className="cda-rig-stat">
          <span className="lbl">In review</span>
          <span className="val warn">{rigStats.inReview}</span>
        </div>
        <div className="cda-rig-stat">
          <span className="lbl">Partial</span>
          <span className="val ember">{rigStats.partial}</span>
        </div>
        <div className="cda-rig-stat">
          <span className="lbl">Storage</span>
          <span className="val">{rigStats.storage.used} / {rigStats.storage.total}</span>
        </div>
        <div className="cda-rig-stat">
          <span className="lbl">Uptime</span>
          <span className="val">{rigStats.uptime}</span>
        </div>
      </div>

      <div className="cda-header-nav">
        <button className="cda-nav-btn">navidrome ↗</button>
        <button className="cda-nav-btn">beets ↗</button>
        <button
          className={"cda-nav-btn " + (logOpen ? "is-on" : "")}
          onClick={onLogToggle}
        >
          ≡ daemon log
        </button>
        <button
          className={"cda-nav-btn " + (rightMode === "drive" ? "is-on" : "")}
          onClick={() => onRightModeChange("drive")}
        >
          drive
        </button>
        <button
          className={"cda-nav-btn " + (rightMode === "card" ? "is-on" : "")}
          onClick={() => onRightModeChange("card")}
        >
          card detail
        </button>
      </div>
    </header>
  );
}

/* ============================================================ TrackSegs */
function TrackSegments({ tracks, size = "sm" }) {
  return (
    <div className={"cda-segs " + (size === "lg" ? "cda-segs--lg" : "")}>
      {tracks.map((t) => {
        let cls = "cda-seg is-" + t.status;
        if (t.identified) cls += " has-id";
        const style = t.status === "ripping" ? { "--p": Math.round((t.progress || 0) * 100) + "%" } : undefined;
        return <span key={t.n} className={cls} style={style} title={`track ${t.n} · ${t.status}${t.identified ? " · id" : ""}`} />;
      })}
    </div>
  );
}

/* ============================================================ Thumb */
function DiscThumb({ disc, size = 56 }) {
  if (disc.photo === "art" && disc.art) {
    // album-art placeholder — vinyl-stripe block + initials
    const initials = disc.art.artist.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
    return (
      <div className="cda-thumb cda-thumb--art" style={{ width: size, height: size, background: "#1d242b" }}>
        <div className="cda-art" />
        <span className="cda-thumb-art-text" style={{ position: "absolute" }}>{initials}</span>
      </div>
    );
  }
  // disc-label thumb — CD photo placeholder
  return (
    <div className="cda-thumb cda-thumb--label" style={{ width: size, height: size }}>
      <span style={{ fontSize: size * 0.18, color: "rgba(255,255,255,0.18)", fontFamily: "var(--font-mono)" }}>
        {disc.slug.slice(-4)}
      </span>
    </div>
  );
}

/* ============================================================ Chips row */
function ChipsRow({ chips }) {
  if (!chips || !chips.length) return null;
  return (
    <div className="cda-chips">
      {chips.map((c, i) => {
        const lvl = c.level || "muted";
        return (
          <span key={i} className={`cda-chip cda-chip--${lvl} ${c.asserted ? "is-asserted" : ""} ${c.glow ? "is-glow" : ""}`}>
            {c.label}
          </span>
        );
      })}
    </div>
  );
}

/* ============================================================ Bottom log */
function BottomLog({ open, onToggle, lines }) {
  const errors = lines.filter(l => l.level === "error").length;
  const warns  = lines.filter(l => l.level === "warn").length;
  return (
    <div className={"cda-log " + (open ? "is-open" : "is-collapsed")}>
      <div className="cda-log-head" onClick={onToggle}>
        <span className="cda-log-title">{open ? "▾" : "▸"} daemon log</span>
        <span className="cda-log-counts">
          {lines.length} entries · <span className="w">{warns} warn</span> · <span className="e">{errors} error</span> · last 16:08:12
        </span>
        <span style={{ marginLeft: "auto", font: "500 10px/1 var(--font-mono)", color: "var(--fg-quiet)" }}>
          per-rip filter · sprint-7
        </span>
      </div>
      {open ? (
        <div className="cda-log-body">
          {lines.map((l, i) => (
            <div key={i} className={"cda-log-line is-" + l.level}>
              <span className="t">{l.t}</span>
              <span className="lvl">{l.level}</span>
              <span className="msg">{l.msg}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

Object.assign(window, { Header, TrackSegments, DiscThumb, ChipsRow, BottomLog });
