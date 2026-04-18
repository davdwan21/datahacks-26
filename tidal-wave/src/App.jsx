import { useState, useRef, useEffect } from "react";
import "./App.css";

// ── Mock data (replace with real JSON from teammates) ──────────────────────
const MOCK_HEALTH = {
  year: 2023,
  overall_index: 63,
  sub_indices: {
    chemistry: 65,
    plankton: 61,
    fish_larvae: 58,
    biodiversity: 63,
  },
  anomaly: false,
  anomaly_label: null,
};

const MOCK_STATIONS = [
  {
    id: "A1",
    lat: 33.4,
    lng: -118.2,
    name: "Line 80",
    chemistry: 71,
    plankton: 68,
  },
  {
    id: "A2",
    lat: 34.1,
    lng: -120.5,
    name: "Line 70",
    chemistry: 63,
    plankton: 55,
  },
  {
    id: "A3",
    lat: 35.2,
    lng: -121.8,
    name: "Line 60",
    chemistry: 58,
    plankton: 61,
  },
  {
    id: "A4",
    lat: 36.6,
    lng: -122.4,
    name: "Line 57",
    chemistry: 72,
    plankton: 70,
  },
  {
    id: "A5",
    lat: 37.8,
    lng: -123.1,
    name: "Farallon",
    chemistry: 66,
    plankton: 64,
  },
  {
    id: "A6",
    lat: 34.8,
    lng: -119.9,
    name: "Line 67",
    chemistry: 60,
    plankton: 52,
  },
];

const BOUNDS = { latMin: 30, latMax: 39, lngMin: -126, lngMax: -116 };

// ── Helpers ────────────────────────────────────────────────────────────────
function latToY(lat, h) {
  return h - ((lat - BOUNDS.latMin) / (BOUNDS.latMax - BOUNDS.latMin)) * h;
}

function lngToX(lng, w) {
  return ((lng - BOUNDS.lngMin) / (BOUNDS.lngMax - BOUNDS.lngMin)) * w;
}

function scoreColor(score) {
  if (score >= 70) return "#34d399";
  if (score >= 55) return "#fbbf24";
  return "#f87171";
}

