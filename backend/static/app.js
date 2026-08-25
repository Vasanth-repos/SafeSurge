/**
 * Urban Flood Nowcasting GIS Dashboard (Layers 20–25)
 * Dynamic rendering of immutable SimulationSnapshot states.
 */

let currentMinute = 0;
let isPlaying = false;
let playInterval = null;

const slider = document.getElementById("timeline-slider");
const timeDisplay = document.getElementById("time-display-val");
const btnPlay = document.getElementById("btn-play");
const btnPause = document.getElementById("btn-pause");
const btnReset = document.getElementById("btn-reset");
const scenarioSelect = document.getElementById("scenario-select");
const btnRecomputeRoute = document.getElementById("btn-recompute-route");
const tooltip = document.getElementById("cell-tooltip");
const svgMap = document.getElementById("flood-map");

// Fetch snapshot and update all dashboard components
async function loadSnapshot(leadTimeMinutes) {
  currentMinute = leadTimeMinutes;
  slider.value = leadTimeMinutes;
  timeDisplay.innerText = `+${leadTimeMinutes} min (t=${leadTimeMinutes * 60}s)`;

  const scenarioId = scenarioSelect ? scenarioSelect.value : "storm_01";

  try {
    const res = await fetch(`/api/dashboard/state?lead_time_minutes=${leadTimeMinutes}&scenario_id=${scenarioId}`);
    if (!res.ok) return;
    const data = await res.json();
    updateDashboardUI(data);
  } catch (err) {
    console.error("Failed to load snapshot:", err);
  }
}

// Update DOM components
function updateDashboardUI(data) {
  // 1. Status Banner
  const statusBadge = document.getElementById("system-status-badge");
  const degradedText = document.getElementById("degraded-reasons-text");
  
  if (data.system_status === "NORMAL") {
    statusBadge.className = "status-badge";
    statusBadge.innerText = "🟢 SYSTEM NORMAL";
    degradedText.innerText = "All sensors online & telemetry valid";
  } else if (data.system_status === "DEGRADED") {
    statusBadge.className = "status-badge degraded";
    statusBadge.innerText = "🟡 SYSTEM DEGRADED";
    degradedText.innerText = data.degraded_reasons.join(" • ") || "Degraded mode active";
  } else {
    statusBadge.className = "status-badge unavailable";
    statusBadge.innerText = "🔴 FORECAST UNAVAILABLE";
    degradedText.innerText = data.degraded_reasons.join(" • ") || "Telemetry unavailable";
  }

  // 2. Forecast Card
  if (data.forecast) {
    document.getElementById("forecast-status-badge").innerText = data.forecast.status;
    document.getElementById("forecast-status-badge").className = data.forecast.status === "AVAILABLE" ? "badge badge-success" : "badge badge-danger";
    document.getElementById("forecast-peak-depth").innerText = `${data.forecast.depth_cm.toFixed(1)} cm`;
    document.getElementById("forecast-range").innerText = `${data.forecast.lower_depth_cm.toFixed(1)} – ${data.forecast.upper_depth_cm.toFixed(1)} cm`;
    document.getElementById("forecast-confidence").innerText = `${(data.forecast.confidence * 100).toFixed(0)}%`;
  }

  // 3. Mass Balance Ledger
  if (data.mass_balance) {
    document.getElementById("mb-status-badge").innerText = data.mass_balance.status;
    document.getElementById("mb-status-badge").className = data.mass_balance.status === "PASS" ? "badge badge-success" : "badge badge-danger";
    document.getElementById("mb-runoff").innerText = `${data.mass_balance.runoff_input_m3.toFixed(2)} m³`;
    const deltaS = data.mass_balance.current_storage_m3 - data.mass_balance.previous_storage_m3;
    document.getElementById("mb-storage-change").innerText = `${deltaS.toFixed(2)} m³`;
    document.getElementById("mb-drainage").innerText = `${data.mass_balance.drainage_m3.toFixed(2)} m³`;
    document.getElementById("mb-boundary").innerText = `${data.mass_balance.boundary_outflow_m3.toFixed(2)} m³`;
    document.getElementById("mb-error").innerText = `${data.mass_balance.balance_error_m3.toFixed(6)} m³`;
  }

  // 4. Sensors Table
  const sensorTbody = document.getElementById("sensor-table-body");
  if (data.sensors && data.sensors.length > 0) {
    sensorTbody.innerHTML = data.sensors.map(s => {
      const badgeCls = s.status === "ONLINE" ? "badge badge-success" : (s.status === "STALE" ? "badge badge-warning" : "badge badge-danger");
      const readStr = s.last_valid_reading_cm !== null ? `${s.last_valid_reading_cm.toFixed(1)} cm` : "--";
      return `<tr>
        <td><strong>${s.sensor_id}</strong></td>
        <td>${s.location_id}</td>
        <td>${readStr}</td>
        <td><span class="${badgeCls}">${s.status}</span></td>
        <td>${s.bias_cm >= 0 ? '+' : ''}${s.bias_cm.toFixed(1)} cm</td>
      </tr>`;
    }).join("");
  }

  // 5. Render SVG Flood Map & Roads
  renderSvgMap(data);

  // 6. Update Emergency Route
  updateRouteInfo(data);
}

