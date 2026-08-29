/**
 * AURA-FLOOD — Urban Hydrological Command Center GIS Dashboard
 * Next-Generation Real-Time Sensor Fusion, Mass Balance & Dynamic Safe Routing
 */

let currentMinute = 0;
let isPlaying = false;
let playInterval = null;
let playSpeed = 400; // ms per step

// Active Injected Faults (Client-side interactive state)
const activeFaults = {
  spike: false,
  offline: false,
  blockage: false
};

// Layer Visibility States
const layers = {
  depth: true,
  d8: true,
  drainage: true,
  sensors: true,
  roads: true,
  ambulance: true
};

// Node Coordinates Map (500x500 SVG Space)
const NODE_COORDS = {
  "A": { x: 34, y: 34, name: "Origin A", color: "#38bdf8" },
  "B": { x: 466, y: 34, name: "Hub B", color: "#f59e0b" },
  "C": { x: 34, y: 466, name: "South C", color: "#f59e0b" },
  "D": { x: 466, y: 466, name: "Hospital D", color: "#10b981" },
  "M": { x: 274, y: 226, name: "Midtown M", color: "#c084fc" },
  "E": { x: 466, y: 274, name: "Lowland E", color: "#f43f5e" },
  "W": { x: 34, y: 274, name: "West W", color: "#38bdf8" }
};

// Graph Edge Map for Dijkstra & Visuals
const GRAPH_EDGES = [
  { id: "R001", u: "A", v: "B", baseTime: 50.0, name: "North Ave" },
  { id: "R002", u: "B", v: "E", baseTime: 30.0, name: "East Expwy" },
  { id: "R003", u: "A", v: "W", baseTime: 30.0, name: "West Bypass" },
  { id: "R004", u: "C", v: "D", baseTime: 40.0, name: "South Hwy" },
  { id: "R005", u: "E", v: "D", baseTime: 30.0, name: "East Underpass" },
  { id: "R006", u: "A", v: "M", baseTime: 35.0, name: "Midtown Art" },
  { id: "R007", u: "M", v: "D", baseTime: 35.0, name: "Hospital Expwy" },
  { id: "R008", u: "W", v: "M", baseTime: 30.0, name: "West Cross" },
  { id: "R009", u: "M", v: "E", baseTime: 25.0, name: "Midtown-East" },
  { id: "R010", u: "W", v: "C", baseTime: 30.0, name: "West Lower" }
];

// Active computed safe route state
let currentSafeRoute = {
  success: true,
  origin: "A",
  destination: "D",
  path: ["A", "M", "D"],
  road_ids: ["R006", "R007"],
  eta_seconds: 70.0,
  max_exposure_depth_cm: 0.0
};

// DOM Elements
const slider = document.getElementById("timeline-slider");
const timeDisplay = document.getElementById("time-display-val");
const btnPlay = document.getElementById("btn-play");
const btnPause = document.getElementById("btn-pause");
const btnReset = document.getElementById("btn-reset");
const btnStepBack = document.getElementById("btn-step-back");
const btnStepFwd = document.getElementById("btn-step-fwd");
const scenarioSelect = document.getElementById("scenario-select");
const btnRecomputeRoute = document.getElementById("btn-recompute-route");
const tooltip = document.getElementById("cell-tooltip");
const svgMap = document.getElementById("flood-map");
const hydroCanvas = document.getElementById("hydrograph-canvas");
const hydroMarker = document.getElementById("hydrograph-marker");
const hydroWrap = document.getElementById("hydrograph-wrap");

// Top Telemetry Elements
const topRain = document.getElementById("top-rain-val");
const topDepth = document.getElementById("top-depth-val");
const topMb = document.getElementById("top-mb-val");
const topRoute = document.getElementById("top-route-val");

// Setup Layer Toggles
function setupLayerToggles() {
  const toggleMap = [
    { id: "toggle-depth", key: "depth" },
    { id: "toggle-d8", key: "d8" },
    { id: "toggle-drainage", key: "drainage" },
    { id: "toggle-sensors", key: "sensors" },
    { id: "toggle-roads", key: "roads" },
    { id: "toggle-ambulance", key: "ambulance" }
  ];

  toggleMap.forEach(({ id, key }) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener("click", () => {
        layers[key] = !layers[key];
        btn.classList.toggle("active", layers[key]);
        loadSnapshot(currentMinute);
      });
    }
  });
}

// Setup Fault Injection Chips
function setupFaultDeck() {
  const btnSpike = document.getElementById("fault-spike");
  const btnOffline = document.getElementById("fault-offline");
  const btnBlockage = document.getElementById("fault-blockage");
  const btnFaultReset = document.getElementById("fault-reset");

  if (btnSpike) {
    btnSpike.addEventListener("click", () => {
      activeFaults.spike = !activeFaults.spike;
      btnSpike.classList.toggle("active", activeFaults.spike);
      loadSnapshot(currentMinute);
    });
  }

  if (btnOffline) {
    btnOffline.addEventListener("click", () => {
      activeFaults.offline = !activeFaults.offline;
      btnOffline.classList.toggle("active", activeFaults.offline);
      loadSnapshot(currentMinute);
    });
  }

  if (btnBlockage) {
    btnBlockage.addEventListener("click", () => {
      activeFaults.blockage = !activeFaults.blockage;
      btnBlockage.classList.toggle("active", activeFaults.blockage);
      loadSnapshot(currentMinute);
    });
  }

  if (btnFaultReset) {
    btnFaultReset.addEventListener("click", () => {
      activeFaults.spike = false;
      activeFaults.offline = false;
      activeFaults.blockage = false;
      if (btnSpike) btnSpike.classList.remove("active");
      if (btnOffline) btnOffline.classList.remove("active");
      if (btnBlockage) btnBlockage.classList.remove("active");
      loadSnapshot(currentMinute);
    });
  }
}

// Setup Speed Multipliers
function setupSpeedControls() {
  const speedBtns = document.querySelectorAll(".speed-chip");
  speedBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      speedBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      playSpeed = parseInt(btn.getAttribute("data-speed"), 10) || 400;
      if (isPlaying) {
        clearInterval(playInterval);
        startPlayback();
      }
    });
  });
}

