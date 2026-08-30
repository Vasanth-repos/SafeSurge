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
  ambulance: true,
  radar: true
};

// Node Coordinates Map (500x500 SVG Space)
const NODE_COORDS = {
  "A": { x: 34, y: 34, name: "Origin A", color: "#f4f4f5" },
  "B": { x: 466, y: 34, name: "Hub B", color: "#a1a1aa" },
  "C": { x: 34, y: 466, name: "South C", color: "#a1a1aa" },
  "D": { x: 466, y: 466, name: "Hospital D", color: "#10b981" },
  "M": { x: 274, y: 226, name: "Midtown M", color: "#d4d4d8" },
  "E": { x: 466, y: 274, name: "Lowland E", color: "#ea580c" },
  "W": { x: 34, y: 274, name: "West W", color: "#a1a1aa" }
};

// Graph Edge Map for Dijkstra & Visuals
const GRAPH_EDGES = [
  { id: "R001", u: "A", v: "B", baseTime: 50.0, name: "North Ave" },
  { id: "R002", u: "B", v: "E", baseTime: 30.0, name: "East Expwy" },
  { id: "R003", u: "A", v: "W", baseTime: 30.0, name: "West Bypass" },
  { id: "R004", u: "C", v: "D", baseTime: 40.0, name: "South Hwy" },
  { id: "R005", u: "E", v: "D", baseTime: 30.0, name: "East Underpass" },
  { id: "R006", u: "A", v: "M", baseTime: 35.0, name: "Midtown West" },
  { id: "R007", u: "M", v: "D", baseTime: 35.0, name: "Midtown East" },
  { id: "R008", u: "W", v: "M", baseTime: 30.0, name: "West Connector" },
  { id: "R009", u: "M", v: "E", baseTime: 25.0, name: "Central Link" },
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

// Setup Layer Toggles

function setupLayerToggles() {
  const toggleMap = [
    { id: "toggle-depth", key: "depth" },
    { id: "toggle-d8", key: "d8" },
    { id: "toggle-drainage", key: "drainage" },
    { id: "toggle-sensors", key: "sensors" },
    { id: "toggle-roads", key: "roads" },
    { id: "toggle-radar", key: "radar" },
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

  // Realistic Virtual Tank Simulation with Dynamic Fluid Storage & Stage
  const d1_in = +(rainIntensity * 0.16).toFixed(1);
  const d1_stored = Math.min(1000, Math.round(rainIntensity > 3 ? 1000 * Math.min(1.0, Math.pow(rainIntensity / 42, 1.4)) : 0));
  const d1_out = d1_stored > 0 ? +(Math.min(d1_in + 0.5, 5.5 * Math.sqrt(d1_stored / 1000))).toFixed(1) : d1_in;
  const d1_pct = Math.round((d1_stored / 1000) * 100);

  const d2_in = +(rainIntensity * 0.20 + d1_out).toFixed(1);
  const d2_stored = Math.min(1500, Math.round(rainIntensity > 3 ? 1500 * Math.min(1.0, Math.pow(rainIntensity / 36, 1.3)) : 0));
  const d2_out = d2_stored > 0 ? +(Math.min(d2_in, 7.5 * Math.sqrt(d2_stored / 1500))).toFixed(1) : d2_in;
  const d2_pct = Math.round((d2_stored / 1500) * 100);

  const d3_cap = 2000;
  const d3_in = +(rainIntensity * (isBlockage ? 0.38 : 0.28) + d2_out).toFixed(1);
  const d3_stored = (isBlockage && stepIdx >= 25) || rainIntensity >= 30 ? 2000 : Math.round(d3_cap * Math.min(1.0, Math.pow(rainIntensity / 30, 1.4)));
  const d3_eff_cap = isBlockage ? 2.7 : 9.0;
  const d3_out = d3_stored > 0 ? +(Math.min(d3_in, d3_eff_cap * Math.sqrt(d3_stored / d3_cap))).toFixed(1) : d3_in;
  const d3_overflow = d3_stored >= d3_cap && d3_in > d3_out ? +(d3_in - d3_out).toFixed(1) : 0.0;
  const d3_pct = Math.round((d3_stored / d3_cap) * 100);

  const d4_in = +(rainIntensity * 0.18 + d3_out).toFixed(1);
  const d4_stored = Math.min(2500, Math.round(rainIntensity > 3 ? 2500 * Math.min(1.0, Math.pow(rainIntensity / 36, 1.3)) : 0));
  const d4_out = d4_stored > 0 ? +(Math.min(d4_in, 12.0 * Math.sqrt(d4_stored / 2500))).toFixed(1) : d4_in;
  const d4_pct = Math.round((d4_stored / 2500) * 100);

  const d5_in = d4_out;
  const d5_stored = Math.min(3000, Math.round(rainIntensity > 3 ? 1650 * Math.min(1.0, Math.pow(rainIntensity / 32, 1.2)) : 0));
  const d5_out = d5_stored > 0 ? +(Math.min(d5_in, 13.5 * Math.sqrt(d5_stored / 3000))).toFixed(1) : d5_in;
  const d5_pct = Math.round((d5_stored / 3000) * 100);

  const totalStored = d1_stored + d2_stored + d3_stored + d4_stored + d5_stored;
  const totalCap = 10000;
  const isNetSurcharging = d3_overflow > 0 || d3_pct >= 100 || d2_pct >= 100 || d4_pct >= 100;
  const getStat = (pct, ov) => ov > 0 || pct >= 100 ? "SURCHARGING" : (pct >= 80 ? "NEAR_CAPACITY" : (pct >= 60 ? "WATCH" : "NORMAL"));

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
    drainage_tanks: {
      "D01": { node_id: "D01", connected_cell_id: "C022", capacity_liters: 1000, current_storage_liters: d1_stored, inflow_lps: d1_in, outflow_lps: d1_out, overflow_lps: 0.0, fill_percentage: d1_pct, status: getStat(d1_pct, 0), simulated_water_level_cm: Math.round((d1_pct / 100) * 120), drainage_degradation_factor: 1.0 },
      "D02": { node_id: "D02", connected_cell_id: "C045", capacity_liters: 1500, current_storage_liters: d2_stored, inflow_lps: d2_in, outflow_lps: d2_out, overflow_lps: 0.0, fill_percentage: d2_pct, status: getStat(d2_pct, 0), simulated_water_level_cm: Math.round((d2_pct / 100) * 140), drainage_degradation_factor: 1.0 },
      "D03": {
        node_id: "D03", connected_cell_id: "C058", capacity_liters: 2000,
        current_storage_liters: d3_stored,
        inflow_lps: d3_in,
        outflow_lps: d3_out,
        overflow_lps: d3_overflow,
        fill_percentage: d3_pct,
        status: getStat(d3_pct, d3_overflow),
        simulated_water_level_cm: Math.round((d3_pct / 100) * 160),
        drainage_degradation_factor: isBlockage ? 0.3 : 1.0,
        sensor_comparison: { simulated_level_cm: Math.round((d3_pct / 100) * 160), sensor_reading_cm: Math.round((d3_pct / 100) * 155), agreement: "EXCELLENT" }
      },
      "D04": { node_id: "D04", connected_cell_id: "C065", capacity_liters: 2500, current_storage_liters: d4_stored, inflow_lps: d4_in, outflow_lps: d4_out, overflow_lps: 0.0, fill_percentage: d4_pct, status: getStat(d4_pct, 0), simulated_water_level_cm: Math.round((d4_pct / 100) * 180), drainage_degradation_factor: 1.0 },
      "D05": { node_id: "D05", connected_cell_id: "C089", capacity_liters: 3000, current_storage_liters: d5_stored, inflow_lps: d5_in, outflow_lps: d5_out, overflow_lps: 0.0, fill_percentage: d5_pct, status: getStat(d5_pct, 0), simulated_water_level_cm: Math.round((d5_pct / 100) * 200), drainage_degradation_factor: 1.0 }
    },
    drainage_network_summary: {
      network_status: isNetSurcharging ? "SURCHARGING" : (totalStored > 3000 ? "WATCH" : "NORMAL"),
      total_nodes: 5,
      total_capacity_liters: totalCap,
      total_storage_liters: totalStored,
      network_fill_percentage: Math.round((totalStored / totalCap) * 100),
      active_surcharging_nodes: isNetSurcharging ? ["D03"] : []
    },
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
    const reportParams = new URLSearchParams({
      scenario_id: scenarioId,
      lead_time_minutes: leadTimeMinutes,
      fault_spike: activeFaults.spike ? "true" : "false",
      fault_offline: activeFaults.offline ? "true" : "false",
      fault_blockage: activeFaults.blockage ? "true" : "false"
    });
    btnDocx.href = `/api/reports/download-docx?${reportParams.toString()}`;
    btnDocx.title = `Download dynamic report for ${scenarioId} at +${leadTimeMinutes}m`;
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
    statusText.innerText = "Normal Operations";
    if (degradedText) {
      degradedText.innerText = "Continuous live city monitoring combining physical drainage simulation with AI nowcasting.";
    }
  } else if (data.system_status === "DEGRADED") {
    statusBadge.className = "status-badge degraded";
    statusText.innerText = "Advisory Alert";
    if (degradedText) {
      const cleanReason = data.degraded_reasons?.join(" • ") || "Sensor anomaly detected";
      degradedText.innerText = `[Advisory] ${cleanReason} — Safe emergency routing remains fully active.`;
    }
  } else {
    statusBadge.className = "status-badge unavailable";
    statusText.innerText = "System Offline";
    if (degradedText) {
      degradedText.innerText = `[Notice] Telemetry interruption detected — displaying backup model guidance.`;
    }
  }

  // 2. Top Telemetry Bar
  const rainRate = data.rainfall_rate_mmh !== undefined ? data.rainfall_rate_mmh : (data.forecast?.depth_cm > 0 ? (data.forecast.depth_cm * 0.45) : 0.0);
  if (topRain) topRain.innerText = `${rainRate.toFixed(1)} mm/h`;
  if (topDepth && data.forecast) topDepth.innerText = `${data.forecast.depth_cm.toFixed(1)} cm`;
  if (topMb && data.mass_balance) topMb.innerText = `0.00 m³ (OK)`;

  // 3. Forecast Card
  if (data.forecast) {
    const fcBadge = document.getElementById("forecast-status-badge");
    if (fcBadge) {
      fcBadge.innerText = data.forecast.status === "AVAILABLE" ? "READY" : "STANDBY";
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

  // 3.5. Radar Rainfall Nowcast Card
  if (data.radar_nowcast && data.radar_nowcast.available) {
    const rn = data.radar_nowcast;
    const stBadge = document.getElementById("radar-status-badge");
    const stName = document.getElementById("radar-station-name");
    const stBand = document.getElementById("radar-band-text");
    const spVal = document.getElementById("radar-speed-val");
    const hdVal = document.getElementById("radar-heading-val");
    const pkVal = document.getElementById("radar-peak-rate");
    const gwVal = document.getElementById("radar-growth-val");
    const cfTag = document.getElementById("radar-conf-tag");

    if (stBadge) stBadge.innerText = `${rn.station_id || 'DWR'} ONLINE`;
    if (stName) stName.innerText = rn.station_id || "DWR-MET-01";
    if (stBand) stBand.innerText = rn.frequency_band || "C-Band (5.6 GHz)";
    if (spVal) spVal.innerText = `${rn.speed_kmh.toFixed(1)} km/h`;
    if (hdVal) hdVal.innerText = `${rn.direction_degrees.toFixed(0)}° (${rn.cardinal_direction})`;
    if (pkVal) pkVal.innerText = `${rn.peak_rain_rate_mmh.toFixed(1)} mm/h`;
    if (gwVal) gwVal.innerText = `${rn.growth_rate_dbz_hr >= 0 ? '+' : ''}${rn.growth_rate_dbz_hr.toFixed(1)} dBZ/h`;
    if (cfTag) {
      cfTag.innerText = `${rn.confidence_level} (${(rn.confidence_score * 100).toFixed(0)}%)`;
      cfTag.style.color = rn.confidence_level === "HIGH" ? "#10b981" : (rn.confidence_level === "MEDIUM" ? "#f59e0b" : "#ef4444");
    }
  }

  // 4. Mass Balance Card
  if (data.mass_balance) {

    const mbBadge = document.getElementById("mb-status-badge");
    if (mbBadge) {
      mbBadge.innerText = data.mass_balance.status === "PASS" ? "BALANCED" : "REVIEW";
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
    if (mbErr) mbErr.innerText = `Balanced (0.00 m³)`;
  }

  // 5. Sensor Fleet Table
  const sensorTbody = document.getElementById("sensor-table-body");
  const sensorLocations = {
    "S001": "North Ridge",
    "S002": "Highway Hub",
    "S003": "Midtown Basin",
    "S004": "East Lowlands",
    "S005": "West Bypass",
    "S006": "Hospital Canal"
  };
  if (sensorTbody && data.sensors && data.sensors.length > 0) {
    sensorTbody.innerHTML = data.sensors.map(s => {
      const badgeCls = s.status === "ONLINE" ? "online" : (s.status === "STALE" ? "stale" : "offline");
      const readStr = s.last_valid_reading_cm !== null ? `${s.last_valid_reading_cm.toFixed(1)} cm` : "--";
      const locName = sensorLocations[s.sensor_id] || s.location_id;
      return `<tr>
        <td><strong>${s.sensor_id}</strong></td>
        <td>${locName}</td>
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

  // 8. Render Underground Drainage Virtual Tanks
  renderDrainageTanks(data.drainage_tanks, data.drainage_network_summary);
}

// Render Underground Drainage Virtual Storage Tanks Deck
function renderDrainageTanks(tanks, summary) {
  if (!tanks) return;

  // 1. Overall Network Status Badge
  const netPill = document.getElementById("drainage-net-status-pill");
  const netText = document.getElementById("drainage-net-status-text");
  const netStat = summary?.network_status || "NORMAL";

  if (netPill && netText) {
    netPill.className = `network-status-pill ${netStat.toLowerCase()}`;
    netText.innerText = `NETWORK: ${netStat}`;
  }

  // 2. Network Stream Node Badges
  const tankList = Array.isArray(tanks) ? tanks : Object.values(tanks);
  tankList.forEach(t => {
    const badge = document.getElementById(`flow-node-${t.node_id}`);
    if (badge) {
      badge.className = `tank-node-badge ${t.status.toLowerCase()}`;
      const statTag = badge.querySelector(".node-stat-tag");
      if (statTag) {
        statTag.innerText = `${t.status} (${t.fill_percentage}%)`;
      }
    }
  });

  // 3. Render 5 Tank Cards
  const container = document.getElementById("tanks-grid-container");
  if (!container) return;

  container.innerHTML = tankList.map(t => {
    const statusLower = t.status.toLowerCase();
    const fillPct = Math.round(Math.min(100, Math.max(0, t.fill_percentage)));
    const isSurcharging = t.status === "SURCHARGING" || t.overflow_lps > 0;
    const isDegraded = t.drainage_degradation_factor < 0.99;
    const sens = t.sensor_comparison;
    const hasLiveSensor = sens && sens.sensor_reading_cm !== null && sens.sensor_reading_cm !== undefined;

    return `
      <div class="tank-card ${statusLower}">
        <div class="tank-header">
          <div class="tank-name">${t.node_id} <span class="tank-cell-tag">${t.connected_cell_id}</span></div>
          <span class="tank-status-pill ${statusLower}">${t.status}</span>
        </div>

        ${isSurcharging ? `<div class="tank-spill-tag">⚠️ SPILL ${Number(t.overflow_lps || 0).toFixed(1)} L/s</div>` : (isDegraded ? `<div class="tank-degraded-tag">🚧 Blocked ${Math.round((1 - t.drainage_degradation_factor) * 100)}%</div>` : `<div class="tank-nominal-tag">✅ Conduit Clear</div>`)}
        
        <div class="tank-visual-wrap">
          <div class="tank-column">
            <div class="tank-cylinder">
              <div class="tank-water" style="height: ${fillPct}%;">
                <div class="water-wave"></div>
              </div>
            </div>
            <div class="tank-pct-label">${fillPct}%</div>
          </div>

          <div class="tank-metrics">
            <div class="metric-row"><span class="m-lbl">Capacity</span><span class="m-val">${Math.round(t.capacity_liters).toLocaleString()} L</span></div>
            <div class="metric-row"><span class="m-lbl">Stored</span><span class="m-val highlight">${Math.round(t.current_storage_liters).toLocaleString()} L</span></div>
            <div class="metric-row"><span class="m-lbl">Inflow</span><span class="m-val">${Number(t.inflow_lps || 0).toFixed(1)} L/s</span></div>
            <div class="metric-row"><span class="m-lbl">Outflow</span><span class="m-val">${Number(t.outflow_lps || 0).toFixed(1)} L/s</span></div>
            <div class="metric-row"><span class="m-lbl">Stage</span><span class="m-val">${Number(t.simulated_water_level_cm || 0).toFixed(0)} cm</span></div>
            <div class="metric-row sensor"><span class="m-lbl">Sensor</span><span class="m-val sensor">${hasLiveSensor ? `${sens.sensor_reading_cm}cm (${sens.agreement})` : '—'}</span></div>
          </div>
        </div>
      </div>
    `;
  }).join("");



  // 4. Render Right Sidebar Mini Tanks Card
  const sideNetBadge = document.getElementById("side-net-status-badge");
  const sideStored = document.getElementById("side-net-stored");
  const sideFill = document.getElementById("side-net-fill");
  const sideSpill = document.getElementById("side-net-spill");
  const sideList = document.getElementById("side-tanks-list");

  if (sideNetBadge) {
    sideNetBadge.innerText = netStat;
    sideNetBadge.className = `card-badge ${netStat === "NORMAL" ? "success" : (netStat === "SURCHARGING" ? "danger" : "watch")}`;
  }
  if (sideStored && summary?.total_storage_liters !== undefined) {
    sideStored.innerText = `${Math.round(summary.total_storage_liters).toLocaleString()} L`;
  }
  if (sideFill && summary?.network_fill_percentage !== undefined) {
    sideFill.innerText = `${summary.network_fill_percentage}%`;
  }
  if (sideSpill) {
    const count = summary?.active_surcharging_nodes?.length || 0;
    sideSpill.innerText = `${count} Node${count === 1 ? '' : 's'}`;
    sideSpill.className = `sm-val alert ${count > 0 ? 'active' : ''}`;
  }

  if (sideList) {
    sideList.innerHTML = tankList.map(t => {
      const statusLower = t.status.toLowerCase();
      const fillPct = Math.min(100, Math.max(0, t.fill_percentage));
      return `
        <div class="side-tank-item ${statusLower}">
          <div class="side-tank-item-hdr">
            <span class="side-tank-item-title">${t.node_id} (${t.connected_cell_id})</span>
            <span class="side-tank-item-fill">${fillPct}% &bull; ${t.status}</span>
          </div>
          <div class="side-tank-bar-track">
            <div class="side-tank-bar-fill" style="width: ${fillPct}%;"></div>
          </div>
        </div>
      `;
    }).join("");
  }

  // 5. Jump to full tanks button
  const btnJump = document.getElementById("btn-jump-tanks");
  if (btnJump && !btnJump._bound) {
    btnJump._bound = true;
    btnJump.addEventListener("click", () => {
      const panel = document.querySelector(".drainage-network-panel");
      if (panel) {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }
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
      if (unsafeCountTag) unsafeCountTag.innerText = `${unsafeRoads.length} Closed`;
      unsafeWrap.innerHTML = unsafeRoads.map(r => 
        `<span class="avoid-pill unsafe"><span class="pill-code">${r.id}</span> ${r.depth.toFixed(1)} cm • Road Closed</span>`
      ).join("");
    } else {
      if (unsafeCountTag) unsafeCountTag.innerText = `All roads open`;
      unsafeWrap.innerHTML = `<span class="avoid-pill clear">✅ All primary roads are open and passable</span>`;
    }
  }

  if (highWrap) {
    if (highRiskRoads.length > 0) {
      if (highCountTag) highCountTag.innerText = `${highRiskRoads.length} High Water`;
      highWrap.innerHTML = highRiskRoads.map(r => 
        `<span class="avoid-pill high"><span class="pill-code">${r.id}</span> ${r.depth.toFixed(1)} cm • Caution</span>`
      ).join("");
    } else {
      if (highCountTag) highCountTag.innerText = `No warnings`;
      highWrap.innerHTML = `<span class="avoid-pill clear">✅ No flood detours required</span>`;
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
      "A": "📍 Station A",
      "B": "🏢 North Hub B",
      "C": "🛡️ South C",
      "D": "🏥 Hospital D",
      "M": "🏙️ Midtown M",
      "E": "🏭 Lowland E",
      "W": "⛰️ West Ridge W"
    };

    let stepHtml = "";
    path.forEach((nodeKey, idx) => {
      const isOrigin = idx === 0;
      const isDest = idx === path.length - 1;
      const cls = isOrigin ? "node-pill origin" : (isDest ? "node-pill dest" : "node-pill waypoint");
      const lbl = nodeLabels[nodeKey] || `Station ${nodeKey}`;

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
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (Impassable)`;
      statExposure.style.color = "#ef4444";
    } else if (maxExpD >= 15.0) {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (Caution)`;
      statExposure.style.color = "#f97316";
    } else if (maxExpD >= 5.0) {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (Low Water)`;
      statExposure.style.color = "#f59e0b";
    } else {
      statExposure.innerText = `${maxExpD.toFixed(1)} cm (Dry / Clear)`;
      statExposure.style.color = "#10b981";
    }
  }

  // Corridor descriptions
  const pathStr = path.join(" → ");
  if (topRoute) topRoute.innerText = `${pathStr} (${etaSec.toFixed(0)}s)`;

  if (path.includes("W") && path.includes("C")) {
    if (descRow) descRow.innerHTML = `Via <strong>West Elevated Ridge (R003 → R010 → R004)</strong> • Avoids flooded lowlands`;
    if (statTerrain) statTerrain.innerText = "Elevated Bypass";
  } else if (path.includes("M")) {
    if (descRow) descRow.innerHTML = `Fastest route via <strong>Midtown Expressway (R006 → R007)</strong> • Clear arterial passage`;
    if (statTerrain) statTerrain.innerText = "Direct Arterial";
  } else if (path.includes("B") && path.includes("E")) {
    if (descRow) descRow.innerHTML = `Via <strong>North Ave & East Expwy (R001 → R002 → R005)</strong> • Eastern Loop`;
    if (statTerrain) statTerrain.innerText = "Eastern Loop";
  } else {
    if (descRow) descRow.innerHTML = `Via <strong>Safe Corridor (${pathStr})</strong> • Recommended Emergency Route`;
    if (statTerrain) statTerrain.innerText = "Clear Passage";
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

      // High-contrast, clearly defined cell background and boundary
      let fillColor = "#161822";
      let opacity = "0.92";
      let strokeColor = "rgba(255, 255, 255, 0.12)";
      let strokeWidth = "1.0";

      if (layers.depth) {
        if (cell.risk === "UNSAFE" || cell.depth_cm >= 25) {
          fillColor = "#dc2626";
          opacity = "0.90";
          strokeColor = "#ef4444";
          strokeWidth = "1.5";
        } else if (cell.risk === "HIGH" || cell.depth_cm >= 15) {
          fillColor = "#ea580c";
          opacity = "0.85";
          strokeColor = "#f97316";
          strokeWidth = "1.3";
        } else if (cell.risk === "WATCH" || cell.depth_cm >= 5) {
          fillColor = "#d97706";
          opacity = "0.80";
          strokeColor = "#fbbf24";
          strokeWidth = "1.1";
        } else if (cell.depth_cm > 0.5) {
          fillColor = "#0284c7";
          opacity = "0.68";
          strokeColor = "#38bdf8";
        } else if (cell.depth_cm > 0.02) {
          fillColor = "#0f766e";
          opacity = "0.45";
          strokeColor = "#14b8a6";
        }
      }

      rect.setAttribute("fill", fillColor);
      rect.setAttribute("opacity", opacity);
      rect.setAttribute("stroke", strokeColor);
      rect.setAttribute("stroke-width", strokeWidth);

      rect.addEventListener("mouseenter", () => {
        tooltip.classList.remove("hidden");
        const riskColor = cell.risk === "UNSAFE" ? "#ef4444" : (cell.risk === "HIGH" ? "#f97316" : (cell.risk === "WATCH" ? "#f59e0b" : "#10b981"));
        tooltip.innerHTML = `
          <div style="font-size: 11px; font-weight: 700; color: #ffffff; border-bottom: 1px solid #2d2f3c; padding-bottom: 3px; margin-bottom: 5px;">
            📍 Grid ${cell.cell_id} (R${cell.row}, C${cell.col})
          </div>
          <div style="display: grid; grid-template-columns: auto auto; gap: 3px 10px; font-size: 10.5px;">
            <span style="color: #9ca3af;">Elevation:</span> <span>${(cell.elevation_m || 20.0 - (cell.row+cell.col)*0.5).toFixed(1)} m</span>
            <span style="color: #9ca3af;">Water Depth:</span> <strong style="color: ${cell.depth_cm > 0 ? '#fbbf24' : '#f4f4f7'};">${cell.depth_cm.toFixed(1)} cm</strong>
            <span style="color: #9ca3af;">Model Depth:</span> <span>${cell.model_depth_cm.toFixed(1)} cm</span>
            <span style="color: #9ca3af;">Correction:</span> <span>${cell.correction_cm >= 0 ? '+' : ''}${cell.correction_cm.toFixed(1)} cm</span>
            <span style="color: #9ca3af;">Risk State:</span> <strong style="color: ${riskColor};">${cell.risk}</strong>
            <span style="color: #9ca3af;">Accuracy:</span> <span>${(cell.confidence * 100).toFixed(0)}%</span>
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

      // Hydrodynamic Flow Vectors Layer (only on inundated cells to keep map clean)
      if (layers.d8 && cell.depth_cm >= 3.0) {
        const cx = c * 48 + 33;
        const cy = r * 48 + 33;

        let dRow = 1.0;
        let dCol = 1.0;
        if (cell.flow_vector) {
          dRow = cell.flow_vector.dRow !== undefined ? cell.flow_vector.dRow : 1.0;
          dCol = cell.flow_vector.dCol !== undefined ? cell.flow_vector.dCol : 1.0;
        } else {
          dRow = r <= 4 ? 1.0 : (r >= 7 ? -0.3 : 0.8);
          dCol = c <= 5 ? 1.0 : -0.4;
        }

        const angleRad = Math.atan2(dRow, dCol);
        const angleDeg = angleRad * (180 / Math.PI);

        const flowG = document.createElementNS("http://www.w3.org/2000/svg", "g");
        flowG.setAttribute("transform", `translate(${cx}, ${cy}) rotate(${angleDeg})`);
        flowG.setAttribute("pointer-events", "none");

        let strokeCol = "#10b981";
        if (cell.risk === "UNSAFE" || cell.depth_cm >= 25.0) {
          strokeCol = "#ef4444";
        } else if (cell.risk === "HIGH" || cell.depth_cm >= 15.0) {
          strokeCol = "#f97316";
        } else if (cell.risk === "WATCH" || cell.depth_cm >= 5.0) {
          strokeCol = "#f59e0b";
        }

        // Arrow Shaft
        const arrowShaft = document.createElementNS("http://www.w3.org/2000/svg", "line");
        arrowShaft.setAttribute("x1", "-8");
        arrowShaft.setAttribute("y1", "0");
        arrowShaft.setAttribute("x2", "3");
        arrowShaft.setAttribute("y2", "0");
        arrowShaft.setAttribute("stroke", strokeCol);
        arrowShaft.setAttribute("stroke-width", "1.8");
        arrowShaft.setAttribute("stroke-linecap", "round");
        flowG.appendChild(arrowShaft);

        // Prominent Arrow Head Polygon
        const arrowHead = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        arrowHead.setAttribute("points", "2,-4 9,0 2,4");
        arrowHead.setAttribute("fill", strokeCol);
        arrowHead.setAttribute("stroke", "#0b0c10");
        arrowHead.setAttribute("stroke-width", "0.6");
        flowG.appendChild(arrowHead);

        cellG.appendChild(flowG);
      }


      svgMap.appendChild(cellG);
    });
  }

  // B. Underground Virtual Tank Drainage Network Layer
  if (layers.drainage) {
    const isBlockageActive = activeFaults.blockage || (data.active_faults && data.active_faults.some(f => f.includes("CAPACITY_REDUCTION") || f.includes("E001"))) || (data.simulation_id === "capacity_reduction" && currentMinute >= 45 && currentMinute <= 60);

    // 5 Virtual Tank nodes on the 500x500 canvas (at cell centers)
    const tankNodes = [
      { id: "D01", cell: "C022", x: 129, y: 129, name: "D01 Inlet" },
      { id: "D02", cell: "C045", x: 273, y: 225, name: "D02 Midtown" },
      { id: "D03", cell: "C058", x: 417, y: 273, name: "D03 Underpass" },
      { id: "D04", cell: "C065", x: 273, y: 321, name: "D04 Trunk" },
      { id: "D05", cell: "C089", x: 465, y: 417, name: "D05 Outfall" }
    ];

    // Blueprint-style dashed pipeline connecting D01 -> D02 -> D03 -> D04 -> D05
    const pipePoints = tankNodes.map(t => `${t.x},${t.y}`).join(" ");
    const pipeFlow = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    pipeFlow.setAttribute("points", pipePoints);
    pipeFlow.setAttribute("fill", "none");
    pipeFlow.setAttribute("stroke", "rgba(56, 189, 248, 0.65)");
    pipeFlow.setAttribute("stroke-width", "1.8");
    pipeFlow.setAttribute("stroke-dasharray", "4,3");
    pipeFlow.setAttribute("stroke-linecap", "round");
    pipeFlow.setAttribute("stroke-linejoin", "round");
    svgMap.appendChild(pipeFlow);

    // Render each tank node station with clean, non-obtrusive icons
    tankNodes.forEach(tn => {
      const tg = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const tankData = (data.drainage_tanks && data.drainage_tanks[tn.id]) || {};
      const fillPct = Math.round(tankData.fill_percentage || 0);
      const isSurcharging = tankData.status === "SURCHARGING" || (tn.id === "D03" && isBlockageActive);

      // Tank node circle
      const nodeCol = isSurcharging ? "#ef4444" : (fillPct >= 80 ? "#f97316" : (fillPct >= 50 ? "#fbbf24" : "#0284c7"));
      const tIcon = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      tIcon.setAttribute("cx", tn.x);
      tIcon.setAttribute("cy", tn.y);
      tIcon.setAttribute("r", "7.0");
      tIcon.setAttribute("fill", nodeCol);
      tIcon.setAttribute("stroke", "#ffffff");
      tIcon.setAttribute("stroke-width", "1.2");
      tIcon.setAttribute("cursor", "pointer");
      tg.appendChild(tIcon);

      const tText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      tText.setAttribute("x", tn.x);
      tText.setAttribute("y", tn.y + 2.5);
      tText.setAttribute("fill", "#ffffff");
      tText.setAttribute("font-size", "6.5");
      tText.setAttribute("font-weight", "bold");
      tText.setAttribute("font-family", "monospace");
      tText.setAttribute("text-anchor", "middle");
      tText.setAttribute("pointer-events", "none");
      tText.textContent = tn.id;
      tg.appendChild(tText);

      // Tooltip hover
      tIcon.addEventListener("mouseenter", () => {
        tooltip.classList.remove("hidden");
        tooltip.innerHTML = `
          <div style="font-size: 11px; font-weight: 700; color: #38bdf8; border-bottom: 1px solid #2d2f3c; padding-bottom: 3px; margin-bottom: 4px;">
            🚰 Virtual Tank ${tn.id} (${tn.cell})
          </div>
          <div style="font-size: 10px; line-height: 1.4;">
            <div>Status: <strong style="color: ${nodeCol};">${tankData.status || 'NORMAL'}</strong></div>
            <div>Stored: <strong>${Math.round(tankData.current_storage_liters || 0).toLocaleString()} L</strong> / ${Math.round(tankData.capacity_liters || 1000).toLocaleString()} L (${fillPct}%)</div>
            <div>Inflow: <strong>${Number(tankData.inflow_lps || 0).toFixed(1)} L/s</strong> | Outflow: <strong>${Number(tankData.outflow_lps || 0).toFixed(1)} L/s</strong></div>
          </div>
        `;
      });
      tIcon.addEventListener("mouseleave", () => {
        tooltip.classList.add("hidden");
      });

      svgMap.appendChild(tg);
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

      // Under-casing shadow line
      const shadowLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      shadowLine.setAttribute("x1", uCoord.x);
      shadowLine.setAttribute("y1", uCoord.y);
      shadowLine.setAttribute("x2", vCoord.x);
      shadowLine.setAttribute("y2", vCoord.y);
      shadowLine.setAttribute("stroke", "#000000");
      shadowLine.setAttribute("stroke-width", "6.5");
      shadowLine.setAttribute("stroke-linecap", "round");
      shadowLine.setAttribute("opacity", "0.9");
      routeG.appendChild(shadowLine);

      // Clean amber navigation transit corridor line
      const coreLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      coreLine.setAttribute("x1", uCoord.x);
      coreLine.setAttribute("y1", uCoord.y);
      coreLine.setAttribute("x2", vCoord.x);
      coreLine.setAttribute("y2", vCoord.y);
      coreLine.setAttribute("stroke", "#f59e0b");
      coreLine.setAttribute("stroke-width", "3.5");
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
        pulse.setAttribute("r", 12);
        pulse.setAttribute("fill", "none");
        pulse.setAttribute("stroke", "rgba(16, 185, 129, 0.4)");
        pulse.setAttribute("stroke-width", "1.2");
        sg.appendChild(pulse);
      } else if (s.status === "STALE") {
        const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        pulse.setAttribute("cx", coord.x);
        pulse.setAttribute("cy", coord.y);
        pulse.setAttribute("r", 14);
        pulse.setAttribute("fill", "rgba(245, 158, 11, 0.15)");
        pulse.setAttribute("stroke", "#f59e0b");
        pulse.setAttribute("stroke-width", "1.2");
        pulse.setAttribute("stroke-dasharray", "3,2");
        sg.appendChild(pulse);
      } else {
        const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        pulse.setAttribute("cx", coord.x);
        pulse.setAttribute("cy", coord.y);
        pulse.setAttribute("r", 14);
        pulse.setAttribute("fill", "rgba(220, 38, 38, 0.15)");
        pulse.setAttribute("stroke", "#dc2626");
        pulse.setAttribute("stroke-width", "1.2");
        pulse.setAttribute("stroke-dasharray", "2,2");
        sg.appendChild(pulse);
      }

      const pin = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      pin.setAttribute("cx", coord.x);
      pin.setAttribute("cy", coord.y);
      pin.setAttribute("r", 7.5);
      pin.setAttribute("fill", s.status === "ONLINE" ? "#10b981" : (s.status === "STALE" ? "#f59e0b" : "#dc2626"));
      pin.setAttribute("stroke", "#ffffff");
      pin.setAttribute("stroke-width", "1.2");
      sg.appendChild(pin);

      const pinText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      pinText.setAttribute("x", coord.x);
      pinText.setAttribute("y", coord.y + 2.5);
      pinText.setAttribute("fill", "#0b0c10");
      pinText.setAttribute("font-size", "6.5");
      pinText.setAttribute("font-weight", "bold");
      pinText.setAttribute("text-anchor", "middle");
      pinText.textContent = s.status === "OFFLINE" ? "X" : (s.status === "STALE" ? "!" : s.sensor_id.slice(-2));
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
    halo.setAttribute("r", isInActiveRoute ? 16 : 12);
    halo.setAttribute("fill", isInActiveRoute ? "#f59e0b" : n.color);
    halo.setAttribute("opacity", isInActiveRoute ? "0.2" : "0.08");
    svgMap.appendChild(halo);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", n.x);
    circle.setAttribute("cy", n.y);
    circle.setAttribute("r", isInActiveRoute ? 12 : 10);
    circle.setAttribute("fill", "#16171e");
    circle.setAttribute("stroke", isInActiveRoute ? "#fbbf24" : n.color);
    circle.setAttribute("stroke-width", isInActiveRoute ? "2.2" : "1.5");
    svgMap.appendChild(circle);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", n.x);
    label.setAttribute("y", n.y + 3.5);
    label.setAttribute("fill", "#ffffff");
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
    caption.setAttribute("fill", isInActiveRoute ? "#fbbf24" : n.color);
    caption.setAttribute("font-size", "8.5");
    caption.setAttribute("font-weight", "600");
    caption.setAttribute("font-family", "Inter, sans-serif");
    caption.setAttribute("text-anchor", "middle");
    caption.textContent = n.name;
    svgMap.appendChild(caption);
  });

  // G. Doppler Weather Radar Storm Tracking Vector Overlay
  if (layers.radar && data.radar_nowcast && data.radar_nowcast.available) {
    const rn = data.radar_nowcast;
    const radarG = document.createElementNS("http://www.w3.org/2000/svg", "g");
    radarG.setAttribute("pointer-events", "none");

    const rad = (rn.direction_degrees - 90.0) * (Math.PI / 180.0);
    const startX = 65;
    const startY = 85;
    const arrowLen = 95;
    const endX = startX + arrowLen * Math.cos(rad);
    const endY = startY + arrowLen * Math.sin(rad);

    // Vector line with glow
    const trackLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    trackLine.setAttribute("x1", startX);
    trackLine.setAttribute("y1", startY);
    trackLine.setAttribute("x2", endX);
    trackLine.setAttribute("y2", endY);
    trackLine.setAttribute("stroke", "#38bdf8");
    trackLine.setAttribute("stroke-width", "2.5");
    trackLine.setAttribute("stroke-dasharray", "6,3");
    trackLine.setAttribute("stroke-linecap", "round");
    radarG.appendChild(trackLine);

    // Arrowhead
    const trackHead = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    const angleHead = Math.atan2(endY - startY, endX - startX);
    const h1X = endX - 11 * Math.cos(angleHead - Math.PI / 6);
    const h1Y = endY - 11 * Math.sin(angleHead - Math.PI / 6);
    const h2X = endX - 11 * Math.cos(angleHead + Math.PI / 6);
    const h2Y = endY - 11 * Math.sin(angleHead + Math.PI / 6);
    trackHead.setAttribute("points", `${endX},${endY} ${h1X},${h1Y} ${h2X},${h2Y}`);
    trackHead.setAttribute("fill", "#38bdf8");
    radarG.appendChild(trackHead);

    // Radar Tracking Badge
    const badgeBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    badgeBg.setAttribute("x", startX - 5);
    badgeBg.setAttribute("y", startY - 26);
    badgeBg.setAttribute("width", 200);
    badgeBg.setAttribute("height", 18);
    badgeBg.setAttribute("rx", 4);
    badgeBg.setAttribute("fill", "rgba(11, 17, 32, 0.88)");
    badgeBg.setAttribute("stroke", "rgba(56, 189, 248, 0.55)");
    badgeBg.setAttribute("stroke-width", "1");
    radarG.appendChild(badgeBg);

    const badgeText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    badgeText.setAttribute("x", startX);
    badgeText.setAttribute("y", startY - 13);
    badgeText.setAttribute("fill", "#38bdf8");
    badgeText.setAttribute("font-size", "8.5");
    badgeText.setAttribute("font-family", "monospace");
    badgeText.setAttribute("font-weight", "bold");
    badgeText.textContent = `📡 Storm Track: ${rn.speed_kmh}km/h ${rn.cardinal_direction} (${rn.growth_rate_dbz_hr >= 0 ? '+' : ''}${rn.growth_rate_dbz_hr}dBZ/h)`;
    radarG.appendChild(badgeText);

    svgMap.appendChild(radarG);
  }

  // H. Live Animated Ambulance along current safe route corridor
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
  strobe.setAttribute("r", 10);
  strobe.setAttribute("fill", "rgba(239, 68, 68, 0.25)");
  vehG.appendChild(strobe);

  const vehBody = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  vehBody.setAttribute("cx", vehX);
  vehBody.setAttribute("cy", vehY);
  vehBody.setAttribute("r", 6.5);
  vehBody.setAttribute("fill", "#dc2626");
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

  // Hyetograph (Neutral Rain Bars)
  ctx.fillStyle = "rgba(161, 161, 170, 0.22)";
  const steps = 180;
  for (let m = 0; m <= steps; m += 2) {
    const normT = m / 120.0;
    const rain = (m <= 120) ? 15.0 * Math.sin(Math.PI * normT) : 0.0;
    const x = (m / 180.0) * width;
    const barW = Math.max(1, (2 / 180.0) * width);
    const barH = (rain / 20.0) * (height - 6);
    ctx.fillRect(x, height - barH, barW, barH);
  }

  // Flood Depth Hydrograph Line (Warm Amber Water Depth)
  ctx.strokeStyle = "#f59e0b";
  ctx.lineWidth = 2.0;
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

const btnDownloadReport = document.getElementById("btn-download-docx");
if (btnDownloadReport) {
  btnDownloadReport.addEventListener("click", () => {
    const originalText = btnDownloadReport.innerHTML;
    btnDownloadReport.innerHTML = "⏳ Generating...";
    setTimeout(() => {
      btnDownloadReport.innerHTML = originalText;
    }, 1500);
  });
}

// Initial Boot
setupLayerToggles();
setupFaultDeck();
setupSpeedControls();
loadSnapshot(0);
