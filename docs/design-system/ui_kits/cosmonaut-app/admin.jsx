/* eslint-disable */
// Admin pages — JobManager, WorkerManagement, Logs.

function JobManager({ onOpenJob }) {
  const rows = [
    { id:"b56ee901", status:"PENDING",   color:"#f39c12", date:"2026-04-22", submitted:"No"  },
    { id:"2f1583ca", status:"COMPLETED", color:"#3498db", date:"2026-04-22", submitted:"Yes" },
    { id:"cc4e7a12", status:"RUNNING",   color:"#2c3e50", date:"2026-04-22", submitted:"No"  },
    { id:"9a2d44c0", status:"FAILED",    color:"#e74c3c", date:"2026-04-21", submitted:"No"  },
    { id:"7f8b1a55", status:"COMPLETED", color:"#3498db", date:"2026-04-21", submitted:"Yes" },
  ];
  return (
    <div style={{ flex:1, overflowY:"auto" }}>
      <PageHeader title="Job Manager" subtitle="Centralized management of all COSMONAUT jobs">
        <div style={{ display:"flex", justifyContent:"flex-end", gap:8 }}>
          <button className="btn btn-warning btn-sm"><i className="bi bi-recycle" style={{ marginRight:4 }}></i>Clean</button>
          <button className="btn btn-danger btn-sm"><i className="bi bi-trash" style={{ marginRight:4 }}></i>Delete Selection</button>
          <button className="btn btn-primary btn-sm"><i className="bi bi-arrow-clockwise" style={{ marginRight:4 }}></i>Refresh Jobs</button>
        </div>
      </PageHeader>
      <div style={{ margin:"0 12px 12px 12px", background:"#fff", border:"1px solid #dee2e6", borderRadius:6 }}>
        <table style={{ width:"100%", borderCollapse:"separate", borderSpacing:0, fontSize:14 }}>
          <thead>
            <tr style={{ background:"#f8f9fa", color:"#212529" }}>
              <th style={{ width:36, padding:"10px 12px", borderBottom:"2px solid #dee2e6" }}>
                <input type="checkbox" />
              </th>
              <th style={{ textAlign:"left", padding:"10px 12px", borderBottom:"2px solid #dee2e6", fontWeight:600 }}>Job ID</th>
              <th style={{ textAlign:"left", padding:"10px 12px", borderBottom:"2px solid #dee2e6", fontWeight:600 }}>Status</th>
              <th style={{ textAlign:"left", padding:"10px 12px", borderBottom:"2px solid #dee2e6", fontWeight:600 }}>Start Date</th>
              <th style={{ textAlign:"left", padding:"10px 12px", borderBottom:"2px solid #dee2e6", fontWeight:600 }}>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} style={{ background: i % 2 ? "#f8f9fa" : "#fff" }}>
                <td style={{ padding:"10px 12px" }}><input type="checkbox" /></td>
                <td style={{ padding:"10px 12px" }}>
                  <a href="#" onClick={(e)=>{ e.preventDefault(); onOpenJob && onOpenJob(r.id); }}
                     style={{ color:"#18bc9c", fontFamily:"var(--cn-font-mono)", textDecoration:"underline" }}>
                    {r.id}
                  </a>
                </td>
                <td style={{ padding:0, background:r.color, color:"#fff", fontWeight:600 }}>
                  <div style={{ padding:"10px 12px" }}>{r.status}</div>
                </td>
                <td style={{ padding:"10px 12px" }}>{r.date}</td>
                <td style={{ padding:"10px 12px" }}>{r.submitted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function WorkerManagement() {
  return (
    <div style={{ flex:1, overflowY:"auto" }}>
      <PageHeader title="Worker Management" subtitle="Monitor and control Celery background workers">
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <button className="btn btn-dark btn-sm" style={{ background:"#2c3e50" }}>
            <i className="bi bi-arrow-clockwise" style={{ marginRight:4 }}></i>Refresh
          </button>
          <button className="btn btn-success btn-sm">
            <i className="bi bi-play" style={{ marginRight:4 }}></i>Submit Test Task
          </button>
          <span style={{ color:"#95a5a6", fontSize:14, marginLeft:8 }}>Last refresh: 16:06:42</span>
        </div>
      </PageHeader>
      <div style={{ margin:"0 12px 12px", padding:"12px 16px", border:"1px solid #dee2e6", borderRadius:6, background:"#fff" }}>
        <strong>worker@leih543494L</strong>
        <div className="text-muted" style={{ marginTop:4, fontSize:14 }}>Active: 0 | Reserved: 0 | Scheduled: 0</div>
      </div>
      {["Active Tasks", "Reserved Tasks", "Scheduled Tasks", "Revoked Tasks"].map(t => (
        <div key={t} className="card shadow-sm" style={{ margin:"0 12px 16px" }}>
          <div className="card-body">
            <h4 style={{ margin:"0 0 .25rem", fontSize:"1.25rem", fontWeight:500 }}>{t}</h4>
            <p className="text-muted small" style={{ marginBottom:".75rem" }}>
              {t === "Active Tasks" && "Currently running tasks on workers"}
              {t === "Reserved Tasks" && "Tasks claimed by workers but not yet started"}
              {t === "Scheduled Tasks" && "Tasks waiting for their scheduled run time"}
              {t === "Revoked Tasks" && "Tasks that have been cancelled"}
            </p>
            <div style={{ border:"1px solid #dee2e6", borderRadius:6 }}>
              <table style={{ width:"100%", borderCollapse:"separate", borderSpacing:0, fontSize:13 }}>
                <thead>
                  <tr style={{ background:"#f8f9fa" }}>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Task ID</th>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Task Name</th>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Worker</th>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Start Time</th>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Duration</th>
                    <th style={{ padding:"8px 12px", textAlign:"left", borderBottom:"1px solid #dee2e6", fontWeight:600 }}>Job ID</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td colSpan="6" style={{ padding:"40px 12px", textAlign:"center", color:"#95a5a6" }}>
                    No Rows To Show
                  </td></tr>
                </tbody>
              </table>
            </div>
            <button className="btn btn-danger" style={{ marginTop:12, opacity:.6 }} disabled>
              <i className="bi bi-x-octagon" style={{ marginRight:6 }}></i>
              {t === "Active Tasks" ? "Kill Selected Task" : "Cancel Selected Task"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function LogsPage() {
  const [levels, setLevels] = React.useState(["Debug", "Info", "Warning", "Error", "Critical"]);
  const [exclude, setExclude] = React.useState(["beat", "layout", "db_manager"]);
  return (
    <div style={{ flex:1, overflowY:"auto" }}>
      <PageHeader title="View logs" subtitle="Show logs of the webserver">
        <div style={{ display:"grid", gridTemplateColumns:"1fr 2fr auto", gap:16 }}>
          <div>
            <label className="form-label">Select Date</label>
            <input className="form-control" type="date" defaultValue="2026-04-22" />
          </div>
          <div>
            <label className="form-label">Time Range</label>
            <div style={{ display:"flex", gap:6, alignItems:"center" }}>
              <span>From</span>
              <input className="form-control" value="15" style={{ width:60 }} readOnly />:
              <input className="form-control" value="06" style={{ width:60 }} readOnly />
              <span>To</span>
              <input className="form-control" value="16" style={{ width:60 }} readOnly />:
              <input className="form-control" value="06" style={{ width:60 }} readOnly />
            </div>
          </div>
          <div>
            <label className="form-label">Live</label>
            <label className="form-switch"><input type="checkbox" defaultChecked /><span>Auto-refresh</span></label>
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16, marginTop:12 }}>
          <div>
            <label className="form-label">Log Levels</label>
            <div style={{ display:"flex", flexWrap:"wrap", gap:6, padding:"6px 8px", border:"1px solid #dee2e6", borderRadius:6, minHeight:38 }}>
              {levels.map(l => (
                <span key={l} style={{ background:"#fff", border:"1px solid #3498db", color:"#3498db", borderRadius:3, padding:"1px 8px", fontSize:13, display:"inline-flex", alignItems:"center", gap:4 }}>
                  <span style={{ color:"#3498db" }}>×</span>{l}
                </span>
              ))}
            </div>
          </div>
          <div>
            <label className="form-label">PID</label>
            <div style={{ display:"flex", gap:6, alignItems:"center" }}>
              <label className="form-switch"><input type="checkbox" /><span>Filter by PID</span></label>
              <input className="form-control" placeholder="Process ID" disabled />
            </div>
          </div>
          <div>
            <label className="form-label">Exclude Modules</label>
            <div style={{ display:"flex", flexWrap:"wrap", gap:6, padding:"6px 8px", border:"1px solid #dee2e6", borderRadius:6, minHeight:38 }}>
              {exclude.map(l => (
                <span key={l} style={{ background:"#fff", border:"1px solid #3498db", color:"#3498db", borderRadius:3, padding:"1px 8px", fontSize:13, display:"inline-flex", alignItems:"center", gap:4 }}>
                  <span style={{ color:"#3498db" }}>×</span>{l}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div style={{ display:"flex", justifyContent:"flex-end", marginTop:14 }}>
          <button className="btn btn-secondary">Refresh</button>
        </div>
      </PageHeader>
      <div style={{ margin:"0 12px 12px", padding:"14px 16px", background:"#f8f9fa", border:"1px solid #dee2e6", borderRadius:6, color:"#212529", fontSize:14 }}>
        Live mode active — waiting for first refresh…
      </div>
    </div>
  );
}

function DocumentationPage() {
  return (
    <div style={{ flex:1, overflowY:"auto", padding:"16px 24px" }}>
      <h2 style={{ fontWeight:500 }}>Documentation</h2>
      <p className="text-muted">User documentation aggregated from all wizard pages. Markdown rendered server-side from docstrings.</p>
      <div className="card shadow-sm">
        <div className="card-body">
          <h3 style={{ fontSize:"1.5rem", fontWeight:500 }}>Welcome to COSMONAUT</h3>
          <p>COSMONAUT is the starting point for creating optimized navigation routes based on cosmic ray neutron sensor measurement locations.</p>
          <p>Each job is assigned a unique identifier that tracks your data, route selections, and final navigation output through the entire workflow.</p>

          <h3 style={{ fontSize:"1.5rem", fontWeight:500, marginTop:16 }}>Upload classification data</h3>
          <ol>
            <li><strong>Specify EPSG Code</strong>: Enter the coordinate reference system (CRS) of your data.</li>
            <li><strong>Upload Membership File</strong>: Drag and drop or select a CSV/TXT file containing your membership data.</li>
            <li><strong>Upload Predictor File</strong>: Upload a CSV file containing the predictor data.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { JobManager, WorkerManagement, LogsPage, DocumentationPage });
