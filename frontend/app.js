// Urban Flood Nowcasting & Response System — Frontend Interactive GIS Dashboard

let currentStep = 0;
let isPlaying = false;
let playInterval = null;
let gridState = [];
let roadState = [];
let sensorState = [];
let drainageState = { nodes: [], edges: [] };
let activeRoute = null;

// Layer visibility toggles
const layers = {
  water: true,
  dem: true,
  flow: true,
  drainage: true,
  roads: true,
  sensors: true,
};

// Canvas Setup
const canvas = document.getElementById("gisCanvas");
const ctx = canvas.getContext("2d");
const GRID_SIZE = 20;
const CELL_PX = canvas.width / GRID_SIZE; // 32px per cell

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadCatchmentData();
  fetchState();
});

function setupEventListeners() {
  // Layer toggles
  document.querySelectorAll(".layer-toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const layer = btn.dataset.layer;
      layers[layer] = !layers[layer];
      btn.classList.toggle("active", layers[layer]);
      renderMap();
    });
  });

  // Playback controls
  document.getElementById("btnRunStep").addEventListener("click", stepSimulation);
  document.getElementById("btnStep").addEventListener("click", stepSimulation);
  document.getElementById("btnPlayPause").addEventListener("click", togglePlay);
  document.getElementById("btnResetSim").addEventListener("click", resetSimulation);

  // Safe Route Planner
  document.getElementById("btnCalculateRoute").addEventListener("click", calculateSafeRoute);

  // Fault Injections
  document.getElementById("btnFaultSpike").addEventListener("click", () => injectFault("sensor_spike", 1));
  document.getElementById("btnFaultDisconnect").addEventListener("click", () => injectFault("sensor_disconnect", 2));
  document.getElementById("btnFaultBlockage").addEventListener("click", () => injectFault("drain_blockage", 3, 0.3));
  document.getElementById("btnRestoreAll").addEventListener("click", restoreAllFaults);

  // Scenario change
  document.getElementById("scenarioSelect").addEventListener("change", () => {
    resetSimulation();
  });
}

async function loadCatchmentData() {
  try {
    const res = await fetch("/api/drainage/network");
    if (res.ok) {
      drainageState = await res.json();
    }
  } catch (err) {
    console.error("Failed to load drainage network:", err);
  }
}

async function fetchState() {
  try {
    const [gridRes, roadsRes, sensorsRes, diagRes, eventsRes] = await Promise.all([
      fetch("/api/flood/grid"),
      fetch("/api/flood/roads"),
      fetch("/api/sensors"),
      fetch("/api/diagnostics/mass_balance"),
      fetch("/api/diagnostics/events"),
    ]);

    if (gridRes.ok) gridState = await gridRes.json();
    if (roadsRes.ok) roadState = await roadsRes.json();
    if (sensorsRes.ok) sensorState = await sensorsRes.json();

    if (diagRes.ok) {
      const diag = await diagRes.json();
      updateDiagnosticsUI(diag);
    }

    if (eventsRes.ok) {
      const events = await eventsRes.json();
      updateEventsUI(events);
    }

    updateSensorsUI();
    updateRoadsUI();
    renderMap();

    if (activeRoute) {
      calculateSafeRoute();
    }
  } catch (err) {
    console.error("Error fetching simulation state:", err);
  }
}

