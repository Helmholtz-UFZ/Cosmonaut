/* eslint-disable */
// Wizard step pages — mirror cosmonaut_app/pages/*.py

const { useState: useStateP, useEffect: useEffectP, useRef: useRefP } = React;

// -----------------------------------------------------------------------------
// 1. Home (no job context)
// -----------------------------------------------------------------------------
function HomePage({ onCreate }) {
  return (
    <div style={{ margin:"12px", flex:1 }}>
      <div className="card shadow-sm">
        <div className="card-header">
          <h3 style={{ margin:0, fontWeight:500, fontSize:"1.75rem" }}>Welcome to COSMONAUT</h3>
        </div>
        <div className="card-body">
          <p className="text-muted" style={{ marginBottom:"1rem" }}>
            Create a new routing job and follow the steps to upload your data, select streets, and download navigation.
          </p>
          <button className="btn btn-primary" onClick={onCreate}>
            <i className="bi bi-rocket-takeoff" style={{ marginRight:8 }}></i>Create new job
          </button>
          <div className="text-muted small" style={{ marginTop:8 }}>
            Or load an existing job using the search bar in the navbar.
          </div>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// 2. User Information
// -----------------------------------------------------------------------------
function UserInfoPage({ jobId, email, setEmail, onNext }) {
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  return (
    <WizardCard stepId="user_info" jobId={jobId}
      footer={<ProgressFooter onNext={onNext} nextDisabled={!valid} />}>
      <p className="text-muted">Enter your email to receive notifications for this job.</p>
      <Alert kind="warning" icon="exclamation-triangle">
        <strong>Warning:</strong> Your email is visible from inside the UFZ network.
      </Alert>
      <label className="form-label" style={{ marginTop:8, fontSize:"0.875rem" }}>Email address</label>
      <input
        className={`form-control ${valid ? "is-valid" : ""}`}
        value={email}
        onChange={e => setEmail(e.target.value)}
        placeholder="you@ufz.de"
      />
      <div className="form-text">
        <i className="bi bi-shield-check" style={{ marginRight:4 }}></i>
        We never share your email.
      </div>
      {valid && (
        <div className="form-text" style={{ color:"#18bc9c", fontWeight:600, marginTop:4 }}>
          Looks good!
        </div>
      )}
    </WizardCard>
  );
}

// -----------------------------------------------------------------------------
// 3. Data Upload
// -----------------------------------------------------------------------------
function DataUploadPage({ jobId, state, setState, onPrev, onNext }) {
  const { epsg, membershipUploaded, predictorUploaded, opacity, streetStatus } = state;
  const epsgValid = /^\d{4,5}$/.test(epsg);
  const nextDisabled = !(membershipUploaded && predictorUploaded);

  const handleUploadMembership = () => {
    setState(s => ({ ...s, membershipUploaded: true, streetStatus: "BUILDING" }));
    setTimeout(() => setState(s => ({ ...s, streetStatus: "COMPLETED" })), 2200);
  };
  const handleUploadPredictor = () => setState(s => ({ ...s, predictorUploaded: true }));
  const handleDeleteMembership = () => setState(s => ({
    ...s, membershipUploaded: false, predictorUploaded: false, streetStatus: "PENDING",
  }));
  const handleDeletePredictor = () => setState(s => ({ ...s, predictorUploaded: false }));

  const streetMsg = {
    PENDING:   { txt: "Road network will be constructed in the background", cls: "text-muted" },
    BUILDING:  { txt: "Road network is being built…", cls: "text-info" },
    COMPLETED: { txt: "Road network is constructed", cls: "text-muted" },
    FAILED:    { txt: "Road network construction failed! Re-upload membership file.", cls: "text-danger" },
  }[streetStatus];

  return (
    <WizardCard stepId="data_upload" jobId={jobId}
      footer={<ProgressFooter onPrev={onPrev} onNext={onNext} nextDisabled={nextDisabled} />}>
      <p className="text-muted">Please enter a valid EPSG code and then upload your membership data file.</p>

      <label className="form-label" style={{ marginTop:8 }}>EPSG code</label>
      <input
        className={`form-control ${epsgValid ? "is-valid" : "is-invalid"}`}
        value={epsg}
        onChange={e => setState(s => ({ ...s, epsg: e.target.value }))}
        disabled={membershipUploaded}
      />
      <div className="form-text">Common choices: 4326, 25832, 3857, …</div>
      <div className="form-text" style={{ color:"#18bc9c", fontWeight:600 }}>EPSG accepted</div>

      <div style={{ margin:"14px 0 6px" }}>
        <button className="btn btn-primary"
                disabled={!epsgValid || membershipUploaded}
                onClick={handleUploadMembership}>
          <i className="bi bi-upload" style={{ marginRight:6 }}></i>Upload membership file
        </button>
      </div>
      <small className="text-muted">
        The membership file should be a CSV file with fuzzy cluster membership values.
        <i className="bi bi-info-circle" style={{ marginLeft:4 }}></i>
      </small>
      <div className="text-muted" style={{ marginTop:4 }}>{membershipUploaded ? "Uploaded" : "Not uploaded"}</div>
      <button className="btn btn-danger btn-sm" style={{ marginTop:8 }}
              disabled={!membershipUploaded} onClick={handleDeleteMembership}>
        <i className="bi bi-trash" style={{ marginRight:4 }}></i>Delete Membership
      </button>
      <div className={`${streetMsg.cls} small`} style={{ marginTop:6 }}>{streetMsg.txt}</div>

      <div style={{ marginTop:16, marginBottom:14 }}>
        <label className="form-label fw-bold">Map Opacity:</label>
        <input type="range" min="0" max="1" step="0.1"
               disabled={!membershipUploaded}
               value={opacity}
               onChange={e => setState(s => ({ ...s, opacity: parseFloat(e.target.value) }))}
               style={{ width:"100%" }} />
        <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, color:"#95a5a6" }}>
          <span>0%</span><span>50%</span><span>100%</span>
        </div>
      </div>

      <div style={{ margin:"8px 0 6px" }}>
        <button className="btn btn-primary"
                disabled={!membershipUploaded || predictorUploaded}
                onClick={handleUploadPredictor}>
          <i className="bi bi-upload" style={{ marginRight:6 }}></i>Upload predictor file
        </button>
      </div>
      <small className="text-muted">
        The predictor file should be a CSV file with comma-separated values.
        <i className="bi bi-info-circle" style={{ marginLeft:4 }}></i>
      </small>
      <div className="text-muted" style={{ marginTop:4 }}>{predictorUploaded ? "Uploaded" : "Not uploaded"}</div>
      <button className="btn btn-danger btn-sm" style={{ marginTop:8 }}
              disabled={!predictorUploaded} onClick={handleDeletePredictor}>
        <i className="bi bi-trash" style={{ marginRight:4 }}></i>Delete Predictor
      </button>
    </WizardCard>
  );
}

