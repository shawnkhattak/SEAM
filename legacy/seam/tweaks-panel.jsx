/* ─── TWEAKS PANEL — loaded as type="text/babel" ──────────────────────────── */

function useTweaks(defaults) {
  const [tweaks, setTweaks] = React.useState(() => {
    try {
      const saved = localStorage.getItem('seam_tweaks');
      return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
    } catch { return defaults; }
  });

  React.useEffect(() => {
    const t = tweaks;
    const root = document.documentElement;
    if (t.accentColor) {
      root.style.setProperty('--accent', t.accentColor);
      root.style.setProperty('--green', t.accentColor);
    }
    if (t.panelOpacity !== undefined) {
      const op = t.panelOpacity / 100;
      root.style.setProperty('--bg-glass', `rgba(252,253,254,${op})`);
      root.style.setProperty('--bg-glass-strong', `rgba(255,255,255,${Math.min(op + 0.12, 1)})`);
    }
    if (t.showGlowEffects === false) {
      root.style.setProperty('--accent-glow', 'rgba(0,0,0,0)');
    } else {
      root.style.setProperty('--accent-glow', 'rgba(47,184,163,0.32)');
    }
    if (t.mapTiles && window.__seamMapRef) {
      const urls = {
        light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      };
      if (window.__seamTileLayerRef && urls[t.mapTiles]) {
        window.__seamTileLayerRef.setUrl(urls[t.mapTiles]);
      }
    }
  }, [tweaks]);

  const setTweak = (k, v) => {
    setTweaks(prev => {
      const next = { ...prev, [k]: v };
      try { localStorage.setItem('seam_tweaks', JSON.stringify(next)); } catch {}
      return next;
    });
  };

  return [tweaks, setTweak];
}

function TweaksPanel({ children }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ position: 'fixed', bottom: 18, right: 18, zIndex: 900, pointerEvents: 'auto' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="toolbar-btn"
        title="Visual tweaks"
        style={{ borderRadius: '50%', width: 36, height: 36, padding: 0, justifyContent: 'center', display: 'flex', alignItems: 'center' }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>
      {open && (
        <div
          className="glass-panel-bright"
          style={{ position: 'absolute', bottom: 44, right: 0, width: 220, borderRadius: 12, padding: '14px 16px', animation: 'slideUp 0.2s ease' }}
        >
          <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 10 }}>TWEAKS</div>
          {children}
        </div>
      )}
    </div>
  );
}

function TweakSection({ label }) {
  return (
    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.08em', marginTop: 10, marginBottom: 5 }}>
      {label.toUpperCase()}
    </div>
  );
}

function TweakRadio({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>{label}</div>
      <div style={{ display: 'flex', gap: 3 }}>
        {options.map(o => (
          <button
            key={o}
            onClick={() => onChange(o)}
            style={{
              flex: 1, padding: '4px 0', border: '1px solid',
              borderRadius: 5, fontSize: 10, fontFamily: 'var(--font-mono)', cursor: 'pointer',
              background: value === o ? 'rgba(47,184,163,0.14)' : 'transparent',
              borderColor: value === o ? 'rgba(47,184,163,0.35)' : 'var(--border)',
              color: value === o ? 'var(--accent-deep)' : 'var(--text-muted)',
              transition: 'all 0.15s',
            }}
          >{o}</button>
        ))}
      </div>
    </div>
  );
}

function TweakColor({ label, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{label}</span>
      <input
        type="color" value={value}
        onChange={e => onChange(e.target.value)}
        style={{ width: 28, height: 20, border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', padding: 0, background: 'transparent' }}
      />
    </div>
  );
}

function TweakSlider({ label, value, min, max, step, unit, onChange }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} />
    </div>
  );
}

function TweakToggle({ label, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{label}</span>
      <button
        onClick={() => onChange(!value)}
        style={{
          width: 32, height: 18, borderRadius: 9, border: 'none',
          background: value ? 'var(--accent)' : 'rgba(38,52,68,0.15)',
          cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
          flexShrink: 0,
        }}
      >
        <div style={{
          position: 'absolute', top: 2, left: value ? 14 : 2,
          width: 14, height: 14, borderRadius: '50%', background: '#fff',
          transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }} />
      </button>
    </div>
  );
}