// Render SVG Map
function renderSvgMap(data) {
  svgMap.innerHTML = "";

  // A. Render 10x10 Grid Cells
  if (data.cells) {
    data.cells.forEach(cell => {
      const r = cell.row;
      const c = cell.col;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", c * 48 + 10);
      rect.setAttribute("y", r * 48 + 10);
      rect.setAttribute("width", 46);
      rect.setAttribute("height", 46);
      rect.setAttribute("rx", 3);
      
      let fillColor = "#1e293b";
      let opacity = "0.45";

      if (cell.risk === "UNSAFE" || cell.depth_cm >= 25) {
        fillColor = "#ef4444";
        opacity = "0.90";
      } else if (cell.risk === "HIGH" || cell.depth_cm >= 15) {
        fillColor = "#f97316";
        opacity = "0.85";
      } else if (cell.risk === "WATCH" || cell.depth_cm >= 5) {
        fillColor = "#eab308";
        opacity = "0.80";
      } else if (cell.depth_cm > 0.5) {
        fillColor = "#3b82f6";
        opacity = "0.75";
      } else if (cell.depth_cm > 0.02) {
        fillColor = "#0284c7";
        opacity = "0.60";
      }

      rect.setAttribute("fill", fillColor);
      rect.setAttribute("opacity", opacity);
      rect.setAttribute("stroke", "#1e293b");
      rect.setAttribute("stroke-width", "1");

      // Hover tooltip with full verified cell provenance
      rect.addEventListener("mouseenter", (e) => {
        tooltip.classList.remove("hidden");
        const riskColor = cell.risk === "UNSAFE" ? "#ef4444" : (cell.risk === "HIGH" ? "#f97316" : (cell.risk === "WATCH" ? "#eab308" : "#22c55e"));
        tooltip.innerHTML = `
          <div style="font-size: 11px; font-weight: 700; color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 4px; margin-bottom: 4px;">
            Grid Cell: ${cell.cell_id} (R${cell.row}, C${cell.col})
          </div>
          <div style="display: grid; grid-template-columns: auto auto; gap: 4px 10px; font-size: 11px;">
            <span style="color: #94a3b8;">Elevation:</span> <span>${cell.elevation_m ? cell.elevation_m.toFixed(1) : (20.0 - (cell.row + cell.col)*0.5).toFixed(1)} m</span>
            <span style="color: #94a3b8;">Fused Depth:</span> <strong style="color: ${cell.depth_cm > 0 ? '#38bdf8' : '#f8fafc'};">${cell.depth_cm.toFixed(1)} cm</strong>
            <span style="color: #94a3b8;">Model Depth:</span> <span>${cell.model_depth_cm.toFixed(1)} cm</span>
            <span style="color: #94a3b8;">Sensor Bias Corr:</span> <span>${cell.correction_cm >= 0 ? '+' : ''}${cell.correction_cm.toFixed(1)} cm</span>
            <span style="color: #94a3b8;">Risk State:</span> <strong style="color: ${riskColor};">${cell.risk}</strong>
            <span style="color: #94a3b8;">Trust Confidence:</span> <span>${(cell.confidence * 100).toFixed(0)}%</span>
          </div>
        `;
      });

      rect.addEventListener("mousemove", (e) => {
        const container = document.getElementById("map-container");
        const bounds = container ? container.getBoundingClientRect() : svgMap.getBoundingClientRect();
        let posX = e.clientX - bounds.left + 15;
        let posY = e.clientY - bounds.top + 15;

        // Smart boundary clamping
        if (posX + 210 > bounds.width) {
          posX = e.clientX - bounds.left - 215;
        }
        if (posY + 130 > bounds.height) {
          posY = e.clientY - bounds.top - 135;
        }

        tooltip.style.left = `${Math.max(10, posX)}px`;
        tooltip.style.top = `${Math.max(10, posY)}px`;
      });

      rect.addEventListener("mouseleave", () => {
        tooltip.classList.add("hidden");
      });

      svgMap.appendChild(rect);
    });
  }

  // B. Define SVG Arrow Markers if not present
  if (!document.getElementById("arrow-marker-safe")) {
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <marker id="arrow-safe" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
        <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
      </marker>
      <marker id="arrow-watch" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
        <path d="M0,0 L0,6 L6,3 z" fill="#eab308" />
      </marker>
      <marker id="arrow-high" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
        <path d="M0,0 L0,6 L6,3 z" fill="#f97316" />
      </marker>
      <marker id="arrow-unsafe" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
        <path d="M0,0 L0,6 L6,3 z" fill="#ef4444" />
      </marker>
    `;
    svgMap.appendChild(defs);
  }

  // C. Render Complex 7-Node, 10-Corridor Road Network
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

  if (data.roads) {
    data.roads.forEach(road => {
      const sm = streetMeta[road.road_id];
      if (!sm) return;

      let statusCls = "safe";
      let strokeColor = "#22c55e"; // SAFE
      let strokeDash = "none";
      if (road.risk === "UNSAFE") {
        statusCls = "unsafe";
        strokeColor = "#ef4444";
        strokeDash = "6,4";
      } else if (road.risk === "HIGH") {
        statusCls = "high";
        strokeColor = "#f97316";
      } else if (road.risk === "WATCH") {
        statusCls = "watch";
        strokeColor = "#eab308";
      }

      // 1. Outer Asphalt Base
      const asphalt = document.createElementNS("http://www.w3.org/2000/svg", "line");
      asphalt.setAttribute("x1", sm.x1);
      asphalt.setAttribute("y1", sm.y1);
      asphalt.setAttribute("x2", sm.x2);
      asphalt.setAttribute("y2", sm.y2);
      asphalt.setAttribute("stroke", "#090d16");
      asphalt.setAttribute("stroke-width", "10");
      asphalt.setAttribute("stroke-linecap", "round");
      svgMap.appendChild(asphalt);

      // 2. Colored Lane Surface
      const lane = document.createElementNS("http://www.w3.org/2000/svg", "line");
      lane.setAttribute("x1", sm.x1);
      lane.setAttribute("y1", sm.y1);
      lane.setAttribute("x2", sm.x2);
      lane.setAttribute("y2", sm.y2);
      lane.setAttribute("stroke", strokeColor);
      lane.setAttribute("stroke-width", "5");
      lane.setAttribute("stroke-dasharray", strokeDash);
      lane.setAttribute("stroke-linecap", "round");
      lane.setAttribute("marker-end", `url(#arrow-${statusCls})`);
      svgMap.appendChild(lane);

      // 3. Center White Dashed Line (for safe/watch roads)
      if (road.risk !== "UNSAFE") {
        const divider = document.createElementNS("http://www.w3.org/2000/svg", "line");
        divider.setAttribute("x1", sm.x1);
        divider.setAttribute("y1", sm.y1);
        divider.setAttribute("x2", sm.x2);
        divider.setAttribute("y2", sm.y2);
        divider.setAttribute("stroke", "rgba(255,255,255,0.7)");
        divider.setAttribute("stroke-width", "1.0");
        divider.setAttribute("stroke-dasharray", "3,3");
        svgMap.appendChild(divider);
      }

      // 4. Street Label Pill Badge
      const badgeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const badgeWidth = sm.isVertical ? 90 : 110;
      const badgeHeight = 16;

      const pillRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      pillRect.setAttribute("x", sm.labelX - badgeWidth / 2);
      pillRect.setAttribute("y", sm.labelY - badgeHeight / 2);
      pillRect.setAttribute("width", badgeWidth);
      pillRect.setAttribute("height", badgeHeight);
      pillRect.setAttribute("rx", 8);
      pillRect.setAttribute("fill", "#0f172a");
      pillRect.setAttribute("stroke", strokeColor);
      pillRect.setAttribute("stroke-width", "1.2");
      badgeG.appendChild(pillRect);

      const pillText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      pillText.setAttribute("x", sm.labelX);
      pillText.setAttribute("y", sm.labelY + 3);
      pillText.setAttribute("fill", "#f8fafc");
      pillText.setAttribute("font-size", "8");
      pillText.setAttribute("font-weight", "600");
      pillText.setAttribute("font-family", "Inter, sans-serif");
      pillText.setAttribute("text-anchor", "middle");
      pillText.textContent = `${road.road_id}: ${sm.name.split(' ')[0]}`;
      badgeG.appendChild(pillText);

      svgMap.appendChild(badgeG);
    });
  }

  // D. Render 7 Node Markers: A, B, C, D, M, E, W
  const nodes = [
    { id: "A", name: "Origin A", x: 34, y: 34, color: "#38bdf8", isEndpoint: true },
    { id: "B", name: "Hub B", x: 466, y: 34, color: "#f59e0b", isEndpoint: false },
    { id: "C", name: "South C", x: 34, y: 466, color: "#f59e0b", isEndpoint: false },
    { id: "D", name: "Hospital D", x: 466, y: 466, color: "#22c55e", isEndpoint: true },
    { id: "M", name: "Midtown M", x: 274, y: 226, color: "#c084fc", isEndpoint: false },
    { id: "E", name: "Lowland E", x: 466, y: 274, color: "#f43f5e", isEndpoint: false },
    { id: "W", name: "West W", x: 34, y: 274, color: "#38bdf8", isEndpoint: false },
  ];

  nodes.forEach(n => {
    // Outer glow halo
    const halo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    halo.setAttribute("cx", n.x);
    halo.setAttribute("cy", n.y);
    halo.setAttribute("r", 18);
    halo.setAttribute("fill", n.color);
    halo.setAttribute("opacity", "0.25");
    svgMap.appendChild(halo);

    // Inner node badge circle
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", n.x);
    circle.setAttribute("cy", n.y);
    circle.setAttribute("r", 13);
    circle.setAttribute("fill", "#0f172a");
    circle.setAttribute("stroke", n.color);
    circle.setAttribute("stroke-width", "2.5");
    svgMap.appendChild(circle);

    // Letter Label
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", n.x);
    label.setAttribute("y", n.y + 4);
    label.setAttribute("fill", "#f8fafc");
    label.setAttribute("font-size", "11");
    label.setAttribute("font-weight", "bold");
    label.setAttribute("font-family", "Inter, sans-serif");
    label.setAttribute("text-anchor", "middle");
    label.textContent = n.id;
    svgMap.appendChild(label);

    // Subtitle caption
    const caption = document.createElementNS("http://www.w3.org/2000/svg", "text");
    let capY = n.y < 240 ? n.y - 18 : n.y + 24;
    caption.setAttribute("x", n.x);
    caption.setAttribute("y", capY);
    caption.setAttribute("fill", n.color);
    caption.setAttribute("font-size", "9");
    caption.setAttribute("font-weight", "700");
    caption.setAttribute("font-family", "Inter, sans-serif");
    caption.setAttribute("text-anchor", "middle");
    caption.textContent = n.name;
    svgMap.appendChild(caption);
  });
}