// -----------------------------------------------------------------------------
// 4. Street Selection
// -----------------------------------------------------------------------------
const ROAD_TYPES = [
  { id:"motorway",    label:"Motorway",     on:false },
  { id:"trunk",       label:"Trunk road",   on:false },
  { id:"primary",     label:"Primary road", on:true  },
  { id:"secondary",   label:"Secondary road",on:true },
  { id:"tertiary",    label:"Tertiary road",on:true  },
  { id:"unclassified",label:"Unclassified", on:false },
  { id:"residential", label:"Residential",  on:false },
  { id:"living",      label:"Living street",on:false },
  { id:"track",       label:"Track",        on:true  },
];

function StreetSelectionPage({ jobId, state, setState, onPrev, onNext }) {
  const { roadTypes, removedCount } = state;
  const selectAll = () => setState(s => ({ ...s, roadTypes: roadTypes.map(r => ({ ...r, on:true })) }));
  const selectNone = () => setState(s => ({ ...s, roadTypes: roadTypes.map(r => ({ ...r, on:false })) }));
  const toggle = id => setState(s => ({
    ...s,
    roadTypes: roadTypes.map(r => r.id === id ? { ...r, on:!r.on } : r),
  }));

  return (
    <WizardCard stepId="street_selection" jobId={jobId}
      footer={<ProgressFooter onPrev={onPrev} onNext={onNext} />}>
      <h5 style={{ fontSize:"1.1rem", fontWeight:500, marginBottom:".5rem" }}>Filter road types</h5>
      <p className="text-muted small">Toggles apply immediately. Disabled types are removed from the network and won't appear in the final route.</p>

      <div style={{ marginBottom:14 }}>
        <div className="form-label">Road type filter</div>
        <div style={{ display:"flex", gap:14, fontSize:13, marginBottom:8 }}>
          <a href="#" style={{ color:"#18bc9c" }} onClick={e => { e.preventDefault(); selectAll(); }}>
            <i className="bi bi-check2-square" style={{ marginRight:3 }}></i>Select all
          </a>
          <a href="#" style={{ color:"#18bc9c" }} onClick={e => { e.preventDefault(); selectNone(); }}>
            <i className="bi bi-x-circle" style={{ marginRight:3 }}></i>Select none
          </a>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:"10px 16px", fontSize:14 }}>
          {roadTypes.map(r => (
            <label key={r.id} className="form-switch">
              <input type="checkbox" checked={r.on} onChange={() => toggle(r.id)} />
              <span>{r.label}</span>
            </label>
          ))}
        </div>
      </div>

      <h5 style={{ fontSize:"1.1rem", fontWeight:500 }}>Edit individual roads</h5>
      <p className="text-muted small">Click roads on the map to mark them, then choose an action below.</p>
      <button className="btn btn-danger" style={{ width:"100%" }}>
        <i className="bi bi-eraser" style={{ marginRight:6 }}></i>Remove clicked roads
        <span className="badge bg-info" style={{ marginLeft:"auto" }}>Selected: 0</span>
      </button>
      <div className="text-muted small" style={{ marginTop:4 }}>Removes the roads you clicked on the map.</div>

      <div style={{ marginTop:14 }}>
        <div className="form-label">Removed roads</div>
        {removedCount > 0 ? (
          <div style={{ border:"1px solid #dee2e6", borderRadius:6, padding:"6px 10px", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <span>track #84761741</span><span style={{ color:"#e74c3c", cursor:"pointer" }}>×</span>
          </div>
        ) : <div className="text-muted small">No edits yet.</div>}
        <a href="#" style={{ color:"#18bc9c", fontSize:13 }}>
          <i className="bi bi-trash" style={{ marginRight:3 }}></i>Clear all
        </a>
      </div>

      <h5 style={{ fontSize:"1.1rem", fontWeight:500, marginTop:14 }}>Network connectivity</h5>
      <div style={{ color:"#f39c12", fontSize:14 }}>
        <i className="bi bi-exclamation-triangle" style={{ marginRight:4 }}></i>
        Road network might be disconnected
      </div>
      <button className="btn btn-secondary" style={{ width:"100%", marginTop:8 }}>
        <i className="bi bi-diagram-3" style={{ marginRight:6 }}></i>Keep largest network
      </button>
    </WizardCard>
  );
}

