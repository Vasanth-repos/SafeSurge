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

  // B. Render Road Network Overlay
  const roadCoords = {
    "R001": { x1: 34, y1: 34, x2: 466, y2: 34 },
    "R002": { x1: 466, y1: 34, x2: 466, y2: 466 },
    "R003": { x1: 34, y1: 34, x2: 34, y2: 466 },
    "R004": { x1: 34, y1: 466, x2: 466, y2: 466 },
  };

  if (data.roads) {
    data.roads.forEach(road => {
      const pts = roadCoords[road.road_id];
      if (!pts) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", pts.x1);
      line.setAttribute("y1", pts.y1);
      line.setAttribute("x2", pts.x2);
      line.setAttribute("y2", pts.y2);

      let strokeColor = "#22c55e"; // SAFE
      let strokeDash = "none";
      if (road.risk === "UNSAFE") {
        strokeColor = "#ef4444";
        strokeDash = "6,4";
      } else if (road.risk === "HIGH") {
        strokeColor = "#f97316";
      } else if (road.risk === "WATCH") {
        strokeColor = "#eab308";
      }

      line.setAttribute("stroke", strokeColor);
      line.setAttribute("stroke-width", "5");
      line.setAttribute("stroke-dasharray", strokeDash);
      line.setAttribute("stroke-linecap", "round");
      svgMap.appendChild(line);
    });
  }

  // C. Render Node Markers: A, B, C, D
  const nodes = [
    { id: "A", name: "Origin A", x: 34, y: 34, color: "#38bdf8", isEndpoint: true },
    { id: "B", name: "Node B", x: 466, y: 34, color: "#f59e0b", isEndpoint: false },
    { id: "C", name: "Node C", x: 34, y: 466, color: "#f59e0b", isEndpoint: false },
    { id: "D", name: "Dest D", x: 466, y: 466, color: "#22c55e", isEndpoint: true },
  ];

  // Road labels
  const roadLabels = [
    { id: "R001", x: 250, y: 22 },
    { id: "R002", x: 472, y: 250 },
    { id: "R003", x: 24, y: 250 },
    { id: "R004", x: 250, y: 480 },
  ];

  roadLabels.forEach(rl => {
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", rl.x);
    txt.setAttribute("y", rl.y);
    txt.setAttribute("fill", "#94a3b8");
    txt.setAttribute("font-size", "10");
    txt.setAttribute("font-weight", "600");
    txt.setAttribute("font-family", "JetBrains Mono, monospace");
    txt.setAttribute("text-anchor", "middle");
    txt.textContent = rl.id;
    svgMap.appendChild(txt);
  });

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
    let capY = n.y < 250 ? n.y - 18 : n.y + 26;
    caption.setAttribute("x", n.x);
    caption.setAttribute("y", capY);
    caption.setAttribute("fill", n.color);
    caption.setAttribute("font-size", "9");
    caption.setAttribute("font-weight", "600");
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
    corridorTag.innerText = "A → C → D (Safe Alternate)";
    corridorTag.className = "route-tag safe";
    avoidedView.innerHTML = `<span class="label">Avoided Road Segments:</span>
      <span class="avoided-item">⛔ R002 (B→D flooded: ${r2.mean_depth_cm.toFixed(1)}cm)</span>`;
  } else {
    corridorTag.innerText = "A → B → D (Optimal Direct)";
    corridorTag.className = "route-tag safe";
    avoidedView.innerHTML = `<span class="label">Avoided Road Segments:</span>
      <span class="avoided-item none">None (All corridors safe)</span>`;
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