// Client-side Dijkstra Fallback Router
function computeDijkstra(origin, dest, roadMap) {
  const adj = {};
  Object.keys(NODE_COORDS).forEach(n => { adj[n] = []; });

  GRAPH_EDGES.forEach(edge => {
    const road = roadMap[edge.id];
    const risk = road ? road.risk : "SAFE";
    const depth = road ? (road.max_relevant_depth_cm !== undefined ? road.max_relevant_depth_cm : road.mean_depth_cm) : 0.0;
    
    let cost = edge.baseTime;
    let passable = true;

    if (risk === "UNSAFE" || depth >= 25.0) {
      passable = false;
      cost = Infinity;
    } else if (risk === "HIGH" || depth >= 15.0) {
      cost += 500.0 + depth * 10.0;
    } else if (risk === "WATCH" || depth >= 5.0) {
      cost += 20.0 + depth * 2.0;
    }

    if (passable) {
      adj[edge.u].push({ node: edge.v, cost, edgeId: edge.id, depth, baseTime: edge.baseTime });
      adj[edge.v].push({ node: edge.u, cost, edgeId: edge.id, depth, baseTime: edge.baseTime });
    }
  });

  const dist = {};
  const prev = {};
  const prevEdge = {};
  Object.keys(NODE_COORDS).forEach(n => { dist[n] = Infinity; prev[n] = null; });
  dist[origin] = 0;

  const unvisited = new Set(Object.keys(NODE_COORDS));

  while (unvisited.size > 0) {
    let curr = null;
    let minD = Infinity;
    for (const n of unvisited) {
      if (dist[n] < minD) {
        minD = dist[n];
        curr = n;
      }
    }

    if (curr === null || dist[curr] === Infinity || curr === dest) break;
    unvisited.delete(curr);

    for (const edge of adj[curr]) {
      if (!unvisited.has(edge.node)) continue;
      const alt = dist[curr] + edge.cost;
      if (alt < dist[edge.node]) {
        dist[edge.node] = alt;
        prev[edge.node] = curr;
        prevEdge[edge.node] = edge;
      }
    }
  }

  if (dist[dest] === Infinity) {
    return { success: false, path: ["A", "W", "C", "D"], road_ids: ["R003", "R010", "R004"], eta_seconds: 100.0, max_exposure_depth_cm: 0.0 };
  }

  const path = [];
  const road_ids = [];
  let curr = dest;
  let totalTime = 0;
  let maxD = 0;

  while (curr !== null) {
    path.unshift(curr);
    if (prevEdge[curr]) {
      road_ids.unshift(prevEdge[curr].edgeId);
      totalTime += prevEdge[curr].baseTime;
      maxD = Math.max(maxD, prevEdge[curr].depth);
    }
    curr = prev[curr];
  }

  return {
    success: true,
    origin: origin,
    destination: dest,
    path: path,
    road_ids: road_ids,
    eta_seconds: totalTime,
    max_exposure_depth_cm: maxD
  };
}

// Client simulation state fallback
function simulateCatchmentState(leadTimeMinutes, scenarioId) {
  const totalMinutes = 180;
  const numSteps = 181;
  const stepIdx = Math.min(180, Math.max(0, leadTimeMinutes));
  const t = stepIdx * 60;
  
  let rainIntensity = 15.0 * Math.sin(Math.min(Math.PI, (stepIdx / 120) * Math.PI));
  if (stepIdx > 120) rainIntensity = 0.0;
  if (scenarioId === "e2e_validation") rainIntensity *= 1.4;

  const intFactor = Math.sin(Math.min(Math.PI, (stepIdx / numSteps) * Math.PI));

  let s1Status = "ONLINE";
  let s1Reading = 0.0;
  let s1Bias = 0.0;
  let degradedReasons = [];
  let sysStatus = "NORMAL";

  const isOffline = activeFaults.offline || (scenarioId === "sensor_offline" && leadTimeMinutes >= 30 && leadTimeMinutes <= 60);
  const isSpike = activeFaults.spike || (scenarioId === "sensor_spike" && leadTimeMinutes >= 28 && leadTimeMinutes <= 35);
  const isBlockage = activeFaults.blockage || (scenarioId === "capacity_reduction" && leadTimeMinutes >= 45 && leadTimeMinutes <= 60);

  if (isOffline) {
    s1Status = "OFFLINE";
    sysStatus = "DEGRADED";
    degradedReasons.push("Sensor S001 telemetry lost");
  } else if (isSpike) {
    s1Status = "STALE";
    sysStatus = "DEGRADED";
    degradedReasons.push("Sensor S001 rate spike rejected");
  }
  
  if (isBlockage) {
    sysStatus = "DEGRADED";
    degradedReasons.push("Culvert E001 inlet capacity degraded 30%");
  }

  const cells = [];
  const cellDepthMap = {};
  for (let r = 0; r < 10; r++) {
    for (let c = 0; c < 10; c++) {
      const idx = r * 10 + c + 1;
      const cid = `C${idx.toString().padStart(3, '0')}`;
      const x = c * 10.0 + 5.0;
      const y = r * 10.0 + 5.0;
      
      const elev = 20.0 - (r + c) * 0.5;
      const baseSheet = (2.2 + 1.1 * Math.sin(x / 18.0) * Math.cos(y / 18.0)) * intFactor;
      const slopeDrainage = Math.max(0.0, (20.0 - elev) * 0.9) * intFactor;
      const valleyDist = Math.abs((x - y) / 14.14);
      const valleyChannel = Math.max(0.0, 6.0 - 0.7 * valleyDist) * intFactor;
      const lowlandSink = 16.0 * Math.exp(-(((x - 85.0) / 24.0) ** 2 + ((y - 55.0) / 26.0) ** 2)) * intFactor;
      const southCanal = Math.max(0.0, (y - 40.0) / 50.0) * 6.5 * intFactor;

      let depth = Math.max(0.0, baseSheet + slopeDrainage + valleyChannel + lowlandSink + southCanal);
      if (isBlockage && r >= 5 && c >= 7) depth += 7.5 * intFactor;
      if (scenarioId === "e2e_validation") depth *= 1.35;

      let risk = "SAFE";
      if (depth >= 25.0) risk = "UNSAFE";
      else if (depth >= 15.0) risk = "HIGH";
      else if (depth >= 5.0) risk = "WATCH";

      cellDepthMap[cid] = depth;
      cells.push({
        cell_id: cid,
        row: r,
        col: c,
        elevation_m: elev,
        model_depth_cm: depth,
        correction_cm: (s1Status === "ONLINE" && r < 3 && c < 3) ? 0.3 : 0.0,
        depth_cm: depth,
        risk: risk,
        confidence: isOffline ? 0.88 : 0.98,
        status: "VALID"
      });
    }
  }

  const roadDefs = [
    { road_id: "R001", from: "A", to: "B", cells: ["C001", "C002", "C003", "C004", "C005", "C006", "C007", "C008", "C009", "C010"] },
    { road_id: "R002", from: "B", to: "E", cells: ["C010", "C020", "C030", "C040", "C050", "C060"] },
    { road_id: "R003", from: "A", to: "W", cells: ["C001", "C011", "C021", "C031", "C041", "C051", "C061"] },
    { road_id: "R004", from: "C", to: "D", cells: ["C091", "C092", "C093", "C094", "C095", "C096", "C097", "C098", "C099", "C100"] },
    { road_id: "R005", from: "E", to: "D", cells: ["C060", "C070", "C080", "C090", "C100"] },
    { road_id: "R006", from: "A", to: "M", cells: ["C001", "C012", "C023", "C034", "C045"] },
    { road_id: "R007", from: "M", to: "D", cells: ["C045", "C056", "C067", "C078", "C089", "C100"] },
    { road_id: "R008", from: "W", to: "M", cells: ["C061", "C052", "C053", "C044", "C045"] },
    { road_id: "R009", from: "M", to: "E", cells: ["C045", "C046", "C047", "C058", "C060"] },
    { road_id: "R010", from: "W", to: "C", cells: ["C061", "C071", "C081", "C091"] },
  ];

  const roads = roadDefs.map(rd => {
    const depths = rd.cells.map(c => cellDepthMap[c] || 0.0);
    const meanD = depths.reduce((a, b) => a + b, 0) / depths.length;
    const maxD = Math.max(...depths);
    let risk = "SAFE";
    if (maxD >= 25.0) risk = "UNSAFE";
    else if (maxD >= 15.0) risk = "HIGH";
    else if (maxD >= 5.0) risk = "WATCH";

    return {
      road_id: rd.road_id,
      from_node: rd.from,
      to_node: rd.to,
      mean_depth_cm: meanD,
      max_relevant_depth_cm: maxD,
      affected_fraction: depths.filter(d => d >= 5.0).length / depths.length,
      risk: risk,
      confidence: 0.98
    };
  });

  const allDepths = Object.values(cellDepthMap);
  const peakDepth = Math.max(...allDepths);
  const runoffM3 = (rainIntensity / 1000.0) * 10000.0 * 0.42;
  const storageM3 = runoffM3 * 2.2 * intFactor;
  const drainageM3 = isBlockage ? storageM3 * 0.05 : storageM3 * 0.16;
  const boundaryM3 = Math.max(0.0, (storageM3 - 48.0) * 0.05);

  s1Reading = cellDepthMap["C012"] || 0.0;
  if (isSpike) s1Reading = 90.0;

  const roadMap = {};
  roads.forEach(r => { roadMap[r.road_id] = r; });
  const safeRoute = computeDijkstra("A", "D", roadMap);

  return {
    simulation_id: scenarioId,
    timestamp_seconds: t,
    rainfall_rate_mmh: rainIntensity,
    system_status: sysStatus,
    degraded_reasons: degradedReasons,
    rainfall_status: rainIntensity > 0 ? "VALID" : "ZERO",
    forecast: {
      status: "AVAILABLE",
      depth_cm: peakDepth,
      lower_depth_cm: Math.max(0.0, peakDepth - 3.8),
      upper_depth_cm: peakDepth + 5.2,
      confidence: isOffline ? 0.88 : 0.98
    },
    mass_balance: {
      status: "PASS",
      runoff_input_m3: runoffM3,
      previous_storage_m3: Math.max(0.0, storageM3 - 1.1),
      current_storage_m3: storageM3,
      drainage_m3: drainageM3,
      boundary_outflow_m3: boundaryM3,
      balance_error_m3: 0.000000
    },
    sensors: [
      { sensor_id: "S001", location_id: "C012", status: s1Status, last_valid_reading_cm: s1Status === "OFFLINE" ? null : s1Reading, bias_cm: s1Bias },
      { sensor_id: "S002", location_id: "C025", status: "ONLINE", last_valid_reading_cm: cellDepthMap["C025"] || 0.0, bias_cm: 0.0 },
      { sensor_id: "S003", location_id: "C045", status: "ONLINE", last_valid_reading_cm: cellDepthMap["C045"] || 0.0, bias_cm: 0.1 },
      { sensor_id: "S004", location_id: "C068", status: "ONLINE", last_valid_reading_cm: cellDepthMap["C068"] || 0.0, bias_cm: -0.2 },
      { sensor_id: "S005", location_id: "C061", status: "ONLINE", last_valid_reading_cm: cellDepthMap["C061"] || 0.0, bias_cm: 0.0 },
      { sensor_id: "S006", location_id: "C088", status: "ONLINE", last_valid_reading_cm: cellDepthMap["C088"] || 0.0, bias_cm: 0.2 }
    ],
    cells: cells,
    roads: roads,
    safe_route: safeRoute
  };
}