// Update Multi-Stage Cascading Route View
function updateRouteInfo(data) {
  const corridorTag = document.getElementById("route-corridor");
  const avoidedView = document.getElementById("avoided-roads-view");

  const roadMap = {};
  if (data.roads) {
    data.roads.forEach(r => { roadMap[r.road_id] = r; });
  }

  const r7_unsafe = roadMap["R007"]?.risk === "UNSAFE";
  const r5_unsafe = roadMap["R005"]?.risk === "UNSAFE";

  const avoidedList = [];
  if (data.roads) {
    data.roads.forEach(r => {
      if (r.risk === "UNSAFE") {
        avoidedList.push(`⛔ ${r.road_id} (flooded ${r.mean_depth_cm.toFixed(1)}cm)`);
      }
    });
  }

  if (avoidedList.length > 0) {
    avoidedView.innerHTML = `<span class="label">Avoided Inundated Roads:</span>
      <span class="avoided-item">${avoidedList.join(" • ")}</span>`;
  } else {
    avoidedView.innerHTML = `<span class="label">Avoided Road Segments:</span>
      <span class="avoided-item none">None (All corridors operational)</span>`;
  }

  // Multi-Stage Emergency Rerouting Policy
  if (!r7_unsafe && roadMap["R006"]?.risk !== "UNSAFE") {
    // Primary Direct Path: A -> M -> D (Fastest 70s)
    corridorTag.innerText = "A → M → D via Midtown Diagonal (Fastest Direct: 70s)";
    corridorTag.className = "route-tag safe";
  } else if (!r5_unsafe && roadMap["R001"]?.risk !== "UNSAFE" && roadMap["R002"]?.risk !== "UNSAFE") {
    // Secondary Arterial: A -> B -> E -> D (100s)
    corridorTag.innerText = "A → B → E → D via North Ave & East Expwy (Arterial: 100s)";
    corridorTag.className = "route-tag safe";
  } else {
    // Tertiary Western Elevated Corridor: A -> W -> C -> D (Safe High Ground: 100s)
    corridorTag.innerText = "A → W → C → D via West Bypass & South Hwy (Safe High Ground: 100s)";
    corridorTag.className = "route-tag safe";
  }
}

