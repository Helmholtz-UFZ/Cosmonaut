/* eslint-disable */
// Shared primitives — mirror cosmonaut_app/layout.py helpers.

const { useState, useEffect, useRef, useMemo } = React;

const STEPS = [
  { id: "user_info",         tab: "Information", title: "Provide user information" },
  { id: "data_upload",       tab: "Upload",      title: "Upload classification data" },
  { id: "street_selection",  tab: "Selection",   title: "Select streets for routing" },
  { id: "routing_params",    tab: "Parameters",  title: "Set routing parameters" },
  { id: "route_computation", tab: "Computation", title: "Monitor routing computation" },
  { id: "route_download",    tab: "Download",    title: "Download the computed route" },
];

function Navbar({ active, onNav }) {
  const links = [
    { id: "home",       label: "COSMONAUT",     brand: true },
    { id: "docs",       label: "Documentation", icon: "book" },
    { id: "logs",       label: "Logs",          icon: "journal-text" },
    { id: "workers",    label: "Worker manager",icon: "cpu" },
    { id: "jobs",       label: "Job manager",   icon: "list-task" },
  ];
  return (
    <nav className="navbar navbar-dark sticky-top" style={{ background:"#2c3e50", padding:"8px 0" }}>
      <div className="container" style={{ display:"flex", alignItems:"center", gap:"32px" }}>
        <a href="#" onClick={(e)=>{ e.preventDefault(); onNav("home"); }}
           style={{ color:"#fff", textDecoration:"none", display:"flex", alignItems:"center", gap:"8px", fontWeight:700, fontSize:"18px" }}>
          <img src="../../assets/logo.svg" alt="" width="28" height="28" style={{ filter:"invert(1)" }} />
          <span>COSMONAUT</span>
        </a>
        <div style={{ display:"flex", gap:"22px", fontSize:"14px" }}>
          {links.slice(1).map(l => (
            <a key={l.id} href="#"
               onClick={(e)=>{ e.preventDefault(); onNav(l.id); }}
               style={{
                 color: active === l.id ? "#fff" : "rgba(255,255,255,.7)",
                 textDecoration:"none",
                 fontWeight: active === l.id ? 600 : 400,
               }}>
              <i className={`bi bi-${l.icon}`} style={{ marginRight: 4 }}></i>{l.label}
            </a>
          ))}
        </div>
      </div>
    </nav>
  );
}

function PageHeader({ title, subtitle, children }) {
  return (
    <div style={{ border:"1px solid #212529", borderRadius:6, margin:"12px", marginTop:8, background:"#fff", overflow:"hidden" }}>
      <div style={{ background:"#3498db", color:"#fff", padding:"18px 0", textAlign:"center" }}>
        <h2 style={{ margin:0, fontSize:"2rem", fontWeight:500 }}>{title}</h2>
        {subtitle && <h3 style={{ margin:0, fontSize:"1.5rem", fontWeight:500, opacity:.95 }}>{subtitle}</h3>}
      </div>
      <div style={{ background:"#fff", padding:"14px" }}>{children}</div>
    </div>
  );
}

function WizardTabs({ stepId }) {
  return (
    <ul className="nav nav-tabs" style={{ marginTop: 8, borderBottom: "1px solid #dee2e6" }}>
      {STEPS.map(s => (
        <li key={s.id} className="nav-item">
          <a className={`nav-link ${s.id === stepId ? "active" : "disabled"}`}
             style={{ pointerEvents: "none" }}>
            {s.tab}
          </a>
        </li>
      ))}
    </ul>
  );
}

function WizardCard({ stepId, jobId, children, footer, banner }) {
  const step = STEPS.find(s => s.id === stepId);
  return (
    <div className="card shadow-sm" style={{ margin:"12px", marginRight:"16px" }}>
      <div className="card-header" style={{ background:"#fff" }}>
        <h3 style={{ margin:0, fontWeight:500, fontSize:"1.75rem" }}>
          {step.title}({jobId})
        </h3>
        <WizardTabs stepId={stepId} />
      </div>
      <div className="card-body">
        {banner}
        {children}
      </div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
}

function ProgressFooter({ onPrev, onNext, nextDisabled, prevDisabled }) {
  return (
    <div style={{ display:"flex", gap:"8px", justifyContent:"flex-end", alignItems:"center", flexWrap:"wrap" }}>
      {onPrev ? (
        <button className="btn btn-primary" disabled={prevDisabled} onClick={onPrev}>
          <i className="bi bi-arrow-left-circle" style={{ marginRight:4 }}></i>Previous
        </button>
      ) : <span />}
      {onNext ? (
        <button className="btn btn-primary" disabled={nextDisabled} onClick={onNext}>
          <i className="bi bi-arrow-right-circle" style={{ marginRight:4 }}></i>Next
        </button>
      ) : <span />}
    </div>
  );
}

function Alert({ kind = "info", icon, children, action }) {
  return (
    <div className={`alert alert-${kind}`} style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:"12px", marginBottom:"1rem" }}>
      <div style={{ display:"flex", alignItems:"center", gap:"10px" }}>
        {icon && <i className={`bi bi-${icon}`}></i>}
        <span>{children}</span>
      </div>
      {action}
    </div>
  );
}