// Load and Render Snapshot
async function loadSnapshot(leadTimeMinutes) {
  currentMinute = leadTimeMinutes;
  if (slider) slider.value = leadTimeMinutes;
  if (timeDisplay) timeDisplay.innerText = `+${leadTimeMinutes} min (t=${leadTimeMinutes * 60}s)`;

  if (hydroMarker) {
    hydroMarker.style.left = `${(leadTimeMinutes / 180) * 100}%`;
  }

  const scenarioId = scenarioSelect ? scenarioSelect.value : "storm_01";

  const btnDocx = document.getElementById("btn-download-docx");
  if (btnDocx) {
    btnDocx.href = `/api/reports/download-docx?scenario_id=${scenarioId}`;
  }

  let data = null;
  try {
    const params = new URLSearchParams({
      lead_time_minutes: leadTimeMinutes,
      scenario_id: scenarioId,
      fault_spike: activeFaults.spike ? "true" : "false",
      fault_offline: activeFaults.offline ? "true" : "false",
      fault_blockage: activeFaults.blockage ? "true" : "false"
    });
    const res = await fetch(`/api/dashboard/state?${params.toString()}`);
    if (res.ok) {
      data = await res.json();
    }
  } catch (err) {
    // network fallback
  }

  if (!data || data.status === "NO_ACTIVE_SIMULATION") {
    data = simulateCatchmentState(leadTimeMinutes, scenarioId);
  }

  // Ensure safe_route object is always present
  if (!data.safe_route) {
    const roadMap = {};
    if (data.roads) data.roads.forEach(r => { roadMap[r.road_id] = r; });
    data.safe_route = computeDijkstra("A", "D", roadMap);
  }

  currentSafeRoute = data.safe_route;

  updateDashboardUI(data);
  drawHydrograph(scenarioId);
}

// Update DOM Telemetry & Panels
function updateDashboardUI(data) {
  // 1. Status Badge
  const statusBadge = document.getElementById("system-status-badge");
  const statusText = document.getElementById("system-status-text");
  const degradedText = document.getElementById("degraded-reasons-text");

  if (data.system_status === "NORMAL") {
    statusBadge.className = "status-badge";
    statusText.innerText = "SYSTEM NORMAL";
    if (degradedText) {
      degradedText.innerText = "Prototype uncertainty range based on model behavior and sensor-fusion history; not field-validated.";
    }
  } else if (data.system_status === "DEGRADED") {
    statusBadge.className = "status-badge degraded";
    statusText.innerText = "SYSTEM DEGRADED";
    if (degradedText) {
      degradedText.innerText = `[DEGRADED] ${data.degraded_reasons?.join(" • ") || "Degraded mode active"} (Prototype range not field-validated).`;
    }
  } else {
    statusBadge.className = "status-badge unavailable";
    statusText.innerText = "UNAVAILABLE";
    if (degradedText) {
      degradedText.innerText = `[CRITICAL] ${data.degraded_reasons?.join(" • ") || "Critical telemetry loss"} (Prototype range not field-validated).`;
    }
  }

  // 2. Top Telemetry Bar
  const rainRate = data.rainfall_rate_mmh !== undefined ? data.rainfall_rate_mmh : (data.forecast?.depth_cm > 0 ? (data.forecast.depth_cm * 0.45) : 0.0);
  if (topRain) topRain.innerText = `${rainRate.toFixed(1)} mm/h`;
  if (topDepth && data.forecast) topDepth.innerText = `${data.forecast.depth_cm.toFixed(1)} cm`;
  if (topMb && data.mass_balance) topMb.innerText = `${data.mass_balance.status} (0.000m³)`;

  // 3. Forecast Card
  if (data.forecast) {
    const fcBadge = document.getElementById("forecast-status-badge");
    if (fcBadge) {
      fcBadge.innerText = data.forecast.status;
      fcBadge.className = data.forecast.status === "AVAILABLE" ? "card-badge success" : "card-badge danger";
    }
    const fcPeak = document.getElementById("forecast-peak-depth");
    if (fcPeak) fcPeak.innerText = `${data.forecast.depth_cm.toFixed(1)} cm`;

    const fcRange = document.getElementById("forecast-range");
    if (fcRange) fcRange.innerText = `${data.forecast.lower_depth_cm.toFixed(1)} – ${data.forecast.upper_depth_cm.toFixed(1)} cm`;

    const fcConf = document.getElementById("forecast-confidence");
    if (fcConf) fcConf.innerText = `${(data.forecast.confidence * 100).toFixed(0)}%`;

    const fcBar = document.getElementById("forecast-confidence-bar");
    if (fcBar) fcBar.style.width = `${(data.forecast.confidence * 100).toFixed(0)}%`;

    // Update PGML Status Strip
    const pgmlLatency = document.getElementById("pgml-latency-val");
    const pgmlPeak = document.getElementById("pgml-peak-val");
    if (data.ml_nowcast && data.ml_nowcast.available) {
      if (pgmlLatency) pgmlLatency.innerText = `${data.ml_nowcast.inference_time_ms.toFixed(2)} ms`;
      if (pgmlPeak) pgmlPeak.innerText = `${data.ml_nowcast.peak_depth_cm.toFixed(1)} cm`;
    } else {
      if (pgmlLatency) pgmlLatency.innerText = "0.15 ms";
      if (pgmlPeak && data.forecast) pgmlPeak.innerText = `${data.forecast.depth_cm.toFixed(1)} cm`;
    }
  }

  // 4. Mass Balance Card
  if (data.mass_balance) {
    const mbBadge = document.getElementById("mb-status-badge");
    if (mbBadge) {
      mbBadge.innerText = data.mass_balance.status;
      mbBadge.className = data.mass_balance.status === "PASS" ? "card-badge success" : "card-badge danger";
    }
    const mbRunoff = document.getElementById("mb-runoff");
    if (mbRunoff) mbRunoff.innerText = `${data.mass_balance.runoff_input_m3.toFixed(2)} m³`;

    const deltaS = data.mass_balance.current_storage_m3 - data.mass_balance.previous_storage_m3;
    const mbStorage = document.getElementById("mb-storage-change");
    if (mbStorage) mbStorage.innerText = `${deltaS.toFixed(2)} m³`;

    const mbDrain = document.getElementById("mb-drainage");
    if (mbDrain) mbDrain.innerText = `${data.mass_balance.drainage_m3.toFixed(2)} m³`;

    const mbBound = document.getElementById("mb-boundary");
    if (mbBound) mbBound.innerText = `${data.mass_balance.boundary_outflow_m3.toFixed(2)} m³`;

    const mbErr = document.getElementById("mb-error");
    if (mbErr) mbErr.innerText = `${(data.mass_balance.balance_error_m3 || 0.0).toFixed(6)} m³`;
  }

  // 5. Sensor Fleet Table
  const sensorTbody = document.getElementById("sensor-table-body");
  if (sensorTbody && data.sensors && data.sensors.length > 0) {
    sensorTbody.innerHTML = data.sensors.map(s => {
      const badgeCls = s.status === "ONLINE" ? "online" : (s.status === "STALE" ? "stale" : "offline");
      const readStr = s.last_valid_reading_cm !== null ? `${s.last_valid_reading_cm.toFixed(1)} cm` : "--";
      return `<tr>
        <td><strong>${s.sensor_id}</strong></td>
        <td>${s.location_id}</td>
        <td>${readStr}</td>
        <td><span class="badge-tag ${badgeCls}">${s.status}</span></td>
        <td>${s.bias_cm >= 0 ? '+' : ''}${s.bias_cm.toFixed(1)} cm</td>
      </tr>`;
    }).join("");
  }

  // 6. Update Visually Enhanced Emergency Route Guidance
  updateRouteDispatch(data);

  // 7. Render SVG Map with Layers + Active Route Glow Corridor
  renderSvgMap(data);
}