// -----------------------------------------------------------------------------
// 5. Routing Parameters
// -----------------------------------------------------------------------------
function RoutingParamsPage({ jobId, state, setState, onPrev, onNext }) {
  const { params, advancedOpen } = state;
  const setP = (k, v) => setState(s => ({ ...s, params: { ...s.params, [k]: v }}));

  return (
    <WizardCard stepId="routing_params" jobId={jobId}
      footer={<ProgressFooter onPrev={onPrev} onNext={onNext} />}>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"12px 16px" }}>
        <div>
          <label className="form-label">Segments per class</label>
          <input className="form-control is-valid" value={params.segments}
                 onChange={e => setP("segments", e.target.value)} />
          <div className="form-text">Must be between 1 and 10</div>
        </div>
        <div>
          <label className="form-label">Time limit [h]</label>
          <input className="form-control is-valid" value={params.timeLimit}
                 onChange={e => setP("timeLimit", e.target.value)} />
          <div className="form-text">Must be a positive number</div>
        </div>
        <div>
          <label className="form-label">Max distance</label>
          <input className="form-control is-valid" value={params.maxDistance}
                 onChange={e => setP("maxDistance", e.target.value)} />
          <div className="form-text">Must be a positive integer</div>
        </div>
        <div>
          <label className="form-label">Objective</label>
          <input className="form-control is-valid" value={params.objective}
                 onChange={e => setP("objective", e.target.value)} />
          <div className="form-text">Must be 'd' (distance) or 't' (time)</div>
        </div>
      </div>
      <div className="form-text" style={{ marginTop:4 }}>Objective: 'd' = max distance, 't' = time limit.</div>

      <div style={{ marginTop:8 }}>
        <label className="form-label">Number of points</label>
        <input className="form-control is-valid" value={params.numPoints}
               onChange={e => setP("numPoints", e.target.value)} />
        <div className="form-text">Number of points for HPE optimization</div>
      </div>

      <a href="#" className="btn btn-link"
         style={{ padding:0, marginTop:8 }}
         onClick={e => { e.preventDefault(); setState(s => ({ ...s, advancedOpen: !advancedOpen })); }}>
        {advancedOpen ? "Hide" : "Show"} advanced options {advancedOpen ? "▴" : "▾"}
      </a>
      {advancedOpen && (
        <div style={{ marginTop:8, padding:"12px", background:"#f8f9fa", borderRadius:6, fontSize:14 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"8px 14px" }}>
            <div><label className="form-label">Lower benefit limit</label><input className="form-control" value="0.1" readOnly /></div>
            <div><label className="form-label">Max ACO iteration</label><input className="form-control" value="100" readOnly /></div>
            <div><label className="form-label">Ant count</label><input className="form-control" value="20" readOnly /></div>
            <div><label className="form-label">Benefit type</label><input className="form-control" value="default" readOnly /></div>
            <div><label className="form-label">Goal ratio</label><input className="form-control" value="0.9" readOnly /></div>
            <div><label className="form-label">Use fixed seeds</label><input className="form-control" value="false" readOnly /></div>
          </div>
        </div>
      )}
    </WizardCard>
  );
}