function ResetBanner({ status, onReset }) {
  const cfg = {
    RUNNING:   { kind:"primary", msg:"This job is currently running. Reset to cancel and restart." },
    COMPLETED: { kind:"success", msg:"This job has been completed. Reset to clear results and restart." },
    FAILED:    { kind:"danger",  msg:"This job has failed. Reset to clear results and try again." },
  }[status];
  if (!cfg) return null;
  return (
    <Alert kind={cfg.kind} action={
      <button className="btn btn-warning btn-sm" onClick={onReset}>
        <i className="bi bi-arrow-counterclockwise" style={{ marginRight:4 }}></i>Reset Job
      </button>
    }>{cfg.msg}</Alert>
  );
}

function LoadingModal({ open }) {
  if (!open) return null;
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(33,37,41,.5)", zIndex:1050, display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:"#fff", borderRadius:8, padding:"24px", minWidth:240, textAlign:"center", boxShadow:"0 .5rem 1rem rgba(0,0,0,.15)" }}>
        <div style={{
          width:48, height:48,
          border:"4px solid #ecf0f1", borderTopColor:"#2c3e50",
          borderRadius:"50%", margin:"0 auto 12px",
          animation:"cnSpin .75s linear infinite",
        }} />
        <h4 style={{ margin:0, fontWeight:500 }}>Loading…</h4>
      </div>
    </div>
  );
}