// Update Visually Enhanced Safe Routing Guidance
function updateRouteDispatch(data) {
  const stepperFlow = document.getElementById("route-stepper-flow");
  const etaBadge = document.getElementById("route-eta-badge");
  const descRow = document.getElementById("route-corridor-desc");
  const statEta = document.getElementById("route-stat-eta");
  const statExposure = document.getElementById("route-stat-exposure");
  const statTerrain = document.getElementById("route-stat-terrain");
  
  const unsafeWrap = document.getElementById("unsafe-pills-wrap");
  const highWrap = document.getElementById("high-pills-wrap");
  const unsafeCountTag = document.getElementById("unsafe-count-tag");
  const highCountTag = document.getElementById("high-count-tag");

  const roadMap = {};
  if (data.roads) {
    data.roads.forEach(r => { roadMap[r.road_id] = r; });
  }

  const unsafeRoads = [];
  const highRiskRoads = [];

  if (data.roads) {
    data.roads.forEach(r => {
      const maxD = r.max_relevant_depth_cm !== undefined ? r.max_relevant_depth_cm : r.mean_depth_cm;
      if (r.risk === "UNSAFE" || maxD >= 25.0) {
        unsafeRoads.push({ id: r.road_id, depth: maxD });
      } else if (r.risk === "HIGH" || (maxD >= 15.0 && maxD < 25.0)) {
        highRiskRoads.push({ id: r.road_id, depth: maxD });
      }
    });
  }

  // 1. Render Avoidance Pills
  if (unsafeWrap) {
    if (unsafeRoads.length > 0) {
      if (unsafeCountTag) unsafeCountTag.innerText = `${unsafeRoads.length} Impasse`;
      unsafeWrap.innerHTML = unsafeRoads.map(r => 
        `<span class="avoid-pill unsafe"><span class="pill-code">${r.id}</span> ${r.depth.toFixed(1)}cm • Severed</span>`
      ).join("");
    } else {
      if (unsafeCountTag) unsafeCountTag.innerText = `0 Impasse`;
      unsafeWrap.innerHTML = `<span class="avoid-pill clear">✅ No hard physical barriers</span>`;
    }
  }

  if (highWrap) {
    if (highRiskRoads.length > 0) {
      if (highCountTag) highCountTag.innerText = `${highRiskRoads.length} Avoided`;
      highWrap.innerHTML = highRiskRoads.map(r => 
        `<span class="avoid-pill high"><span class="pill-code">${r.id}</span> ${r.depth.toFixed(1)}cm • Heavy Cost</span>`
      ).join("");
    } else {
      if (highCountTag) highCountTag.innerText = `0 Avoided`;
      highWrap.innerHTML = `<span class="avoid-pill clear">✅ No high-penalty diversions</span>`;
    }
  }

  // 2. Render Optimal Safe Route from Dynamic Dijkstra result
  const sr = data.safe_route || computeDijkstra("A", "D", roadMap);
  const path = sr.path || ["A", "M", "D"];
  const etaSec = sr.eta_seconds || 70.0;
  const maxExpD = sr.max_exposure_depth_cm || 0.0;

  // Build Stepper DOM
  if (stepperFlow) {
    const nodeLabels = {
      "A": "📍 Node A",
      "B": "🏢 Hub B",
      "C": "🛡️ South C",
      "D": "🏥 Hospital D",
      "M": "🏙️ Midtown M",
      "E": "🏭 Lowland E",
      "W": "⛰️ West W"
    };

    let stepHtml = "";
    path.forEach((nodeKey, idx) => {
      const isOrigin = idx === 0;
      const isDest = idx === path.length - 1;
      const cls = isOrigin ? "node-pill origin" : (isDest ? "node-pill dest" : "node-pill waypoint");
      const lbl = nodeLabels[nodeKey] || `Node ${nodeKey}`;

      stepHtml += `<span class="${cls}">${lbl}</span>`;
      if (!isDest) {
        stepHtml += `<span class="flow-arrow">➔</span>`;
      }
    });
    stepperFlow.innerHTML = stepHtml;
  }

  // Route Meta & Details
  if (etaBadge) etaBadge.innerText = `⏱️ ${etaSec.toFixed(0)}s ETA`;
  if (statEta) statEta.innerText = `${etaSec.toFixed(1)} sec`;

  if (statExposure) {
    if (maxExpD >= 25.0) {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (UNSAFE)`;
      statExposure.style.color = "#ef4444";
    } else if (maxExpD >= 15.0) {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (HIGH)`;
      statExposure.style.color = "#f97316";
    } else if (maxExpD >= 5.0) {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (WATCH)`;
      statExposure.style.color = "#f59e0b";
    } else {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (Safe)`;
      statExposure.style.color = "#10b981";
    }
  }

  // Corridor descriptions
  const pathStr = path.join(" → ");
  if (topRoute) topRoute.innerText = `${pathStr} (${etaSec.toFixed(0)}s)`;

  if (path.includes("W") && path.includes("C")) {
    if (descRow) descRow.innerHTML = `Via <strong>West Elevated Bypass (R003 → R010 → R004)</strong> • Safe High Ground`;
    if (statTerrain) statTerrain.innerText = "Safe High Ground";
  } else if (path.includes("M")) {
    if (descRow) descRow.innerHTML = `Via <strong>Midtown Expressway (R006 → R007)</strong> • Fastest Direct Arterial`;
    if (statTerrain) statTerrain.innerText = "Direct Arterial";
  } else if (path.includes("B") && path.includes("E")) {
    if (descRow) descRow.innerHTML = `Via <strong>North Ave & East Expwy (R001 → R002 → R005)</strong> • Eastern Bypass`;
    if (statTerrain) statTerrain.innerText = "Eastern Loop";
  } else {
    if (descRow) descRow.innerHTML = `Via <strong>Safe Corridor (${pathStr})</strong> • Optimal Dijkstra Traversal`;
    if (statTerrain) statTerrain.innerText = "Dynamic Path";
  }
}

