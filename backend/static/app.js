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

  try {
    const res = await fetch(`/api/dashboard/state?lead_time_minutes=${leadTimeMinutes}`);
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
      if (cell.risk === "UNSAFE") fillColor = "#ef4444";
      else if (cell.risk === "HIGH") fillColor = "#f97316";
      else if (cell.risk === "WATCH") fillColor = "#eab308";
      else if (cell.depth_cm > 0.5) fillColor = "#3b82f6";

      rect.setAttribute("fill", fillColor);
      rect.setAttribute("opacity", cell.depth_cm > 0 ? "0.85" : "0.4");
      rect.setAttribute("stroke", "#334155");
      rect.setAttribute("stroke-width", "1");

      // Hover tooltip
      rect.addEventListener("mouseenter", (e) => {
        tooltip.classList.remove("hidden");
        tooltip.innerHTML = `
          <strong>Cell: ${cell.cell_id}</strong><br/>
          Depth: <strong>${cell.depth_cm.toFixed(1)} cm</strong><br/>
          Model: ${cell.model_depth_cm.toFixed(1)} cm (Corr: ${cell.correction_cm >= 0 ? '+' : ''}${cell.correction_cm.toFixed(1)}cm)<br/>
          Risk: <strong>${cell.risk}</strong> | Conf: ${(cell.confidence * 100).toFixed(0)}%
        `;
      });
      rect.addEventListener("mousemove", (e) => {
        const bounds = svgMap.getBoundingClientRect();
        tooltip.style.left = `${e.clientX - bounds.left + 15}px`;
        tooltip.style.top = `${e.clientY - bounds.top + 15}px`;
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

  // C. Render Road Network with Double-Lane Asphalt & Street Badges
  const streetMeta = {
    "R001": { name: "North Ave (A → B)", x1: 34, y1: 34, x2: 466, y2: 34, labelX: 250, labelY: 34, isVertical: false },
    "R002": { name: "East Expwy (B → D)", x1: 466, y1: 34, x2: 466, y2: 466, labelX: 466, labelY: 250, isVertical: true },
    "R003": { name: "West Bypass (A → C)", x1: 34, y1: 34, x2: 34, y2: 466, labelX: 34, labelY: 250, isVertical: true },
    "R004": { name: "South Blvd (C → D)", x1: 34, y1: 466, x2: 466, y2: 466, labelX: 250, labelY: 466, isVertical: false },
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
      asphalt.setAttribute("stroke-width", "12");
      asphalt.setAttribute("stroke-linecap", "round");
      svgMap.appendChild(asphalt);

      // 2. Colored Lane Surface
      const lane = document.createElementNS("http://www.w3.org/2000/svg", "line");
      lane.setAttribute("x1", sm.x1);
      lane.setAttribute("y1", sm.y1);
      lane.setAttribute("x2", sm.x2);
      lane.setAttribute("y2", sm.y2);
      lane.setAttribute("stroke", strokeColor);
      lane.setAttribute("stroke-width", "6");
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
        divider.setAttribute("stroke-width", "1.2");
        divider.setAttribute("stroke-dasharray", "4,4");
        svgMap.appendChild(divider);
      }

      // 4. Street Label Pill Badge
      const badgeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const badgeWidth = sm.isVertical ? 110 : 130;
      const badgeHeight = 18;

      const pillRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      pillRect.setAttribute("x", sm.labelX - badgeWidth / 2);
      pillRect.setAttribute("y", sm.labelY - badgeHeight / 2);
      pillRect.setAttribute("width", badgeWidth);
      pillRect.setAttribute("height", badgeHeight);
      pillRect.setAttribute("rx", 9);
      pillRect.setAttribute("fill", "#0f172a");
      pillRect.setAttribute("stroke", strokeColor);
      pillRect.setAttribute("stroke-width", "1.5");
      badgeG.appendChild(pillRect);

      const pillText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      pillText.setAttribute("x", sm.labelX);
      pillText.setAttribute("y", sm.labelY + 4);
      pillText.setAttribute("fill", "#f8fafc");
      pillText.setAttribute("font-size", "9");
      pillText.setAttribute("font-weight", "600");
      pillText.setAttribute("font-family", "Inter, sans-serif");
      pillText.setAttribute("text-anchor", "middle");
      pillText.textContent = `${road.road_id}: ${sm.name.split(' ')[0]} ${sm.name.split(' ')[1]}`;
      badgeG.appendChild(pillText);

      svgMap.appendChild(badgeG);
    });
  }

  // D. Render Node Markers: A, B, C, D
  const nodes = [
    { id: "A", name: "Origin A", x: 34, y: 34, color: "#38bdf8", isEndpoint: true },
    { id: "B", name: "Node B", x: 466, y: 34, color: "#f59e0b", isEndpoint: false },
    { id: "C", name: "Node C", x: 34, y: 466, color: "#f59e0b", isEndpoint: false },
    { id: "D", name: "Dest D", x: 466, y: 466, color: "#22c55e", isEndpoint: true },
  ];

  nodes.forEach(n => {
    // Outer glow halo
    const halo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    halo.setAttribute("cx", n.x);
    halo.setAttribute("cy", n.y);
    halo.setAttribute("r", 20);
    halo.setAttribute("fill", n.color);
    halo.setAttribute("opacity", "0.25");
    svgMap.appendChild(halo);

    // Inner node badge circle
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", n.x);
    circle.setAttribute("cy", n.y);
    circle.setAttribute("r", 14);
    circle.setAttribute("fill", "#0f172a");
    circle.setAttribute("stroke", n.color);
    circle.setAttribute("stroke-width", "3");
    svgMap.appendChild(circle);

    // Letter Label A, B, C, D
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", n.x);
    label.setAttribute("y", n.y + 4);
    label.setAttribute("fill", "#f8fafc");
    label.setAttribute("font-size", "12");
    label.setAttribute("font-weight", "bold");
    label.setAttribute("font-family", "Inter, sans-serif");
    label.setAttribute("text-anchor", "middle");
    label.textContent = n.id;
    svgMap.appendChild(label);

    // Subtitle caption (e.g. Origin / Dest)
    const caption = document.createElementNS("http://www.w3.org/2000/svg", "text");
    let capY = n.y < 250 ? n.y - 20 : n.y + 28;
    caption.setAttribute("x", n.x);
    caption.setAttribute("y", capY);
    caption.setAttribute("fill", n.color);
    caption.setAttribute("font-size", "10");
    caption.setAttribute("font-weight", "700");
    caption.setAttribute("font-family", "Inter, sans-serif");
    caption.setAttribute("text-anchor", "middle");
    caption.textContent = n.name;
    svgMap.appendChild(caption);
  });
}

// Update Route View
function updateRouteInfo(data) {
  const corridorTag = document.getElementById("route-corridor");
  const avoidedView = document.getElementById("avoided-roads-view");

  const r2 = data.roads?.find(r => r.road_id === "R002");
  if (r2 && r2.risk === "UNSAFE") {
    corridorTag.innerText = "A → C → D via West Bypass (R003) & South Blvd (R004)";
    corridorTag.className = "route-tag safe";
    avoidedView.innerHTML = `<span class="label">Avoided Road Segments:</span>
      <span class="avoided-item">⛔ East Expwy (R002: B→D flooded ${r2.mean_depth_cm.toFixed(1)}cm)</span>`;
  } else {
    corridorTag.innerText = "A → B → D via North Ave (R001) & East Expwy (R002)";
    corridorTag.className = "route-tag safe";
    avoidedView.innerHTML = `<span class="label">Avoided Road Segments:</span>
      <span class="avoided-item none">None (All direct streets safe)</span>`;
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

// Initial load
loadSnapshot(0);