// ── Sub-index bar ──────────────────────────────────────────────────────────
function SubBar({ label, value, color }) {
  return (
    <div className="sub-bar">
      <div className="sub-bar__header">
        <span className="sub-bar__label">{label}</span>
        <span className="sub-bar__value">{value}</span>
      </div>
      <div className="sub-bar__track">
        <div
          className="sub-bar__fill"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ── Map panel ──────────────────────────────────────────────────────────────
function MapPanel({ onSelectStation, selectedStation }) {
  const svgRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef(null);
  const W = 680,
    H = 360;

  const handleWheel = (e) => {
    e.preventDefault();
    setZoom((z) => Math.min(4, Math.max(1, z - e.deltaY * 0.001)));
  };

  const handleMouseDown = (e) => {
    setDragging(true);
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e) => {
    if (!dragging || !dragStart.current) return;
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handleMouseUp = () => {
    setDragging(false);
    dragStart.current = null;
  };

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  const latLines = [31, 33, 35, 37, 39];
  const lngLines = [-125, -123, -121, -119, -117];

  return (
    <div className="map-panel">
      <svg
        ref={svgRef}
        className="map-panel__svg"
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        style={{ cursor: dragging ? "grabbing" : "grab" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <radialGradient id="oceanGrad" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#1a3a5c" />
            <stop offset="100%" stopColor="#0a1628" />
          </radialGradient>
        </defs>

        <g
          transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}
          style={{ transformOrigin: `${W / 2}px ${H / 2}px` }}
        >
          <rect width={W} height={H} fill="url(#oceanGrad)" />

          {/* Grid lines */}
          {latLines.map((lat) => (
            <line
              key={lat}
              x1={0}
              x2={W}
              y1={latToY(lat, H)}
              y2={latToY(lat, H)}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth={0.5}
              strokeDasharray="4 4"
            />
          ))}
          {lngLines.map((lng) => (
            <line
              key={lng}
              x1={lngToX(lng, W)}
              x2={lngToX(lng, W)}
              y1={0}
              y2={H}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth={0.5}
              strokeDasharray="4 4"
            />
          ))}

          {/* Grid labels */}
          {latLines.map((lat) => (
            <text
              key={lat}
              x={6}
              y={latToY(lat, H) - 3}
              fill="rgba(148,163,184,0.4)"
              fontSize={9}
              fontFamily="monospace"
            >
              {lat}°N
            </text>
          ))}
          {lngLines.map((lng) => (
            <text
              key={lng}
              x={lngToX(lng, W) + 3}
              y={H - 5}
              fill="rgba(148,163,184,0.4)"
              fontSize={9}
              fontFamily="monospace"
            >
              {Math.abs(lng)}°W
            </text>
          ))}

          {/* CalCOFI bounding box */}
          <rect
            x={lngToX(-124.5, W)}
            y={latToY(38, H)}
            width={lngToX(-117, W) - lngToX(-124.5, W)}
            height={latToY(30.5, H) - latToY(38, H)}
            fill="rgba(56,189,248,0.04)"
            stroke="rgba(56,189,248,0.25)"
            strokeWidth={1}
            strokeDasharray="6 3"
          />
          <text
            x={lngToX(-124.5, W) + 6}
            y={latToY(38, H) + 14}
            fill="rgba(56,189,248,0.5)"
            fontSize={10}
            fontFamily="monospace"
            fontWeight="500"
          >
            CalCOFI region
          </text>

          {/* Station dots */}
          {MOCK_STATIONS.map((s) => {
            const x = lngToX(s.lng, W);
            const y = latToY(s.lat, H);
            const isSelected = selectedStation?.id === s.id;
            const c = scoreColor((s.chemistry + s.plankton) / 2);
            return (
              <g
                key={s.id}
                onClick={() => onSelectStation(s)}
                style={{ cursor: "pointer" }}
              >
                {isSelected && (
                  <circle cx={x} cy={y} r={16} fill={c} opacity={0.15} />
                )}
                <circle
                  cx={x}
                  cy={y}
                  r={isSelected ? 8 : 6}
                  fill={c}
                  opacity={0.9}
                />
                <circle
                  cx={x}
                  cy={y}
                  r={isSelected ? 8 : 6}
                  fill="none"
                  stroke={c}
                  strokeWidth={1.5}
                  opacity={0.5}
                />
                <text
                  x={x + 11}
                  y={y + 4}
                  fill="rgba(226,232,240,0.8)"
                  fontSize={10}
                  fontFamily="monospace"
                >
                  {s.name}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      <div className="map-panel__hint">scroll to zoom · drag to pan</div>

      <div className="map-panel__zoom-controls">
        {["+", "−"].map((lbl, i) => (
          <button
            key={lbl}
            className="map-panel__zoom-btn"
            onClick={() =>
              setZoom((z) =>
                Math.min(4, Math.max(1, z + (i === 0 ? 0.4 : -0.4)))
              )
            }
          >
            {lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Info panel ─────────────────────────────────────────────────────────────
function InfoPanel({ selectedStation }) {
  const d = MOCK_HEALTH;
  const score = d.overall_index;
  const scoreCol = scoreColor(score);

  return (
    <div className="info-panel">
      <div className="info-panel__header">
        <span className="label-xs">Ocean health index</span>
        <span className="label-year">· {d.year}</span>
      </div>

      <div className="info-panel__score-row">
        <span className="info-panel__score" style={{ color: scoreCol }}>
          {score}
        </span>
        <span className="info-panel__score-denom">/100</span>
      </div>

      <div className="info-panel__track">
        <div
          className="info-panel__fill"
          style={{ width: `${score}%`, background: scoreCol }}
        />
      </div>

      <div className="info-panel__divider">
        <SubBar
          label="Chemistry"
          value={d.sub_indices.chemistry}
          color="#34d399"
        />
        <SubBar
          label="Plankton"
          value={d.sub_indices.plankton}
          color="#38bdf8"
        />
        <SubBar
          label="Fish larvae"
          value={d.sub_indices.fish_larvae}
          color="#a78bfa"
        />
        <SubBar
          label="Biodiversity"
          value={d.sub_indices.biodiversity}
          color="#fb923c"
        />
      </div>

      {selectedStation ? (
        <div className="info-panel__divider">
          <div className="label-xs" style={{ marginBottom: 8 }}>
            Station · {selectedStation.name}
          </div>
          <div className="info-panel__station-grid">
            {[
              { label: "Chemistry", val: selectedStation.chemistry },
              { label: "Plankton", val: selectedStation.plankton },
              { label: "Lat", val: `${selectedStation.lat}°N` },
              { label: "Lng", val: `${Math.abs(selectedStation.lng)}°W` },
            ].map(({ label, val }) => (
              <div key={label} className="info-panel__station-card">
                <div className="info-panel__station-label">{label}</div>
                <div className="info-panel__station-value">{val}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="info-panel__hint">
          Click a station on the map to inspect it
        </p>
      )}
    </div>
  );
}

// ── Policy box ─────────────────────────────────────────────────────────────
const QUICK_PROMPTS = [
  "Expand marine protected areas in the southern California Bight...",
  "Mandate quarterly plankton monitoring at high-stress stations...",
  "Implement seasonal fishing restrictions when health index drops below 50...",
];

function PolicyBox() {
  const [text, setText] = useState("");

  return (
    <div className="policy-box">
      <div className="policy-box__header">
        <span className="label-xs">Policy sandbox</span>
        <span className="policy-box__char-count">{text.length} chars</span>
      </div>

      <textarea
        className="policy-box__textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a policy idea based on the data above..."
      />

      <span className="policy-box__prompts-label">QUICK PROMPTS</span>
      <div className="policy-box__prompts">
        {QUICK_PROMPTS.map((idea, i) => (
          <button
            key={i}
            className="policy-box__prompt-btn"
            onClick={() => setText(idea)}
          >
            {idea.slice(0, 52)}…
          </button>
        ))}
      </div>
    </div>
  );
}

// ── App root ───────────────────────────────────────────────────────────────
export default function App() {
  const [selectedStation, setSelectedStation] = useState(null);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__dot" />
        <span className="topbar__title">TIDAL WAVE</span>
        <span className="topbar__meta">
          Catchphrase -- <br />
          CalCOFI + iNaturalist · mock data
        </span>
      </header>

      <main className="main-layout">
        <section className="left-panel">
          <MapPanel
            onSelectStation={setSelectedStation}
            selectedStation={selectedStation}
          />
        </section>

        <section className="right-panel">
          <div className="right-top">
            <InfoPanel selectedStation={selectedStation} />
          </div>

          <div className="right-bottom">
            <PolicyBox />
          </div>
        </section>
      </main>
    </div>
  );
}