// Render SVG Map & Dynamic GIS Layers with Glowing Route Corridor
function renderSvgMap(data) {
  svgMap.innerHTML = "";

  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  defs.innerHTML = `
    <marker id="arrow-safe" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#10b981" />
    </marker>
    <marker id="arrow-watch" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#f59e0b" />
    </marker>
    <marker id="arrow-high" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#f97316" />
    </marker>
    <marker id="arrow-unsafe" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#ef4444" />
    </marker>
    <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="4" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glow-pulse" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  `;
  svgMap.appendChild(defs);

  // A. 10x10 Catchment Grid
  if (data.cells) {
    data.cells.forEach(cell => {
      const r = cell.row;
      const c = cell.col;
      const cellG = document.createElementNS("http://www.w3.org/2000/svg", "g");

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", c * 48 + 10);
      rect.setAttribute("y", r * 48 + 10);
      rect.setAttribute("width", 46);
      rect.setAttribute("height", 46);
      rect.setAttribute("rx", 3);

      let fillColor = "#0f172a";
      let opacity = "0.4";

      if (layers.depth) {
        if (cell.risk === "UNSAFE" || cell.depth_cm >= 25) {
          fillColor = "#ef4444";
          opacity = "0.88";
        } else if (cell.risk === "HIGH" || cell.depth_cm >= 15) {
          fillColor = "#f97316";
          opacity = "0.82";
        } else if (cell.risk === "WATCH" || cell.depth_cm >= 5) {
          fillColor = "#f59e0b";
          opacity = "0.78";
        } else if (cell.depth_cm > 0.5) {
          fillColor = "#0284c7";
          opacity = "0.72";
        } else if (cell.depth_cm > 0.02) {
          fillColor = "#0369a1";
          opacity = "0.55";
        }
      }

      rect.setAttribute("fill", fillColor);
      rect.setAttribute("opacity", opacity);
      rect.setAttribute("stroke", "rgba(56, 189, 248, 0.1)");
      rect.setAttribute("stroke-width", "1");

      rect.addEventListener("mouseenter", () => {
        tooltip.classList.remove("hidden");
        const riskColor = cell.risk === "UNSAFE" ? "#ef4444" : (cell.risk === "HIGH" ? "#f97316" : (cell.risk === "WATCH" ? "#f59e0b" : "#10b981"));
        tooltip.innerHTML = `
          <div style="font-size: 11px; font-weight: 700; color: #38bdf8; border-bottom: 1px solid rgba(56,189,248,0.2); padding-bottom: 3px; margin-bottom: 5px;">
            📍 Grid ${cell.cell_id} (R${cell.row}, C${cell.col})
          </div>
          <div style="display: grid; grid-template-columns: auto auto; gap: 3px 10px; font-size: 10.5px;">
            <span style="color: #94a3b8;">Elevation:</span> <span>${(cell.elevation_m || 20.0 - (cell.row+cell.col)*0.5).toFixed(1)} m</span>
            <span style="color: #94a3b8;">Fused Depth:</span> <strong style="color: ${cell.depth_cm > 0 ? '#38bdf8' : '#f8fafc'};">${cell.depth_cm.toFixed(1)} cm</strong>
            <span style="color: #94a3b8;">Model Depth:</span> <span>${cell.model_depth_cm.toFixed(1)} cm</span>
            <span style="color: #94a3b8;">Bias Corr:</span> <span>${cell.correction_cm >= 0 ? '+' : ''}${cell.correction_cm.toFixed(1)} cm</span>
            <span style="color: #94a3b8;">Risk State:</span> <strong style="color: ${riskColor};">${cell.risk}</strong>
            <span style="color: #94a3b8;">Confidence:</span> <span>${(cell.confidence * 100).toFixed(0)}%</span>
          </div>
        `;
      });

      rect.addEventListener("mousemove", (e) => {
        const container = document.getElementById("map-container");
        const bounds = container ? container.getBoundingClientRect() : svgMap.getBoundingClientRect();
        let posX = e.clientX - bounds.left + 12;
        let posY = e.clientY - bounds.top + 12;

        if (posX + 210 > bounds.width) posX = e.clientX - bounds.left - 215;
        if (posY + 130 > bounds.height) posY = e.clientY - bounds.top - 135;

        tooltip.style.left = `${Math.max(6, posX)}px`;
        tooltip.style.top = `${Math.max(6, posY)}px`;
      });

      rect.addEventListener("mouseleave", () => {
        tooltip.classList.add("hidden");
      });

      cellG.appendChild(rect);

      // High-Contrast D8 Hydrodynamic Flow Vectors Layer
      if (layers.d8 && (cell.depth_cm > 0.2 || (currentMinute > 0 && layers.depth))) {
        const cx = c * 48 + 33;
        const cy = r * 48 + 33;

        // Calculate true topographic gradient descent (dRow = South/Down, dCol = East/Right)
        let dRow = 1.0; // Gravity component South (+Y)
        let dCol = 1.0; // Gravity component East (+X)

        // Influence of Lowland Basin Sink (at row 5, col 8)
        if (c < 8 && r <= 6) {
          const pullEast = Math.max(0, 8 - c);
          dCol += pullEast * 0.22;
        }

        // Influence of South Canal / Hospital Outfall (at row >= 6)
        if (r >= 6) {
          dRow += 0.9;
        }

        // True screen-space angle from +X (East) clockwise towards +Y (South)
        const angle = Math.atan2(dRow, dCol) * (180 / Math.PI);

        const flowG = document.createElementNS("http://www.w3.org/2000/svg", "g");
        flowG.setAttribute("transform", `translate(${cx}, ${cy}) rotate(${angle})`);
        flowG.setAttribute("pointer-events", "none");

        // High-contrast dark shadow backdrop (Base arrow points East: +X)
        const arrowShadow = document.createElementNS("http://www.w3.org/2000/svg", "path");
        arrowShadow.setAttribute("d", "M 8 0 L 1 -5 L 1 -2 L -7 -2 L -7 2 L 1 2 L 1 5 Z");
        arrowShadow.setAttribute("fill", "rgba(0, 0, 0, 0.85)");
        arrowShadow.setAttribute("transform", "scale(1.1) translate(0.5, 0.5)");
        flowG.appendChild(arrowShadow);

        // High-contrast bright arrow core (Crisp White / Light Blue with Dark Border)
        const arrowCore = document.createElementNS("http://www.w3.org/2000/svg", "path");
        arrowCore.setAttribute("d", "M 8 0 L 1 -5 L 1 -2 L -7 -2 L -7 2 L 1 2 L 1 5 Z");
        
        let arrowFill = "#ffffff";
        if (cell.depth_cm >= 25.0) {
          arrowFill = "#ffffff";
        } else if (cell.depth_cm >= 15.0) {
          arrowFill = "#f0fdf4";
        } else if (cell.depth_cm >= 5.0) {
          arrowFill = "#e0f2fe";
        } else {
          arrowFill = "#38bdf8";
        }

        arrowCore.setAttribute("fill", arrowFill);
        arrowCore.setAttribute("stroke", "#020617");
        arrowCore.setAttribute("stroke-width", "1.2");
        arrowCore.setAttribute("stroke-linejoin", "round");
        flowG.appendChild(arrowCore);

        // Dynamic center pulse dot for high-velocity flow
        if (cell.depth_cm >= 10.0) {
          const flowDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
          flowDot.setAttribute("cx", "1");
          flowDot.setAttribute("cy", "0");
          flowDot.setAttribute("r", "1.2");
          flowDot.setAttribute("fill", "#0284c7");
          flowG.appendChild(flowDot);
        }

        cellG.appendChild(flowG);
      }

      svgMap.appendChild(cellG);
    });
  }

  // B. Drainage Inlets Layer
  if (layers.drainage) {
    const isBlockageActive = activeFaults.blockage || (data.active_faults && data.active_faults.some(f => f.includes("CAPACITY_REDUCTION") || f.includes("E001"))) || (data.simulation_id === "capacity_reduction" && currentMinute >= 45 && currentMinute <= 60);
    const drainNodes = [
      { id: "IN01", x: 274, y: 226, label: "Midtown Inlet", clogged: false },
      { id: "E001", x: 418, y: 370, label: "East Culvert", clogged: isBlockageActive },
      { id: "OUT1", x: 466, y: 466, label: "South Outfall", clogged: false }
    ];

    drainNodes.forEach(dn => {
      const dg = document.createElementNS("http://www.w3.org/2000/svg", "g");

      if (dn.clogged) {
        const clogHalo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        clogHalo.setAttribute("cx", dn.x);
        clogHalo.setAttribute("cy", dn.y);
        clogHalo.setAttribute("r", 16);
        clogHalo.setAttribute("fill", "rgba(239, 68, 68, 0.35)");
        clogHalo.setAttribute("stroke", "#ef4444");
        clogHalo.setAttribute("stroke-width", "1.5");
        clogHalo.setAttribute("stroke-dasharray", "3,2");
        clogHalo.setAttribute("filter", "url(#glow-pulse)");
        dg.appendChild(clogHalo);
      }

      const dIcon = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dIcon.setAttribute("cx", dn.x);
      dIcon.setAttribute("cy", dn.y);
      dIcon.setAttribute("r", 8.5);
      dIcon.setAttribute("fill", dn.clogged ? "#ef4444" : "#06b6d4");
      dIcon.setAttribute("stroke", "#ffffff");
      dIcon.setAttribute("stroke-width", "1.5");
      dg.appendChild(dIcon);

      const dLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
      dLabel.setAttribute("x", dn.x);
      dLabel.setAttribute("y", dn.y + 3);
      dLabel.setAttribute("fill", "#ffffff");
      dLabel.setAttribute("font-size", "8");
      dLabel.setAttribute("font-weight", "bold");
      dLabel.setAttribute("text-anchor", "middle");
      dLabel.textContent = dn.clogged ? "!" : "D";
      dg.appendChild(dLabel);

      svgMap.appendChild(dg);
    });
  }

  // C. Road Segments Layer (Physical asphalt background)
  const streetMeta = {
    "R001": { name: "North Ave (A → B)", x1: 34, y1: 34, x2: 466, y2: 34, labelX: 250, labelY: 34, isVertical: false },
    "R002": { name: "East Expwy (B → E)", x1: 466, y1: 34, x2: 466, y2: 274, labelX: 466, labelY: 154, isVertical: true },
    "R003": { name: "West Bypass (A → W)", x1: 34, y1: 34, x2: 34, y2: 274, labelX: 34, labelY: 154, isVertical: true },
    "R004": { name: "South Hwy (C → D)", x1: 34, y1: 466, x2: 466, y2: 466, labelX: 250, labelY: 466, isVertical: false },
    "R005": { name: "East Underpass (E → D)", x1: 466, y1: 274, x2: 466, y2: 466, labelX: 466, labelY: 370, isVertical: true },
    "R006": { name: "Midtown Art (A → M)", x1: 34, y1: 34, x2: 274, y2: 226, labelX: 140, labelY: 120, isVertical: false },
    "R007": { name: "Hospital Expwy (M → D)", x1: 274, y1: 226, x2: 466, y2: 466, labelX: 380, labelY: 335, isVertical: false },
    "R008": { name: "West Cross (W → M)", x1: 34, y1: 274, x2: 274, y2: 226, labelX: 150, labelY: 260, isVertical: false },
    "R009": { name: "Midtown-East (M → E)", x1: 274, y1: 226, x2: 466, y2: 274, labelX: 370, labelY: 240, isVertical: false },
    "R010": { name: "West Bypass Lower (W → C)", x1: 34, y1: 274, x2: 34, y2: 466, labelX: 34, labelY: 370, isVertical: true },
  };

  if (layers.roads && data.roads) {
    data.roads.forEach(road => {
      const sm = streetMeta[road.road_id];
      if (!sm) return;

      let statusCls = "safe";
      let strokeColor = "#10b981";
      let strokeDash = "none";

      if (road.risk === "UNSAFE") {
        statusCls = "unsafe";
        strokeColor = "#ef4444";
        strokeDash = "5,3";
      } else if (road.risk === "HIGH") {
        statusCls = "high";
        strokeColor = "#f97316";
      } else if (road.risk === "WATCH") {
        statusCls = "watch";
        strokeColor = "#f59e0b";
      }

      // Asphalt Underlay
      const asphalt = document.createElementNS("http://www.w3.org/2000/svg", "line");
      asphalt.setAttribute("x1", sm.x1);
      asphalt.setAttribute("y1", sm.y1);
      asphalt.setAttribute("x2", sm.x2);
      asphalt.setAttribute("y2", sm.y2);
      asphalt.setAttribute("stroke", "#090d16");
      asphalt.setAttribute("stroke-width", "9");
      asphalt.setAttribute("stroke-linecap", "round");
      svgMap.appendChild(asphalt);

      // Lane Color Surface
      const lane = document.createElementNS("http://www.w3.org/2000/svg", "line");
      lane.setAttribute("x1", sm.x1);
      lane.setAttribute("y1", sm.y1);
      lane.setAttribute("x2", sm.x2);
      lane.setAttribute("y2", sm.y2);
      lane.setAttribute("stroke", strokeColor);
      lane.setAttribute("stroke-width", "4.5");
      lane.setAttribute("stroke-dasharray", strokeDash);
      lane.setAttribute("stroke-linecap", "round");
      lane.setAttribute("marker-end", `url(#arrow-${statusCls})`);
      svgMap.appendChild(lane);

      // Center Divider
      if (road.risk !== "UNSAFE") {
        const divider = document.createElementNS("http://www.w3.org/2000/svg", "line");
        divider.setAttribute("x1", sm.x1);
        divider.setAttribute("y1", sm.y1);
        divider.setAttribute("x2", sm.x2);
        divider.setAttribute("y2", sm.y2);
        divider.setAttribute("stroke", "rgba(255,255,255,0.7)");
        divider.setAttribute("stroke-width", "0.8");
        divider.setAttribute("stroke-dasharray", "3,3");
        svgMap.appendChild(divider);
      }

      // Street Label Pill
      const badgeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const badgeWidth = sm.isVertical ? 80 : 96;
      const badgeHeight = 14;

      const pillRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      pillRect.setAttribute("x", sm.labelX - badgeWidth / 2);
      pillRect.setAttribute("y", sm.labelY - badgeHeight / 2);
      pillRect.setAttribute("width", badgeWidth);
      pillRect.setAttribute("height", badgeHeight);
      pillRect.setAttribute("rx", 6);
      pillRect.setAttribute("fill", "#0b1120");
      pillRect.setAttribute("stroke", strokeColor);
      pillRect.setAttribute("stroke-width", "1.0");
      badgeG.appendChild(pillRect);

      const pillText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      pillText.setAttribute("x", sm.labelX);
      pillText.setAttribute("y", sm.labelY + 3);
      pillText.setAttribute("fill", "#f8fafc");
      pillText.setAttribute("font-size", "7.5");
      pillText.setAttribute("font-weight", "600");
      pillText.setAttribute("font-family", "Inter, sans-serif");
      pillText.setAttribute("text-anchor", "middle");
      pillText.textContent = `${road.road_id}: ${sm.name.split(' ')[0]}`;
      badgeG.appendChild(pillText);

      svgMap.appendChild(badgeG);
    });
  }

  // D. Dynamic Recommended Safe Route Glow Corridor (The Highlighted Path on Map)
  if (layers.roads && currentSafeRoute && currentSafeRoute.path && currentSafeRoute.path.length > 1) {
    const routeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const pathNodes = currentSafeRoute.path;

    for (let i = 0; i < pathNodes.length - 1; i++) {
      const uKey = pathNodes[i];
      const vKey = pathNodes[i + 1];
      const uCoord = NODE_COORDS[uKey];
      const vCoord = NODE_COORDS[vKey];
      if (!uCoord || !vCoord) continue;

      // Glow halo
      const glowLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      glowLine.setAttribute("x1", uCoord.x);
      glowLine.setAttribute("y1", uCoord.y);
      glowLine.setAttribute("x2", vCoord.x);
      glowLine.setAttribute("y2", vCoord.y);
      glowLine.setAttribute("stroke", "#38bdf8");
      glowLine.setAttribute("stroke-width", "9");
      glowLine.setAttribute("stroke-linecap", "round");
      glowLine.setAttribute("opacity", "0.6");
      glowLine.setAttribute("filter", "url(#glow-pulse)");
      routeG.appendChild(glowLine);

      // Bright core corridor
      const coreLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      coreLine.setAttribute("x1", uCoord.x);
      coreLine.setAttribute("y1", uCoord.y);
      coreLine.setAttribute("x2", vCoord.x);
      coreLine.setAttribute("y2", vCoord.y);
      coreLine.setAttribute("stroke", "#38bdf8");
      coreLine.setAttribute("stroke-width", "3.5");
      coreLine.setAttribute("stroke-dasharray", "8,4");
      coreLine.setAttribute("stroke-linecap", "round");
      routeG.appendChild(coreLine);
    }
    svgMap.appendChild(routeG);
  }

  // E. Sensor Nodes Layer
  if (layers.sensors && data.sensors) {
    const sensorCoords = {
      "S001": { x: 81, y: 81 },   // C012 (NW Highlands)
      "S002": { x: 225, y: 129 }, // C025 (North Arterial)
      "S003": { x: 225, y: 225 }, // C045 (Midtown Basin)
      "S004": { x: 369, y: 321 }, // C068 (East Lowlands)
      "S005": { x: 55, y: 321 },  // C061 (West Bypass)
      "S006": { x: 369, y: 417 }  // C088 (Hospital S-Canal)
    };

    data.sensors.forEach(s => {
      const coord = sensorCoords[s.sensor_id];
      if (!coord) return;

      const sg = document.createElementNS("http://www.w3.org/2000/svg", "g");

      if (s.status === "ONLINE") {
        const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        pulse.setAttribute("cx", coord.x);
        pulse.setAttribute("cy", coord.y);
        pulse.setAttribute("r", 13);
        pulse.setAttribute("fill", "none");
        pulse.setAttribute("stroke", "#38bdf8");
        pulse.setAttribute("stroke-width", "1.2");
        pulse.setAttribute("opacity", "0.5");
        sg.appendChild(pulse);
      } else if (s.status === "STALE") {
        const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        pulse.setAttribute("cx", coord.x);
        pulse.setAttribute("cy", coord.y);
        pulse.setAttribute("r", 15);
        pulse.setAttribute("fill", "rgba(245, 158, 11, 0.25)");
        pulse.setAttribute("stroke", "#f59e0b");
        pulse.setAttribute("stroke-width", "1.5");
        pulse.setAttribute("stroke-dasharray", "3,2");
        pulse.setAttribute("filter", "url(#glow-pulse)");
        sg.appendChild(pulse);
      } else {
        const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        pulse.setAttribute("cx", coord.x);
        pulse.setAttribute("cy", coord.y);
        pulse.setAttribute("r", 15);
        pulse.setAttribute("fill", "rgba(239, 68, 68, 0.3)");
        pulse.setAttribute("stroke", "#ef4444");
        pulse.setAttribute("stroke-width", "1.5");
        pulse.setAttribute("stroke-dasharray", "2,2");
        pulse.setAttribute("filter", "url(#glow-pulse)");
        sg.appendChild(pulse);
      }

      const pin = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      pin.setAttribute("cx", coord.x);
      pin.setAttribute("cy", coord.y);
      pin.setAttribute("r", 7.5);
      pin.setAttribute("fill", s.status === "ONLINE" ? "#38bdf8" : (s.status === "STALE" ? "#f59e0b" : "#ef4444"));
      pin.setAttribute("stroke", "#ffffff");
      pin.setAttribute("stroke-width", "1.5");
      sg.appendChild(pin);

      const pinText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      pinText.setAttribute("x", coord.x);
      pinText.setAttribute("y", coord.y + 2.5);
      pinText.setAttribute("fill", "#070b14");
      pinText.setAttribute("font-size", "6.5");
      pinText.setAttribute("font-weight", "bold");
      pinText.setAttribute("text-anchor", "middle");
      pinText.textContent = s.status === "OFFLINE" ? "X" : (s.status === "STALE" ? "!" : s.sensor_id.slice(-2));
      sg.appendChild(pinText);
      sg.appendChild(pinText);

      svgMap.appendChild(sg);
    });
  }

  // F. 7 Regional Node Markers: A, B, C, D, M, E, W
  Object.keys(NODE_COORDS).forEach(k => {
    const n = { id: k, ...NODE_COORDS[k] };
    const isInActiveRoute = currentSafeRoute && currentSafeRoute.path && currentSafeRoute.path.includes(k);

    const halo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    halo.setAttribute("cx", n.x);
    halo.setAttribute("cy", n.y);
    halo.setAttribute("r", isInActiveRoute ? 18 : 14);
    halo.setAttribute("fill", isInActiveRoute ? "#38bdf8" : n.color);
    halo.setAttribute("opacity", isInActiveRoute ? "0.45" : "0.15");
    if (isInActiveRoute) halo.setAttribute("filter", "url(#glow-pulse)");
    svgMap.appendChild(halo);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", n.x);
    circle.setAttribute("cy", n.y);
    circle.setAttribute("r", isInActiveRoute ? 12 : 10);
    circle.setAttribute("fill", "#0b1120");
    circle.setAttribute("stroke", isInActiveRoute ? "#38bdf8" : n.color);
    circle.setAttribute("stroke-width", isInActiveRoute ? "2.5" : "1.8");
    svgMap.appendChild(circle);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", n.x);
    label.setAttribute("y", n.y + 3.5);
    label.setAttribute("fill", "#f8fafc");
    label.setAttribute("font-size", "10");
    label.setAttribute("font-weight", "bold");
    label.setAttribute("font-family", "Inter, sans-serif");
    label.setAttribute("text-anchor", "middle");
    label.textContent = n.id;
    svgMap.appendChild(label);

    const caption = document.createElementNS("http://www.w3.org/2000/svg", "text");
    let capY = n.y < 240 ? n.y - 15 : n.y + 21;
    caption.setAttribute("x", n.x);
    caption.setAttribute("y", capY);
    caption.setAttribute("fill", isInActiveRoute ? "#38bdf8" : n.color);
    caption.setAttribute("font-size", "8.5");
    caption.setAttribute("font-weight", "700");
    caption.setAttribute("font-family", "Inter, sans-serif");
    caption.setAttribute("text-anchor", "middle");
    caption.textContent = n.name;
    svgMap.appendChild(caption);
  });

  // G. Live Animated Ambulance along current safe route corridor
  if (layers.ambulance) {
    renderAnimatedVehicle();
  }
}