async function stepSimulation() {
  const scenario = document.getElementById("scenarioSelect").value;
  try {
    const res = await fetch(`/api/scenarios/step?scenario=${scenario}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      currentStep = data.step;
      document.getElementById("currentStepIndicator").innerText = 
        `STEP ${currentStep} / TIME: 00:${String(currentStep).padStart(2, '0')}:00`;
      document.getElementById("timelineSlider").value = currentStep;
      await fetchState();
    }
  } catch (err) {
    console.error("Step error:", err);
  }
}

function togglePlay() {
  isPlaying = !isPlaying;
  const btn = document.getElementById("btnPlayPause");
  if (isPlaying) {
    btn.innerText = "⏸ Pause";
    btn.classList.add("btn-danger");
    playInterval = setInterval(async () => {
      if (currentStep >= 10) {
        togglePlay();
        return;
      }
      await stepSimulation();
    }, 1200);
  } else {
    btn.innerText = "▶ Play";
    btn.classList.remove("btn-danger");
    if (playInterval) clearInterval(playInterval);
  }
}

async function resetSimulation() {
  if (isPlaying) togglePlay();
  await fetch("/api/scenarios/reset", { method: "POST" });
  currentStep = 0;
  document.getElementById("currentStepIndicator").innerText = "STEP 0 / TIME: 00:00:00";
  document.getElementById("timelineSlider").value = 0;
  activeRoute = null;
  document.getElementById("routeEta").innerText = "-- min";
  document.getElementById("routeExposure").innerText = "0.0 (SAFE)";
  document.getElementById("routeExposure").style.color = "var(--accent-green)";
  await fetchState();
}

async function injectFault(faultType, targetId, value = null) {
  try {
    const res = await fetch("/api/faults/inject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fault_type: faultType, target_id: targetId, value: value }),
    });
    if (res.ok) {
      await fetchState();
    }
  } catch (err) {
    console.error("Fault injection failed:", err);
  }
}

async function restoreAllFaults() {
  await injectFault("sensor_restore", 1);
  await injectFault("sensor_restore", 2);
  await injectFault("drain_restore", 3);
  await fetchState();
}

async function calculateSafeRoute() {
  const origin = document.getElementById("routeOrigin").value;
  const destination = document.getElementById("routeDestination").value;
  const mode = document.getElementById("routeMode").value;

  try {
    const res = await fetch("/api/routes/safe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination, mode }),
    });

    if (res.ok) {
      const data = await res.json();
      activeRoute = data;
      if (data.success) {
        document.getElementById("routeEta").innerText = `${data.eta_minutes} min`;
        const exp = document.getElementById("routeExposure");
        exp.innerText = `${data.flood_exposure_score} (${data.flood_exposure_score > 3 ? 'HIGH' : data.flood_exposure_score > 0 ? 'WATCH' : 'SAFE'})`;
        exp.style.color = data.flood_exposure_score > 3 ? 'var(--accent-red)' : data.flood_exposure_score > 0 ? 'var(--accent-yellow)' : 'var(--accent-green)';
        document.getElementById("routeConfidence").innerText = `${Math.round(data.confidence * 100)}%`;
      } else {
        document.getElementById("routeEta").innerText = "BLOCKED";
        document.getElementById("routeExposure").innerText = "UNSAFE";
        document.getElementById("routeExposure").style.color = "var(--accent-red)";
      }
      renderMap();
    }
  } catch (err) {
    console.error("Route calculation error:", err);
  }
}

function updateDiagnosticsUI(diag) {
  document.getElementById("statInflow").innerText = `${diag.input_total_m3.toFixed(1)} m³`;
  document.getElementById("statStorage").innerText = `${diag.storage_total_m3.toFixed(1)} m³`;
  document.getElementById("statDrained").innerText = `${diag.drained_total_m3.toFixed(1)} m³`;
  document.getElementById("statOutflow").innerText = `${diag.boundary_outflow_m3.toFixed(1)} m³`;
  
  const errEl = document.getElementById("statError");
  errEl.innerText = `${diag.balance_error_m3.toFixed(4)} m³ (${diag.status})`;
  errEl.style.color = diag.status === "PASS" ? "var(--accent-green)" : "var(--accent-red)";

  const mbPill = document.getElementById("massBalancePill");
  document.getElementById("mbStatusText").innerText = `${diag.status} (${diag.balance_error_m3.toFixed(4)} m³)`;
  mbPill.className = `status-pill ${diag.status === 'PASS' ? '' : 'fail'}`;
}

function updateSensorsUI() {
  const container = document.getElementById("sensorListContainer");
  container.innerHTML = sensorState.map(s => {
    const badgeClass = `badge-${s.status.toLowerCase()}`;
    const reading = s.last_reading_cm !== null ? `${s.last_reading_cm} cm` : "--";
    return `
      <div class="sensor-item">
        <div>
          <div style="font-weight: 600; color: var(--text-primary);">${s.name}</div>
          <div style="font-size: 0.7rem; color: var(--text-muted);">${s.sensor_type.toUpperCase()} | Bias: ${s.current_bias_cm > 0 ? '+' : ''}${s.current_bias_cm}cm | Batt: ${s.battery}%</div>
        </div>
        <div style="text-align: right;">
          <div style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-cyan);">${reading}</div>
          <span class="sensor-badge ${badgeClass}">${s.status}</span>
        </div>
      </div>
    `;
  }).join("");
}

function updateRoadsUI() {
  const container = document.getElementById("roadListContainer");
  const riskyRoads = roadState.filter(r => r.predicted_depth_cm > 1.0);
  if (riskyRoads.length === 0) {
    container.innerHTML = `<div style="font-size: 0.75rem; color: var(--accent-green); padding: 6px;">All arterial roads are clear and safe.</div>`;
    return;
  }
  container.innerHTML = riskyRoads.map(r => `
    <div class="sensor-item">
      <div>
        <div style="font-weight: 600;">${r.name} (${r.from_node} ↔ ${r.to_node})</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">Conf: ${Math.round(r.confidence * 100)}% (${r.data_quality})</div>
      </div>
      <div style="text-align: right;">
        <div style="font-family: var(--font-mono); font-weight: 700;">${r.predicted_depth_cm} cm</div>
        <span class="sensor-badge" style="background: ${r.risk_level === 'UNSAFE' ? 'rgba(239,68,68,0.2)' : r.risk_level === 'HIGH' ? 'rgba(249,115,22,0.2)' : 'rgba(245,158,11,0.2)'}; color: ${r.risk_level === 'UNSAFE' ? 'var(--accent-red)' : r.risk_level === 'HIGH' ? 'var(--accent-orange)' : 'var(--accent-yellow)'}">${r.risk_level}</span>
      </div>
    </div>
  `).join("");
}

function updateEventsUI(events) {
  const ticker = document.getElementById("eventTicker");
  if (events.length > 0) {
    const recent = events.slice(-8).reverse();
    ticker.innerHTML = recent.map(e => `
      <div class="ticker-item ${e.event_type.includes('ANOMALY') || e.event_type.includes('FAULT') ? 'warn' : ''}">
        [T+${e.step}m] <strong>${e.event_type}</strong>: ${JSON.stringify(e.payload)}
      </div>
    `).join("");
  }
}

// -------------------------------------------------------------
// Canvas GIS Renderer
// -------------------------------------------------------------
function renderMap() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 1. Draw DEM Terrain elevation
  if (layers.dem && gridState.length > 0) {
    gridState.forEach(cell => {
      const x = cell.col * CELL_PX;
      const y = cell.row * CELL_PX;
      // Map elevation 10..32m to dark topographic gray-green gradient
      const normElev = (cell.elevation - 10.0) / 22.0;
      const gray = Math.floor(18 + normElev * 30);
      ctx.fillStyle = `rgb(${gray}, ${gray + 6}, ${gray + 12})`;
      ctx.fillRect(x, y, CELL_PX, CELL_PX);

      // Subtle contour grid border
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.strokeRect(x, y, CELL_PX, CELL_PX);
    });
  }

  // 2. Draw Flood Water Layer (fused depth)
  if (layers.water && gridState.length > 0) {
    gridState.forEach(cell => {
      const d = cell.fused_depth_cm;
      if (d > 0.5) {
        const x = cell.col * CELL_PX;
        const y = cell.row * CELL_PX;
        
        let color = "rgba(56, 189, 248, 0.35)"; // Safe
        if (d >= 30.0) color = "rgba(239, 68, 68, 0.85)"; // Unsafe
        else if (d >= 15.0) color = "rgba(249, 115, 22, 0.75)"; // High
        else if (d >= 5.0) color = "rgba(245, 158, 11, 0.60)"; // Watch

        ctx.fillStyle = color;
        ctx.fillRect(x, y, CELL_PX, CELL_PX);
      }
    });
  }

  // 3. Draw Drainage Network (Pipes & Inlets)
  if (layers.drainage && drainageState.nodes.length > 0) {
    // Draw pipe edges
    ctx.strokeStyle = "rgba(99, 102, 241, 0.6)";
    ctx.lineWidth = 3;
    ctx.setLineDash([4, 4]);
    drainageState.edges.forEach(edge => {
      const n1 = drainageState.nodes.find(n => n.node_id === edge.from_node);
      const n2 = drainageState.nodes.find(n => n.node_id === edge.to_node);
      if (n1 && n2) {
        const x1 = n1.col * CELL_PX + CELL_PX / 2;
        const y1 = n1.row * CELL_PX + CELL_PX / 2;
        const x2 = n2.col * CELL_PX + CELL_PX / 2;
        const y2 = n2.row * CELL_PX + CELL_PX / 2;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
    });
    ctx.setLineDash([]);

    // Draw Inlets / Manholes
    drainageState.nodes.forEach(node => {
      const cx = node.col * CELL_PX + CELL_PX / 2;
      const cy = node.row * CELL_PX + CELL_PX / 2;
      ctx.fillStyle = node.capacity_factor < 0.7 ? "#ef4444" : "#6366f1";
      ctx.beginPath();
      ctx.arc(cx, cy, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }

  // 4. Draw Road Network & Junction Nodes
  if (layers.roads) {
    // 4x4 Junctions
    for (let jr = 0; jr < 4; jr++) {
      for (let jc = 0; jc < 4; jc++) {
        const jid = `J${jr * 4 + jc + 1}`;
        const r = jr * 6 + 1;
        const c = jc * 6 + 1;
        const jx = c * CELL_PX + CELL_PX / 2;
        const jy = r * CELL_PX + CELL_PX / 2;

        // Junction Node Marker
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(jx, jy, 5, 0, Math.PI * 2);
        ctx.fill();

        // Node Label
        ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
        ctx.font = "10px JetBrains Mono";
        ctx.fillText(jid, jx + 7, jy + 3);
      }
    }

    // Road segments
    roadState.forEach(road => {
      // Parse u and v
      const uNum = parseInt(road.from_node.replace("J", "")) - 1;
      const vNum = parseInt(road.to_node.replace("J", "")) - 1;
      const uR = Math.floor(uNum / 4) * 6 + 1;
      const uC = (uNum % 4) * 6 + 1;
      const vR = Math.floor(vNum / 4) * 6 + 1;
      const vC = (vNum % 4) * 6 + 1;

      const x1 = uC * CELL_PX + CELL_PX / 2;
      const y1 = uR * CELL_PX + CELL_PX / 2;
      const x2 = vC * CELL_PX + CELL_PX / 2;
      const y2 = vR * CELL_PX + CELL_PX / 2;

      let strokeColor = "rgba(255, 255, 255, 0.4)";
      if (road.risk_level === "UNSAFE") strokeColor = "#ef4444";
      else if (road.risk_level === "HIGH") strokeColor = "#f97316";
      else if (road.risk_level === "WATCH") strokeColor = "#f59e0b";

      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = road.risk_level === "UNSAFE" ? 4 : 2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    });
  }

  // 5. Draw Active Safe Route Highlight
  if (activeRoute && activeRoute.success && activeRoute.path_nodes.length > 1) {
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 6;
    ctx.shadowColor = "#38bdf8";
    ctx.shadowBlur = 12;
    ctx.beginPath();

    for (let i = 0; i < activeRoute.path_nodes.length; i++) {
      const nId = activeRoute.path_nodes[i];
      const nNum = parseInt(nId.replace("J", "")) - 1;
      const r = Math.floor(nNum / 4) * 6 + 1;
      const c = (nNum % 4) * 6 + 1;
      const x = c * CELL_PX + CELL_PX / 2;
      const y = r * CELL_PX + CELL_PX / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0; // reset
  }

  // 6. Draw Sensors
  if (layers.sensors && sensorState.length > 0) {
    sensorState.forEach(s => {
      const r = Math.floor(s.cell_id / GRID_SIZE);
      const c = s.cell_id % GRID_SIZE;
      const sx = c * CELL_PX + CELL_PX / 2;
      const sy = r * CELL_PX + CELL_PX / 2;

      let color = "#10b981"; // ONLINE
      if (s.status === "STALE") color = "#f59e0b";
      else if (s.status === "OFFLINE") color = "#ef4444";
      else if (s.status === "INVALID") color = "#a855f7";

      // Pulsing outer halo
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(sx, sy, 8, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(sx, sy, 4, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px Inter";
      ctx.fillText(`S${s.sensor_id}`, sx - 6, sy - 10);
    });
  }
}
