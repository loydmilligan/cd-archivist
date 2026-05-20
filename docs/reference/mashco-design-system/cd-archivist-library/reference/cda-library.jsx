// cd-archivist — Library Manager shell + comparison artboards for the
// surface-switcher decision. Static React + Babel components. Reuses
// rig stats / live chip / right drawer / bottom log treatment from
// cda-chrome.jsx (loaded by the same HTML).

const { useState: useLibS } = React;

// ============================================================ Surface switcher — Option A (header tabs)

function SurfaceTabs({ active = "rip" }) {
  return (
    <div className="cda-tabs" role="tablist">
      <button className={"cda-tab " + (active === "rip" ? "is-on" : "")}>
        Rip <span className="count">4</span>
      </button>
      <button className={"cda-tab " + (active === "library" ? "is-on" : "")}>
        Library <span className="count">7</span>
      </button>
    </div>
  );
}

// ============================================================ Surface switcher — Option C (breadcrumb)

function SurfaceSwitcher({ active = "rip", popOpen = false }) {
  return (
    <div className="cda-switcher">
      <span className="cda-brand-mark">cd/a</span>
      <span className="cda-switcher-sep">·</span>
      <button className="cda-switcher-btn">
        {active}
        <span className="cda-switcher-caret">▾</span>
      </button>
      {popOpen ? (
        <div className="cda-switcher-pop">
          <div className="cda-switcher-pop-h">Surfaces</div>
          <div className={"cda-switcher-row " + (active === "rip" ? "is-on" : "")}>
            <span className="check">✓</span>
            <span className="name">rip</span>
            <span className="meta">4 ripping · 2 review</span>
          </div>
          <div className={"cda-switcher-row " + (active === "library" ? "is-on" : "")}>
            <span className="check">✓</span>
            <span className="name">library</span>
            <span className="meta">3 inbox · 1 download</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ============================================================ Headers — both variants

function HeaderTabsVariant({ active = "rip", rigStats }) {
  return (
    <header className="cda-header">
      <div className="cda-brand">
        <span className="cda-brand-mark">cd/a</span>
        <span className="cda-brand-slug">cd-archivist</span>
      </div>
      <SurfaceTabs active={active} />
      <span className="cda-live">ripping · DISC-A4F2</span>
      <div className="cda-rig-stats">
        <div className="cda-rig-stat"><span className="lbl">Ripped</span><span className="val">{rigStats.discsRipped}</span></div>
        <div className="cda-rig-stat"><span className="lbl">In review</span><span className="val warn">{rigStats.inReview}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Partial</span><span className="val ember">{rigStats.partial}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Storage</span><span className="val">{rigStats.storage.used} / {rigStats.storage.total}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Uptime</span><span className="val">{rigStats.uptime}</span></div>
      </div>
      <div className="cda-header-nav">
        <button className="cda-nav-btn">navidrome ↗</button>
        <button className="cda-nav-btn">beets ↗</button>
      </div>
    </header>
  );
}

function HeaderBreadcrumbVariant({ active = "rip", popOpen = false, rigStats }) {
  return (
    <header className="cda-header">
      <SurfaceSwitcher active={active} popOpen={popOpen} />
      <span className="cda-brand-host">{rigStats.hostname} · {rigStats.ip}</span>
      <span className="cda-live">ripping · DISC-A4F2</span>
      <div className="cda-rig-stats">
        <div className="cda-rig-stat"><span className="lbl">Ripped</span><span className="val">{rigStats.discsRipped}</span></div>
        <div className="cda-rig-stat"><span className="lbl">In review</span><span className="val warn">{rigStats.inReview}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Partial</span><span className="val ember">{rigStats.partial}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Storage</span><span className="val">{rigStats.storage.used} / {rigStats.storage.total}</span></div>
        <div className="cda-rig-stat"><span className="lbl">Uptime</span><span className="val">{rigStats.uptime}</span></div>
      </div>
      <div className="cda-header-nav">
        <button className="cda-nav-btn">navidrome ↗</button>
        <button className="cda-nav-btn">beets ↗</button>
      </div>
    </header>
  );
}

// ============================================================ Panel inventory

const LIB_PANELS = {
  primary: [
    {
      id: "downloads",
      glyph: "↓",
      name: "Downloads",
      sub: "spooty queue",
      count: "1",
      title: "Spotify → YouTube",
      eyebrow: "Downloads · spooty queue",
      summary: "Albums and playlists queued for spooty to download from YouTube using the Spotify track list as the spec. One row per playlist; per-track sub-state.",
    },
    {
      id: "inbox",
      glyph: "▣",
      name: "Inbox",
      sub: "cd rips · downloads",
      count: "3",
      title: "Albums waiting to import",
      eyebrow: "Inbox queue",
      summary: "/srv/music/inbox/ + /srv/music/inbox/spooty/. One row per album folder. READY-marked folders are eligible for beets auto-import.",
    },
    {
      id: "disk",
      glyph: "◧",
      name: "Disk",
      sub: "usage",
      count: null,
      title: "Where the bytes live",
      eyebrow: "Disk usage",
      summary: "Per-mount and per-surface breakdown. /, /mnt/seagate (the new 1 TB), /mnt/archive. Inbox vs library vs archive vs spooty.",
    },
    {
      id: "library",
      glyph: "♪",
      name: "Library",
      sub: "browse + jump",
      count: null,
      title: "Browse · jump to Navidrome",
      eyebrow: "Library",
      summary: "Read-only Subsonic API into Navidrome. Search + 10 most-recent imports + one big jump-out CTA. Real browsing happens in Navidrome.",
    },
  ],
  ghosts: [
    {
      id: "review",
      glyph: "?",
      name: "Review",
      sub: "soon",
      title: "Beets couldn't auto-apply",
      eyebrow: "Review queue · v2",
      summary: "Walks /srv/music/review/. Surfaces what beets couldn't match.",
    },
    {
      id: "recent",
      glyph: "≡",
      name: "Recent imports",
      sub: "soon",
      title: "Tail of beets-import.log",
      eyebrow: "Recent imports · v2",
      summary: "Reads /srv/music/logs/beets-import.log + beets sqlite. Live tail of what just landed.",
    },
    {
      id: "cron",
      glyph: "⏱",
      name: "Cron / scheduler",
      sub: "soon",
      title: "Spooty cron health",
      eyebrow: "Cron / scheduler · v2",
      summary: "Next-run + last-run + errors for the spooty cron and any other scheduled jobs.",
    },
  ],
};

// ============================================================ Library shell — left sidebar

function LibrarySidebar({ activeId }) {
  return (
    <aside className="cda-lib-sidebar">
      <div className="cda-lib-side-group">Queues</div>
      {LIB_PANELS.primary.slice(0, 2).map(p => (
        <div key={p.id} className={"cda-lib-row " + (activeId === p.id ? "is-active" : "")}>
          <span className="glyph">{p.glyph}</span>
          <span className="label">
            <span className="name">{p.name}</span>
            <span className="sub">{p.sub}</span>
          </span>
          {p.count ? <span className="count">{p.count}</span> : null}
        </div>
      ))}

      <div className="cda-lib-side-group">Health</div>
      {LIB_PANELS.primary.slice(2, 3).map(p => (
        <div key={p.id} className={"cda-lib-row " + (activeId === p.id ? "is-active" : "")}>
          <span className="glyph">{p.glyph}</span>
          <span className="label">
            <span className="name">{p.name}</span>
            <span className="sub">{p.sub}</span>
          </span>
        </div>
      ))}

      <div className="cda-lib-side-group">Browse</div>
      {LIB_PANELS.primary.slice(3, 4).map(p => (
        <div key={p.id} className={"cda-lib-row " + (activeId === p.id ? "is-active" : "")}>
          <span className="glyph">{p.glyph}</span>
          <span className="label">
            <span className="name">{p.name}</span>
            <span className="sub">{p.sub}</span>
          </span>
        </div>
      ))}

      <div className="cda-lib-side-group">Coming · v2</div>
      {LIB_PANELS.ghosts.map(p => (
        <div key={p.id} className="cda-lib-row is-ghost">
          <span className="glyph">{p.glyph}</span>
          <span className="label">
            <span className="name">{p.name}</span>
            <span className="sub">{p.sub}</span>
          </span>
          <span className="soon">soon</span>
        </div>
      ))}
    </aside>
  );
}

// ============================================================ Landing card grid (default when no panel selected)

function LandingDownloadsPreview() {
  return (
    <div className="cda-lib-card-preview">
      <div className="cda-prev-pl-row">
        <span>liked songs · 47 tracks</span>
        <span style={{ color: "var(--fg-quiet)" }}>32/47</span>
      </div>
      <div className="cda-prev-pl-pips">
        {Array.from({ length: 24 }, (_, i) => {
          const cls = i < 18 ? "is-ok" : i === 18 ? "is-active" : i === 22 ? "is-err" : "";
          return <span key={i} className={"cda-prev-pl-pip " + cls} />;
        })}
      </div>
    </div>
  );
}

function LandingInboxPreview() {
  return (
    <div className="cda-lib-card-preview">
      <div className="cda-prev-inbox-row">
        <span><span className="name">Wilco · A Ghost Is Born</span></span>
        <span className="size">421 MB</span>
        <span className="ready">ready</span>
      </div>
      <div className="cda-prev-inbox-row">
        <span><span className="name">Aimee Mann · Bachelor No. 2</span></span>
        <span className="size">312 MB</span>
        <span style={{ color: "var(--fg-quiet)" }}>—</span>
      </div>
      <div className="cda-prev-inbox-row">
        <span><span className="name">spooty/ Caribou playlist</span></span>
        <span className="size">128 MB</span>
        <span className="ready">ready</span>
      </div>
    </div>
  );
}

function LandingDiskPreview() {
  return (
    <div className="cda-lib-card-preview cda-prev-disk">
      <div className="cda-prev-disk-row">
        <span className="mount">/</span>
        <span className="bar"><i style={{ width: "44%" }} /></span>
        <span className="val">44%</span>
      </div>
      <div className="cda-prev-disk-row">
        <span className="mount">/mnt/seagate</span>
        <span className="bar"><i style={{ width: "23%" }} /></span>
        <span className="val">23%</span>
      </div>
      <div className="cda-prev-disk-row">
        <span className="mount">/mnt/archive</span>
        <span className="bar"><i className="is-amber" style={{ width: "78%" }} /></span>
        <span className="val">78%</span>
      </div>
    </div>
  );
}

function LandingLibraryPreview() {
  const recent = [
    { name: "Tom Waits · Mule Variations", when: "14m" },
    { name: "Miles Davis · Kind of Blue", when: "1h" },
    { name: "Big Thief · Two Hands", when: "2d" },
  ];
  return (
    <div className="cda-lib-card-preview">
      {recent.map(r => (
        <div key={r.name} className="cda-prev-lib-row">
          <span className="cda-prev-lib-thumb" />
          <span className="name">{r.name}</span>
          <span className="when">{r.when}</span>
        </div>
      ))}
    </div>
  );
}

function GhostPreview() {
  return (
    <div className="cda-lib-card-preview">
      <span className="cda-prev-ghost-line" />
      <span className="cda-prev-ghost-line is-mid" />
      <span className="cda-prev-ghost-line is-short" />
    </div>
  );
}

function LandingCard({ panel, ghost = false, previewKind }) {
  let Preview = null;
  if (ghost) Preview = GhostPreview;
  else if (previewKind === "downloads") Preview = LandingDownloadsPreview;
  else if (previewKind === "inbox") Preview = LandingInboxPreview;
  else if (previewKind === "disk") Preview = LandingDiskPreview;
  else if (previewKind === "library") Preview = LandingLibraryPreview;
  else Preview = GhostPreview;

  return (
    <article className={"cda-lib-card " + (ghost ? "is-ghost" : "")}>
      <header className="cda-lib-card-head">
        <span className="cda-lib-card-eyebrow">{panel.eyebrow}</span>
        {ghost ? <span className="cda-lib-card-soon">soon · v2</span> : null}
      </header>
      <h3 className="cda-lib-card-title">{panel.title}</h3>
      <p className="cda-lib-card-sub">{panel.summary}</p>
      <Preview />
    </article>
  );
}

function LibraryLanding() {
  return (
    <div className="cda-lib-panel">
      <header className="cda-lib-landing-h">
        <p className="eyebrow">Library manager · cm4 music stack</p>
        <h1>The post-rip side of the rig</h1>
        <p>
          Queues, disk, scheduled jobs, library browse. Four panels live now, three coming. Pick one from the menu on the left or start with a card below.
        </p>
      </header>
      <div className="cda-lib-landing-grid">
        <LandingCard panel={LIB_PANELS.primary[0]} previewKind="downloads" />
        <LandingCard panel={LIB_PANELS.primary[1]} previewKind="inbox" />
        <LandingCard panel={LIB_PANELS.primary[2]} previewKind="disk" />
        <LandingCard panel={LIB_PANELS.primary[3]} previewKind="library" />
        {LIB_PANELS.ghosts.map(p => (
          <LandingCard key={p.id} panel={p} ghost />
        ))}
      </div>
    </div>
  );
}

// ============================================================ Panel header + "in design" placeholder

function PanelHeader({ panel, statsRight }) {
  return (
    <header className="cda-lib-panel-head">
      <div className="cda-lib-panel-head-left">
        <span className="eyebrow">{panel.eyebrow}</span>
        <h1>{panel.title}</h1>
        <p className="sub">{panel.summary}</p>
      </div>
      {statsRight}
    </header>
  );
}

function PanelEmptyPlaceholder({ panel }) {
  return (
    <div className="cda-lib-panel-empty">
      <div className="row">
        <span style={{ color: "var(--fg-quiet)", textAlign: "center", fontWeight: 700 }}>·</span>
        <span><span className="label">ghost row · ghost row · ghost row</span></span>
        <span style={{ color: "var(--fg-quiet)" }}>—</span>
      </div>
      <div className="row">
        <span style={{ color: "var(--fg-quiet)", textAlign: "center", fontWeight: 700 }}>·</span>
        <span><span className="label">ghost row · ghost row · ghost row</span></span>
        <span style={{ color: "var(--fg-quiet)" }}>—</span>
      </div>
      <div className="row">
        <span style={{ color: "var(--fg-quiet)", textAlign: "center", fontWeight: 700 }}>·</span>
        <span><span className="label">ghost row · ghost row · ghost row</span></span>
        <span style={{ color: "var(--fg-quiet)" }}>—</span>
      </div>
      <div className="cda-lib-panel-empty-foot">
        <span className="tag">in design</span>
        <span>UX is intentionally undecided in this pass. Drill-in actions, list density, expand-states, and retry/import affordances come in a per-panel brief.</span>
      </div>
    </div>
  );
}

function DownloadsPanel() {
  const stats = (
    <div className="stats">
      <div><span className="lbl">Playlists</span><span className="val">1</span></div>
      <div><span className="lbl">Tracks</span><span className="val">47</span></div>
      <div><span className="lbl">Done</span><span className="val" style={{ color: "var(--moss)" }}>32</span></div>
      <div><span className="lbl">Errors</span><span className="val" style={{ color: "var(--ember)" }}>3</span></div>
    </div>
  );
  return (
    <div className="cda-lib-panel">
      <PanelHeader panel={LIB_PANELS.primary[0]} statsRight={stats} />
      <PanelEmptyPlaceholder panel={LIB_PANELS.primary[0]} />
    </div>
  );
}

// ============================================================ Library shell (left sidebar + viewport)

function LibraryShell({ activeId = null, rigStats, switcherActive = "library", switcherPopOpen = false, useTabs = false }) {
  return (
    <div className="cda-app">
      {useTabs
        ? <HeaderTabsVariant active="library" rigStats={rigStats} />
        : <HeaderBreadcrumbVariant active={switcherActive} popOpen={switcherPopOpen} rigStats={rigStats} />}

      <main className="cda-main">
        <div className="cda-lib-shell">
          <LibrarySidebar activeId={activeId} />
          <div className="cda-lib-viewport">
            {activeId === "downloads" ? <DownloadsPanel />
              : activeId ? <DownloadsPanel />  /* placeholder for now */
              : <LibraryLanding />}
          </div>
        </div>
      </main>

      <aside className="cda-drawer">
        <header className="cda-drawer-head">
          <span className="cda-drawer-mode">▸ library · idle</span>
          <button className="cda-btn cda-btn--ghost cda-btn--sm">pin</button>
        </header>
        <div className="cda-drawer-idle">
          Select an item to see details.
        </div>
      </aside>

      <BottomLog open={false} onToggle={() => {}} lines={DAEMON_LOG} />
    </div>
  );
}

// ============================================================ Side-by-side comparison wrappers
// Used by the canvas to show A vs C in their own artboards.

function HeaderCompareTabs({ rigStats }) {
  return (
    <div className="cda-app" style={{ gridTemplateRows: "56px 1fr" }}>
      <HeaderTabsVariant active="rip" rigStats={rigStats} />
      <main className="cda-main" style={{ display: "grid", placeItems: "center", padding: 40 }}>
        <div style={{ textAlign: "center", color: "var(--fg-quiet)", font: "500 13px/1.5 var(--font-mono)" }}>
          Option A · two pulp tabs between the brand and the live chip.<br/>
          Familiar pattern, minimal change to existing header, header gets busier.
        </div>
      </main>
    </div>
  );
}

function HeaderCompareBreadcrumb({ rigStats }) {
  return (
    <div className="cda-app" style={{ gridTemplateRows: "56px 1fr" }}>
      <HeaderBreadcrumbVariant active="rip" popOpen={true} rigStats={rigStats} />
      <main className="cda-main" style={{ display: "grid", placeItems: "center", padding: 40 }}>
        <div style={{ textAlign: "center", color: "var(--fg-quiet)", font: "500 13px/1.5 var(--font-mono)" }}>
          Option C · the brand mark becomes the navigation primitive.<br/>
          Dropdown shows every surface with a per-surface telemetry hint.<br/>
          Takes no horizontal real estate from the work area.
        </div>
      </main>
    </div>
  );
}

Object.assign(window, {
  SurfaceTabs, SurfaceSwitcher,
  HeaderTabsVariant, HeaderBreadcrumbVariant,
  LibrarySidebar, LibraryLanding, LibraryShell,
  HeaderCompareTabs, HeaderCompareBreadcrumb,
  LIB_PANELS,
});