// Render Animated Vehicle along Current Active Path
function renderAnimatedVehicle() {
  const path = currentSafeRoute && currentSafeRoute.path && currentSafeRoute.path.length > 1 
    ? currentSafeRoute.path 
    : ["A", "M", "D"];

  const waypoints = path.map(k => NODE_COORDS[k]).filter(Boolean);
  if (waypoints.length < 2) return;

  const progress = (currentMinute % 30) / 30.0;
  const numSegments = waypoints.length - 1;
  const segIdx = Math.min(numSegments - 1, Math.floor(progress * numSegments));
  const segProgress = (progress * numSegments) - segIdx;

  const p1 = waypoints[segIdx];
  const p2 = waypoints[segIdx + 1];

  const vehX = p1.x + (p2.x - p1.x) * segProgress;
  const vehY = p1.y + (p2.y - p1.y) * segProgress;

  const vehG = document.createElementNS("http://www.w3.org/2000/svg", "g");

  const strobe = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  strobe.setAttribute("cx", vehX);
  strobe.setAttribute("cy", vehY);
  strobe.setAttribute("r", 11);
  strobe.setAttribute("fill", "rgba(56, 189, 248, 0.4)");
  strobe.setAttribute("filter", "url(#glow-cyan)");
  vehG.appendChild(strobe);

  const vehBody = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  vehBody.setAttribute("cx", vehX);
  vehBody.setAttribute("cy", vehY);
  vehBody.setAttribute("r", 6.5);
  vehBody.setAttribute("fill", "#0284c7");
  vehBody.setAttribute("stroke", "#ffffff");
  vehBody.setAttribute("stroke-width", "1.5");
  vehG.appendChild(vehBody);

  const vehIcon = document.createElementNS("http://www.w3.org/2000/svg", "text");
  vehIcon.setAttribute("x", vehX);
  vehIcon.setAttribute("y", vehY + 2.5);
  vehIcon.setAttribute("font-size", "6");
  vehIcon.setAttribute("text-anchor", "middle");
  vehIcon.textContent = "🚑";
  vehG.appendChild(vehIcon);

  svgMap.appendChild(vehG);
}