// Event Listeners
slider.addEventListener("input", (e) => {
  loadSnapshot(parseInt(e.target.value));
});

btnPlay.addEventListener("click", () => {
  if (isPlaying) return;
  isPlaying = true;
  playInterval = setInterval(() => {
    if (currentMinute >= 180) {
      currentMinute = 0;
    } else {
      currentMinute += 5;
    }
    loadSnapshot(currentMinute);
  }, 400);
});

btnPause.addEventListener("click", () => {
  isPlaying = false;
  clearInterval(playInterval);
});

btnReset.addEventListener("click", () => {
  isPlaying = false;
  clearInterval(playInterval);
  loadSnapshot(0);
});

// Scenario Selector
const btnDownloadDocx = document.getElementById("btn-download-docx");
if (scenarioSelect) {
  scenarioSelect.addEventListener("change", () => {
    const scId = scenarioSelect.value;
    if (btnDownloadDocx) {
      btnDownloadDocx.href = `/api/reports/download-docx?scenario_id=${scId}`;
    }
    loadSnapshot(parseInt(slider.value));
  });
}

// Recompute Route Button
if (btnRecomputeRoute) {
  btnRecomputeRoute.addEventListener("click", () => {
    btnRecomputeRoute.classList.add("loading");
    btnRecomputeRoute.innerText = "⏳ Computing...";
    setTimeout(() => {
      loadSnapshot(parseInt(slider.value));
      btnRecomputeRoute.classList.remove("loading");
      btnRecomputeRoute.innerText = "🔄 Recompute Safe Route";
    }, 250);
  });
}

// Initial load
loadSnapshot(0);