function ResetConfirmModal({ open, onCancel, onConfirm }) {
  if (!open) return null;
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(33,37,41,.5)", zIndex:1050, display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:"#fff", borderRadius:8, width:480, boxShadow:"0 .5rem 1rem rgba(0,0,0,.15)", overflow:"hidden" }}>
        <div style={{ padding:"1rem", borderBottom:"1px solid #dee2e6" }}>
          <strong style={{ fontSize:"1.25rem", fontWeight:500 }}>Reset Job?</strong>
        </div>
        <div style={{ padding:"1rem", fontSize:14, lineHeight:1.5 }}>
          <p style={{ margin:"0 0 .5rem" }}>This will delete all computation results (logs, routes, GPX files) and reset the job status to PENDING. You will need to restart the computation.</p>
          <p style={{ margin:0, color:"#95a5a6" }}>Your uploaded data and selected streets will be preserved.</p>
        </div>
        <div style={{ padding:".75rem 1rem", borderTop:"1px solid #dee2e6", display:"flex", justifyContent:"flex-end", gap:8 }}>
          <button className="btn btn-outline-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-danger" onClick={onConfirm}>
            <i className="bi bi-exclamation-triangle" style={{ marginRight:4 }}></i>Reset Job
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// FauxMap — static OSM-style SVG with optional overlays
// =============================================================================
function FauxMap({ showMembership, showStreets, showRoute, showSelected, membershipOpacity = 0.7 }) {
  return (
    <div style={{ position:"relative", width:"100%", height:"100%", background:"#e8efe5", overflow:"hidden" }}>
      {/* base OSM-like tile */}
      <svg viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice" style={{ position:"absolute", inset:0, width:"100%", height:"100%" }}>
        <defs>
          <pattern id="osm-tile" width="120" height="120" patternUnits="userSpaceOnUse">
            <rect width="120" height="120" fill="#e8efe5"/>
            <path d="M0 60 H120 M60 0 V120" stroke="#cfdcc1" strokeWidth=".4" />
            <path d="M0 80 Q 30 70 60 78 T 120 65" stroke="#bccbb1" strokeWidth=".6" fill="none" />
          </pattern>
          {/* forest tufts */}
          <pattern id="forest" width="60" height="60" patternUnits="userSpaceOnUse">
            <circle cx="15" cy="22" r="9" fill="#b2c7a2" />
            <circle cx="40" cy="38" r="11" fill="#a8bf99" />
            <circle cx="48" cy="12" r="7" fill="#b9ceaa" />
          </pattern>
        </defs>
        <rect width="800" height="600" fill="url(#osm-tile)"/>
        {/* forest patches */}
        <ellipse cx="120" cy="120" rx="110" ry="80" fill="url(#forest)" opacity=".75"/>
        <ellipse cx="650" cy="180" rx="140" ry="100" fill="url(#forest)" opacity=".75"/>
        <ellipse cx="200" cy="500" rx="170" ry="80" fill="url(#forest)" opacity=".75"/>
        {/* yellow roads (default OSM secondary) */}
        <g stroke="#f5d97b" strokeWidth="6" fill="none" opacity=".75">
          <path d="M0 320 Q 200 280 380 310 T 800 280" />
          <path d="M150 0 Q 200 200 240 360 T 320 600" />
          <path d="M520 0 Q 480 250 540 400 T 600 600" />
        </g>
        {/* white residential roads */}
        <g stroke="#ffffff" strokeWidth="3" fill="none">
          <path d="M280 200 L 480 220 L 520 360 L 320 380 Z" />
          <path d="M260 240 L 480 260" />
          <path d="M300 280 L 520 300" />
          <path d="M320 320 L 510 340" />
          <path d="M380 200 L 400 380" />
          <path d="M440 200 L 470 380" />
        </g>
        {/* place labels */}
        <g fill="#3a3a3a" fontFamily="Lato, sans-serif" fontSize="11">
          <text x="240" y="160">Osterwieck</text>
          <text x="430" y="270">Dardesheim</text>
          <text x="580" y="400">Zilly</text>
          <text x="120" y="450">Berßel</text>
        </g>

        {/* membership tile overlay */}
        {showMembership && (
          <g opacity={membershipOpacity}>
            <defs>
              <radialGradient id="cluster1" cx="40%" cy="40%" r="40%">
                <stop offset="0%" stopColor="#9b59b6" stopOpacity=".7"/>
                <stop offset="100%" stopColor="#9b59b6" stopOpacity="0"/>
              </radialGradient>
              <radialGradient id="cluster2" cx="60%" cy="60%" r="40%">
                <stop offset="0%" stopColor="#1abc9c" stopOpacity=".7"/>
                <stop offset="100%" stopColor="#1abc9c" stopOpacity="0"/>
              </radialGradient>
              <radialGradient id="cluster3" cx="50%" cy="30%" r="35%">
                <stop offset="0%" stopColor="#f1c40f" stopOpacity=".7"/>
                <stop offset="100%" stopColor="#f1c40f" stopOpacity="0"/>
              </radialGradient>
            </defs>
            <rect width="800" height="600" fill="url(#cluster1)"/>
            <rect width="800" height="600" fill="url(#cluster2)"/>
            <rect width="800" height="600" fill="url(#cluster3)"/>
          </g>
        )}

        {/* COSMONAUT-style street GeoJSON layer */}
        {showStreets && (
          <g stroke="#e74c3c" strokeWidth="3" fill="none" opacity=".85">
            <path d="M120 380 Q 200 320 280 340 T 460 300 T 620 280 T 720 240" />
            <path d="M180 200 Q 240 260 320 240 T 460 280" />
            <path d="M320 120 L 320 540" />
            <path d="M200 480 L 420 460 L 540 500" />
            <path d="M460 140 L 480 280 L 460 460" />
            <path d="M540 180 Q 600 220 640 200" />
            <path d="M240 320 L 380 320 L 460 360" />
            <path d="M120 220 L 220 230 L 260 260" />
            <path d="M500 360 L 580 380 L 620 420" />
            <path d="M280 420 L 360 440 L 440 420" />
            {showSelected && (
              <>
                <path d="M320 240 L 460 280" stroke="#ffd400" strokeWidth="4" />
                <path d="M460 280 L 460 460" stroke="#ffd400" strokeWidth="4" />
              </>
            )}
          </g>
        )}

        {/* Computed route polyline */}
        {showRoute && (
          <path d="M150 380 Q 240 340 320 360 T 460 340 T 540 280 T 620 220 T 700 200"
                stroke="#1a73e8" strokeWidth="4" fill="none" opacity=".9" />
        )}
      </svg>

      {/* map controls (zoom + layers) */}
      <div style={{ position:"absolute", top:10, left:10, background:"#fff", border:"1px solid #ccc", borderRadius:4, display:"flex", flexDirection:"column", fontFamily:"sans-serif" }}>
        <button style={{ border:0, background:"#fff", width:28, height:28, cursor:"pointer", fontSize:18, borderBottom:"1px solid #eee" }}>+</button>
        <button style={{ border:0, background:"#fff", width:28, height:28, cursor:"pointer", fontSize:18, borderBottom:"1px solid #eee" }}>−</button>
        <button style={{ border:0, background:"#fff", width:28, height:28, cursor:"pointer" }}>
          <i className="bi bi-arrows-fullscreen" style={{ fontSize:13 }} />
        </button>
      </div>
      <div style={{ position:"absolute", top:10, right:10, background:"#fff", border:"1px solid #ccc", borderRadius:4, padding:6 }}>
        <i className="bi bi-layers" style={{ fontSize:18, color:"#444" }} />
      </div>
      <div style={{ position:"absolute", bottom:4, right:6, fontSize:11, color:"#444", background:"rgba(255,255,255,.7)", padding:"1px 4px" }}>
        <span style={{ color:"#0080ff" }}>Leaflet</span> | © OpenStreetMap contributors
      </div>
    </div>
  );
}

// Expose to other files
Object.assign(window, {
  STEPS, Navbar, PageHeader, WizardTabs, WizardCard,
  ProgressFooter, Alert, ResetBanner, LoadingModal,
  ResetConfirmModal, FauxMap,
});