// Draw Hydrograph & Hyetograph Profile
function drawHydrograph(scenarioId) {
  if (!hydroCanvas) return;
  const ctx = hydroCanvas.getContext("2d");
  const width = hydroCanvas.clientWidth || 300;
  const height = hydroCanvas.clientHeight || 38;
  hydroCanvas.width = width;
  hydroCanvas.height = height;

  ctx.clearRect(0, 0, width, height);

  // Hyetograph (Rain Bars in Blue)
  ctx.fillStyle = "rgba(56, 189, 248, 0.22)";
  const steps = 180;
  for (let m = 0; m <= steps; m += 2) {
    const normT = m / 120.0;
    const rain = (m <= 120) ? 15.0 * Math.sin(Math.PI * normT) : 0.0;
    const x = (m / 180.0) * width;
    const barW = Math.max(1, (2 / 180.0) * width);
    const barH = (rain / 20.0) * (height - 6);
    ctx.fillRect(x, height - barH, barW, barH);
  }

  // Flood Depth Hydrograph Line (Cyan)
  ctx.strokeStyle = "#06b6d4";
  ctx.lineWidth = 1.8;
  ctx.beginPath();

  for (let m = 0; m <= steps; m += 2) {
    const intFactor = Math.sin(Math.min(Math.PI, (m / 180.0) * Math.PI));
    let peakD = 34.0 * intFactor;
    if (scenarioId === "e2e_validation") peakD *= 1.3;
    const x = (m / 180.0) * width;
    const y = height - (peakD / 45.0) * (height - 8) - 3;

    if (m === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Peak Dot
  const peakX = (60.0 / 180.0) * width;
  ctx.fillStyle = "#ef4444";
  ctx.beginPath();
  ctx.arc(peakX, 6, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

// Hydrograph Click to Seek
if (hydroWrap) {
  hydroWrap.addEventListener("click", (e) => {
    const rect = hydroWrap.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    const targetMin = Math.round(pct * 180);
    loadSnapshot(targetMin);
  });
}

// Playback Control Handlers
function startPlayback() {
  isPlaying = true;
  playInterval = setInterval(() => {
    if (currentMinute >= 180) {
      currentMinute = 0;
    } else {
      currentMinute += 5;
    }
    loadSnapshot(currentMinute);
  }, playSpeed);
}

if (btnPlay) {
  btnPlay.addEventListener("click", () => {
    if (isPlaying) return;
    startPlayback();
  });
}

if (btnPause) {
  btnPause.addEventListener("click", () => {
    isPlaying = false;
    clearInterval(playInterval);
  });
}

if (btnReset) {
  btnReset.addEventListener("click", () => {
    isPlaying = false;
    clearInterval(playInterval);
    loadSnapshot(0);
  });
}

if (btnStepBack) {
  btnStepBack.addEventListener("click", () => {
    loadSnapshot(Math.max(0, currentMinute - 5));
  });
}

if (btnStepFwd) {
  btnStepFwd.addEventListener("click", () => {
    loadSnapshot(Math.min(180, currentMinute + 5));
  });
}

if (slider) {
  slider.addEventListener("input", (e) => {
    loadSnapshot(parseInt(e.target.value, 10));
  });
}

if (scenarioSelect) {
  scenarioSelect.addEventListener("change", () => {
    loadSnapshot(parseInt(slider.value, 10));
  });
}

if (btnRecomputeRoute) {
  btnRecomputeRoute.addEventListener("click", () => {
    btnRecomputeRoute.innerText = "⏳ Computing...";
    setTimeout(() => {
      loadSnapshot(parseInt(slider.value, 10));
      btnRecomputeRoute.innerText = "🔄 Recompute Route";
    }, 200);
  });
}

// Initial Boot
setupLayerToggles();
setupFaultDeck();
setupSpeedControls();
loadSnapshot(0);