// -----------------------------------------------------------------------------
// 6. Route Computation
// -----------------------------------------------------------------------------
function RouteComputationPage({ jobId, state, setState, onPrev, onNext }) {
  const { status, logs } = state;
  const startCompute = () => {
    setState(s => ({ ...s, status:"RUNNING", logs: [] }));
    const lines = [
      "[15:57:11,556] INFO  in routing_tasks: Starting routing job computation for job_id=" + jobId,
      "[15:57:11,573] INFO  in street_selector: Projected 271 features to EPSG 25832",
      "[15:57:54,816] INFO  in routing_tasks: Starting post-processing for job " + jobId,
      "[15:57:54,816] INFO  in cosmonaut_job: Creating QR code for routing job " + jobId,
      "[15:57:54,816] DEBUG in navigation_routing: RouteCreator initialized.",
      "[15:57:54,816] INFO  in navigation_routing: Starting GPX creation process.",
      "[15:57:54,822] DEBUG in navigation_routing: GPX file created at /work_dir/" + jobId + "/route.gpx.",
      "[15:57:54,862] DEBUG in navigation_routing: QR code created and saved.",
      "[15:57:54,863] INFO  in cosmonaut_job: Save job " + jobId,
    ];
    lines.forEach((line, i) => setTimeout(() => {
      setState(s => ({ ...s, logs: [...s.logs, line] }));
      if (i === lines.length - 1) setState(s => ({ ...s, status:"COMPLETED" }));
    }, 350 + i * 250));
  };

  const statusBadge = {
    PENDING:   <span className="badge bg-warning">PENDING</span>,
    RUNNING:   <span className="badge bg-primary">RUNNING</span>,
    COMPLETED: <span className="badge bg-success">COMPLETED</span>,
    FAILED:    <span className="badge bg-danger">FAILED</span>,
  }[status];

  return (
    <WizardCard stepId="route_computation" jobId={jobId}
      footer={<ProgressFooter onPrev={onPrev} onNext={status === "COMPLETED" ? onNext : null} nextDisabled={status !== "COMPLETED"} />}>
      <p className="text-muted">Monitor the routing computation status and manage the computation job.</p>
      <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
        <strong>Job Status:</strong> {statusBadge}
      </div>
      {status === "PENDING" && (
        <button className="btn btn-primary" onClick={startCompute}>
          <i className="bi bi-play" style={{ marginRight:6 }}></i>Start Computation
        </button>
      )}
      {status !== "PENDING" && (
        <button className="btn btn-warning" onClick={startCompute}>
          <i className="bi bi-arrow-clockwise" style={{ marginRight:6 }}></i>Restart Computation
        </button>
      )}
      <Alert kind="info" icon="info-circle">This job will be automatically deleted in 60 day(s).</Alert>

      <h5 style={{ fontSize:"1.05rem", fontWeight:500, marginTop:14 }}>Celery Worker Information</h5>
      <div style={{ border:"1px solid #dee2e6", borderRadius:6, padding:"10px 12px", fontSize:14, lineHeight:1.8 }}>
        <div><strong>Worker Availability:</strong> 1 worker(s) available</div>
        <div><strong>Task Celery Status:</strong> {status === "COMPLETED" ? "SUCCESS" : status === "RUNNING" ? "STARTED" : "PENDING"}</div>
        <div><strong>Worker Name:</strong> worker@leih543494L</div>
      </div>

      <h5 style={{ fontSize:"1.05rem", fontWeight:500, marginTop:14 }}>Computation Logs</h5>
      <pre style={{
        background:"#f8f9fa", border:"1px solid #dee2e6", borderRadius:6,
        padding:"10px 12px", fontSize:12, lineHeight:1.5,
        maxHeight:220, overflowY:"auto", whiteSpace:"pre-wrap", margin:0,
      }}>
        {logs.length ? logs.join("\n") : "No logs yet — start the computation."}
      </pre>
    </WizardCard>
  );
}

// -----------------------------------------------------------------------------
// 7. Route Download
// -----------------------------------------------------------------------------
function RouteDownloadPage({ jobId, onPrev }) {
  return (
    <WizardCard stepId="route_download" jobId={jobId}
      footer={<ProgressFooter onPrev={onPrev} />}>
      <p>Scan the QR code to download the GPX file of the final route.</p>
      <div style={{ display:"flex", justifyContent:"center", margin:"14px 0" }}>
        {/* Fake QR pattern */}
        <svg width="200" height="200" viewBox="0 0 25 25" shapeRendering="crispEdges">
          <rect width="25" height="25" fill="#fff"/>
          {Array.from({ length: 25 }).map((_, y) =>
            Array.from({ length: 25 }).map((__, x) => {
              const seed = (x * 73 + y * 37 + x * y * 13) % 17;
              const corner = (x < 7 && y < 7) || (x > 17 && y < 7) || (x < 7 && y > 17);
              const cornerEye = corner && ((x === 0 || x === 6 || y === 0 || y === 6 || (x >= 2 && x <= 4 && y >= 2 && y <= 4)));
              const fill = corner ? cornerEye : seed < 8;
              return fill ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="#000" /> : null;
            })
          )}
        </svg>
      </div>
      <div style={{ display:"flex", flexDirection:"column", gap:8, alignItems:"center" }}>
        <button className="btn btn-primary"><i className="bi bi-download" style={{ marginRight:6 }}></i>Download GPX File</button>
        <button className="btn btn-secondary"><i className="bi bi-folder" style={{ marginRight:6 }}></i>Download work_dir</button>
        <a href="#" style={{ color:"#e83e8c", fontFamily:"var(--cn-font-mono)", fontSize:14, marginTop:6 }}>
          http://localhost:8080/download/{jobId}/route.gpx
        </a>
      </div>
    </WizardCard>
  );
}

Object.assign(window, {
  HomePage, UserInfoPage, DataUploadPage, StreetSelectionPage,
  RoutingParamsPage, RouteComputationPage, RouteDownloadPage,
});
