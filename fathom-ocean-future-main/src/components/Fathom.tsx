import { useEffect, useMemo, useRef, useState } from "react";
import { SpiralAnimation } from "@/components/ui/spiral-animation";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

// ---------------- Types & data ----------------
type Trend = "improving" | "stable" | "declining";
type SpeciesKey =
  | "phytoplankton"
  | "zooplankton"
  | "anchovy"
  | "sardine"
  | "sea_lion"
  | "kelp"
  | "urchin";

interface AgentState {
  population: number;
  last_action: string;
  health_trend: Trend;
}

interface EnvState {
  temperature: number;
  nutrients: number;
  pH: number;
  salinity: number;
  fishing_pressure: number;
  pollution_index: number;
}

interface SimTick {
  timestamp_utc: string;
  ticks: number;
  policy: string;
  environment: EnvState;
  agents: Record<SpeciesKey, AgentState>;
}

const SPECIES_META: Record<
  SpeciesKey,
  { name: string; color: string; size: number }
> = {
  phytoplankton: { name: "Phytoplankton", color: "#00ff9d", size: 4 },
  zooplankton:   { name: "Zooplankton",   color: "#00cfff", size: 4 },
  anchovy:       { name: "Anchovy",       color: "#3b82f6", size: 5 },
  sardine:       { name: "Sardine",       color: "#60a5fa", size: 5 },
  sea_lion:      { name: "Sea Lion",      color: "#ffb347", size: 6 },
  kelp:          { name: "Kelp",          color: "#22c55e", size: 5 },
  urchin:        { name: "Urchin",        color: "#ff4757", size: 5 },
};

const SPECIES_ORDER: SpeciesKey[] = [
  "phytoplankton",
  "zooplankton",
  "anchovy",
  "sardine",
  "sea_lion",
  "kelp",
  "urchin",
];

// Sample baseline tick (the user-provided sample, used as tick #5)
const SAMPLE_TICK: SimTick = {
  timestamp_utc: new Date().toISOString(),
  ticks: 5,
  policy: "ban commercial fishing",
  environment: {
    temperature: 16.35,
    nutrients: 0.57,
    pH: 8.05,
    salinity: 33.4,
    fishing_pressure: 0.05,
    pollution_index: 0.29,
  },
  agents: {
    phytoplankton: { population: 95, last_action: "persist", health_trend: "stable" },
    zooplankton:   { population: 70, last_action: "swarm", health_trend: "improving" },
    anchovy:       { population: 95, last_action: "feed_aggressively", health_trend: "improving" },
    sardine:       { population: 100, last_action: "feed_aggressively", health_trend: "improving" },
    sea_lion:      { population: 100, last_action: "thrive", health_trend: "improving" },
    kelp:          { population: 31, last_action: "recover", health_trend: "improving" },
    urchin:        { population: 66, last_action: "starve", health_trend: "declining" },
  },
};

// Pre-policy baseline (year 0): high fishing, depleted populations
const BASELINE_TICK: SimTick = {
  timestamp_utc: new Date().toISOString(),
  ticks: 0,
  policy: "none",
  environment: {
    temperature: 16.8, nutrients: 0.42, pH: 8.02, salinity: 33.5,
    fishing_pressure: 0.5, pollution_index: 0.34,
  },
  agents: {
    phytoplankton: { population: 60, last_action: "persist", health_trend: "stable" },
    zooplankton:   { population: 35, last_action: "drift", health_trend: "declining" },
    anchovy:       { population: 25, last_action: "flee", health_trend: "declining" },
    sardine:       { population: 30, last_action: "flee", health_trend: "declining" },
    sea_lion:      { population: 45, last_action: "hunt", health_trend: "stable" },
    kelp:          { population: 18, last_action: "decline", health_trend: "declining" },
    urchin:        { population: 78, last_action: "graze", health_trend: "improving" },
  },
};

// Build a sequence of ticks (year 0 -> year 5) interpolated toward sample
function buildTimeline(target: SimTick, baseline: SimTick): SimTick[] {
  const total = target.ticks;
  const out: SimTick[] = [baseline];
  for (let i = 1; i <= total; i++) {
    const t = i / total;
    const env: EnvState = {
      temperature: baseline.environment.temperature + (target.environment.temperature - baseline.environment.temperature) * t,
      nutrients: baseline.environment.nutrients + (target.environment.nutrients - baseline.environment.nutrients) * t,
      pH: baseline.environment.pH + (target.environment.pH - baseline.environment.pH) * t,
      salinity: baseline.environment.salinity + (target.environment.salinity - baseline.environment.salinity) * t,
      fishing_pressure: baseline.environment.fishing_pressure + (target.environment.fishing_pressure - baseline.environment.fishing_pressure) * t,
      pollution_index: baseline.environment.pollution_index + (target.environment.pollution_index - baseline.environment.pollution_index) * t,
    };
    const agents = {} as Record<SpeciesKey, AgentState>;
    for (const k of SPECIES_ORDER) {
      const b = baseline.agents[k].population;
      const a = target.agents[k].population;
      const pop = Math.round(b + (a - b) * t + (Math.random() - 0.5) * 6);
      const clamped = Math.max(0, Math.min(100, pop));
      const trend: Trend =
        i === total ? target.agents[k].health_trend :
        clamped > b + 3 ? "improving" : clamped < b - 3 ? "declining" : "stable";
      agents[k] = {
        population: clamped,
        last_action: i === total ? target.agents[k].last_action : target.agents[k].last_action,
        health_trend: trend,
      };
    }
    out.push({
      timestamp_utc: new Date().toISOString(),
      ticks: i,
      policy: target.policy,
      environment: env,
      agents,
    });
  }
  return out;
}

// Counterfactual: ecosystem WITHOUT policy (extrapolate baseline trends)
function buildCounterfactual(baseline: SimTick, years: number): SimTick[] {
  const out: SimTick[] = [baseline];
  // Worsening trajectory
  const target: Record<SpeciesKey, number> = {
    phytoplankton: 50, zooplankton: 22, anchovy: 12, sardine: 14,
    sea_lion: 30, kelp: 5, urchin: 95,
  };
  for (let i = 1; i <= years; i++) {
    const t = i / years;
    const agents = {} as Record<SpeciesKey, AgentState>;
    for (const k of SPECIES_ORDER) {
      const b = baseline.agents[k].population;
      const a = target[k];
      const pop = Math.max(0, Math.min(100, Math.round(b + (a - b) * t)));
      agents[k] = { population: pop, last_action: "no_policy", health_trend: pop < b ? "declining" : "stable" };
    }
    out.push({
      timestamp_utc: new Date().toISOString(),
      ticks: i,
      policy: "no policy",
      environment: { ...baseline.environment },
      agents,
    });
  }
  return out;
}

// ---------------- Map dot generation ----------------
// Static map: dots are positioned in SVG viewBox coordinates (0..1000, 0..1000).
// The viewBox shows California's offshore Pacific waters.
interface Dot { x: number; y: number; key: string }

function seededRand(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

// California coastline approximated as a polyline in viewBox coords (0..1000).
// y=0 is north (Crescent City), y=1000 is south (San Diego).
// x=0 is west (open Pacific), x=1000 is east (inland).
// The coast roughly hugs the right side of the viewBox.
const COAST_X_AT_Y: Array<[number, number]> = [
  [0,    760],
  [80,   765],
  [180,  740],
  [280,  720],
  [380,  730],
  [480,  745],
  [560,  775],
  [620,  820],
  [680,  870],
  [740,  900],
  [800,  860],
  [860,  830],
  [920,  830],
  [1000, 850],
];

function coastXAt(y: number): number {
  if (y <= COAST_X_AT_Y[0][0]) return COAST_X_AT_Y[0][1];
  const last = COAST_X_AT_Y[COAST_X_AT_Y.length - 1];
  if (y >= last[0]) return last[1];
  for (let i = 0; i < COAST_X_AT_Y.length - 1; i++) {
    const [y1, x1] = COAST_X_AT_Y[i];
    const [y2, x2] = COAST_X_AT_Y[i + 1];
    if (y >= y1 && y <= y2) {
      const t = (y - y1) / (y2 - y1);
      return x1 + (x2 - x1) * t;
    }
  }
  return 800;
}

function generateDots(species: SpeciesKey, count: number, seed: number): Dot[] {
  const rand = seededRand(seed);
  const dots: Dot[] = [];
  for (let i = 0; i < count; i++) {
    // Spread along the entire California coast top-to-bottom
    const y = 40 + rand() * 920;
    const coast = coastXAt(y);
    // Offshore: anywhere from just off the coast to deep open Pacific
    const offshore = 60 + rand() * (coast - 120);
    const x = coast - offshore;
    dots.push({ x, y, key: `${species}-${i}` });
  }
  return dots;
}

// ---------------- Helpers ----------------
const trendColor = (t: Trend) => t === "improving" ? "var(--healthy)" : t === "stable" ? "var(--warning)" : "var(--danger)";
const trendHex = (t: Trend) => t === "improving" ? "#00ff9d" : t === "stable" ? "#ffb347" : "#ff4757";

function generateNarrative(tick: SimTick): string {
  const { agents, ticks } = tick;
  if (agents.urchin.population > 70 && agents.kelp.population < 35) {
    return `In year ${ticks}, the seafloor tells a quiet tragedy — urchins blanket the rocks where forests once swayed, and the cold currents carry no memory of the kelp.`;
  }
  if (agents.anchovy.population > 80 && agents.sea_lion.population > 80) {
    return `By year ${ticks}, silver clouds of anchovy gather thick beneath the surface, and the sea lions, fat and easy, bark from every haul-out along the coast.`;
  }
  if (agents.kelp.health_trend === "improving") {
    return `In year ${ticks}, young kelp lifts toward the light again, and the cold green water hums with the patient promise of return.`;
  }
  return `Year ${ticks} drifts on the long tide — the ecosystem turns, slow and uncertain, neither broken nor whole.`;
}

function isUrchinBarren(tick: SimTick) {
  return tick.agents.urchin.population > 70 && tick.agents.kelp.population < 35;
}

function isAnchovyCollapse(tick: SimTick) {
  return tick.agents.anchovy.population < 20;
}

// ---------------- Components ----------------

// Static California coastline as an SVG path (in 0..1000 viewBox space).
// Built from the COAST_X_AT_Y polyline + closed inland to fill the land mass.
const CALIFORNIA_LAND_PATH = (() => {
  const top = COAST_X_AT_Y.map(([y, x]) => `${x},${y}`);
  // Close the polygon by going to the right edge and back to the top
  return `M ${top.join(" L ")} L 1000,1000 L 1000,0 Z`;
})();

const CALIFORNIA_COAST_PATH = `M ${COAST_X_AT_Y.map(([y, x]) => `${x},${y}`).join(" L ")}`;

function SpeciesDots({ species, count, total, onClick }: {
  species: SpeciesKey;
  count: number;
  total: number;
  onClick: () => void;
}) {
  // Generate the maximum set once (stable), then hide some based on count.
  // When population drops, the higher-indexed dots fade out → fewer dots on map.
  const allDots = useMemo(
    () => generateDots(species, total, species.length * 7919 + total),
    [species, total]
  );
  const meta = SPECIES_META[species];
  return (
    <g>
      {allDots.map((d, i) => {
        const visible = i < count;
        return (
          <circle
            key={d.key}
            cx={d.x}
            cy={d.y}
            r={meta.size}
            fill={meta.color}
            opacity={visible ? 0.9 : 0}
            onClick={onClick}
            style={{
              cursor: "pointer",
              pointerEvents: visible ? "auto" : "none",
              transition: "opacity 800ms ease, r 800ms ease",
            }}
          />
        );
      })}
    </g>
  );
}

function CoastMap({
  tick,
  onSpeciesClick,
  showBarrenFlash,
}: {
  tick: SimTick;
  onSpeciesClick: (s: SpeciesKey) => void;
  showBarrenFlash: boolean;
}) {
  return (
    <div className="relative w-full h-full overflow-hidden" style={{ background: "#050d1a" }}>
      <svg
        viewBox="0 0 1000 1000"
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0 w-full h-full"
      >
        {/* Ocean background */}
        <defs>
          <radialGradient id="ocean-grad" cx="30%" cy="40%" r="80%">
            <stop offset="0%" stopColor="#0a1f3d" />
            <stop offset="100%" stopColor="#050d1a" />
          </radialGradient>
          <linearGradient id="land-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#0f2040" />
            <stop offset="100%" stopColor="#0a1628" />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width="1000" height="1000" fill="url(#ocean-grad)" />

        {/* California landmass */}
        <path d={CALIFORNIA_LAND_PATH} fill="url(#land-grad)" stroke="#1a3050" strokeWidth="2" />

        {/* Coastline highlight */}
        <path d={CALIFORNIA_COAST_PATH} fill="none" stroke="#00cfff" strokeWidth="1.5" opacity="0.4" />

        {/* "CALIFORNIA" label on land */}
        <text
          x="900"
          y="500"
          fill="#6b8fa8"
          fontSize="22"
          fontFamily="IBM Plex Mono, monospace"
          fontWeight="700"
          letterSpacing="6"
          textAnchor="middle"
          transform="rotate(90 900 500)"
          opacity="0.6"
        >
          CALIFORNIA
        </text>

        {/* "PACIFIC OCEAN" label */}
        <text
          x="200"
          y="500"
          fill="#6b8fa8"
          fontSize="16"
          fontFamily="IBM Plex Mono, monospace"
          letterSpacing="4"
          opacity="0.5"
        >
          PACIFIC OCEAN
        </text>

        {/* Species dots */}
        {SPECIES_ORDER.map((sp) => {
          const pop = tick.agents[sp].population;
          const maxDots = sp === "phytoplankton" ? 50 : sp === "zooplankton" ? 40 : sp === "kelp" ? 30 : sp === "urchin" ? 30 : sp === "sea_lion" ? 18 : 32;
          const visible = Math.round((pop / 100) * maxDots);
          return (
            <SpeciesDots
              key={sp}
              species={sp}
              count={visible}
              total={maxDots}
              onClick={() => onSpeciesClick(sp)}
            />
          );
        })}
      </svg>

      {/* Barren flash overlay */}
      {showBarrenFlash && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "radial-gradient(circle at 70% 60%, rgba(255,71,87,0.35), transparent 60%)",
            animation: "flash-danger 1.2s ease-in-out infinite",
          }}
        />
      )}
    </div>
  );
}

function HealthBar({ value, trend, compareValue }: { value: number; trend: Trend; compareValue?: number }) {
  const color = trendHex(trend);
  return (
    <div className="w-full">
      <div className="h-2 rounded-full bg-[#0f2040] overflow-hidden relative">
        <div
          className="h-full rounded-full"
          style={{
            width: `${value}%`,
            background: color,
            transition: "width 800ms ease, background 400ms ease",
          }}
        />
        {compareValue !== undefined && (
          <div
            className="absolute top-0 h-full border-r-2 border-dashed"
            style={{
              left: `${compareValue}%`,
              borderColor: "#6b8fa8",
              opacity: 0.8,
            }}
            title={`Without policy: ${compareValue}`}
          />
        )}
      </div>
    </div>
  );
}

function EnvReadout({ label, value, unit, color = "#00cfff" }: { label: string; value: string; unit?: string; color?: string }) {
  return (
    <div className="rounded-md bg-[#050d1a] border border-[#0f2040] p-2.5">
      <div className="text-[10px] tracking-widest text-[#6b8fa8] font-bold" style={{ fontFamily: "var(--font-mono)" }}>{label}</div>
      <div className="flex items-baseline gap-1 mt-1">
        <span className="text-2xl font-bold leading-none" style={{ fontFamily: "var(--font-mono)", color }}>{value}</span>
        {unit && <span className="text-[10px] text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>{unit}</span>}
      </div>
    </div>
  );
}

// Shared species legend used on landing + simulation screens
function SpeciesLegend({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex flex-wrap gap-x-4 gap-y-2 ${compact ? "text-[10px]" : "text-xs"}`} style={{ fontFamily: "var(--font-mono)" }}>
      {SPECIES_ORDER.map((sp) => {
        const meta = SPECIES_META[sp];
        return (
          <div key={sp} className="flex items-center gap-1.5">
            <span
              className="inline-block rounded-full"
              style={{
                width: compact ? 8 : 10,
                height: compact ? 8 : 10,
                background: meta.color,
              }}
            />
            <span className="text-[#e8f4f8] font-medium uppercase tracking-wide">{meta.name}</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------- Landing screen ----------------
function Landing({ onSimulate }: { onSimulate: (policy: string) => void }) {
  const [policy, setPolicy] = useState("");
  const [visible, setVisible] = useState(false);
  const examples = ["Ban trawling", "Create marine protected area", "Reduce pollution"];

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 1800);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="fixed inset-0 w-full h-full overflow-hidden bg-black">
      {/* Spiral background */}
      <div className="absolute inset-0">
        <SpiralAnimation />
      </div>

      {/* Centered content */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center z-10 transition-all duration-1000 ease-out"
        style={{ opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(12px)" }}
      >
        <h1
          className="text-5xl md:text-7xl tracking-widest text-white font-extralight mb-3 uppercase"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "0.18em" }}
        >
          Tidal Wave
        </h1>
        <p
          className="text-xs tracking-[0.35em] text-white/40 uppercase mb-12"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          California Current Ecosystem Simulator
        </p>

        {/* Policy input */}
        <div className="w-full max-w-md px-6 flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && policy.trim()) onSimulate(policy.trim()); }}
              placeholder="Enter a policy to simulate..."
              className="flex-1 px-4 py-2.5 rounded-sm bg-white/10 border border-white/25 text-white placeholder:text-white/40 outline-none focus:border-white/50 text-sm transition-colors"
              style={{ fontFamily: "var(--font-mono)" }}
            />
            <button
              onClick={() => policy.trim() && onSimulate(policy.trim())}
              className="px-5 py-2.5 rounded-sm text-black text-xs font-bold tracking-widest uppercase hover:opacity-90 transition-opacity"
              style={{ background: "white", fontFamily: "var(--font-mono)" }}
            >
              Run
            </button>
          </div>

          {/* Example chips */}
          <div className="flex flex-wrap gap-2 justify-center">
            {examples.map((e) => (
              <button
                key={e}
                onClick={() => setPolicy(e)}
                className="px-3.5 py-1.5 rounded-sm border border-white/20 text-white/50 text-[11px] tracking-widest uppercase hover:border-white/40 hover:text-white/75 transition-all"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {e}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Loading screen ----------------
function LoadingScreen({ years }: { years: number }) {
  const phases = [
    "Reading the tides…",
    "Modeling phytoplankton blooms…",
    "Tracking sardine schools…",
    "Projecting kelp recovery…",
    "Synthesizing forecast…",
  ];
  const [phaseIdx, setPhaseIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setPhaseIdx((i) => (i + 1) % phases.length), 600);
    return () => clearInterval(id);
  }, [phases.length]);

  return (
    <div className="fixed inset-0 w-full h-full overflow-hidden bg-black">
      {/* Spiral background */}
      <div className="absolute inset-0">
        <SpiralAnimation />
      </div>

      {/* Centered text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center z-10 text-center px-6">
        <div
          className="text-3xl md:text-5xl mb-3 font-bold text-white"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "0.05em" }}
        >
          SIMULATING {years} YEARS
        </div>
        <div className="text-xs md:text-sm text-white/40 uppercase tracking-[0.3em] mb-4" style={{ fontFamily: "var(--font-mono)" }}>
          California Current
        </div>
        <div
          key={phaseIdx}
          className="text-base md:text-lg text-white/60 animate-fade-in"
          style={{ fontFamily: "var(--font-narrative)", fontStyle: "italic", minHeight: "1.5em" }}
        >
          {phases[phaseIdx]}
        </div>
      </div>
    </div>
  );
}

// ---------------- Param diff ----------------
const PARAM_LABELS: Record<string, string> = {
  fishing_pressure: "Fishing",
  pollution_index: "Pollution",
  nutrients: "Nutrients",
  temperature: "Temperature",
};
const PARAM_UNITS: Record<string, string> = { temperature: "°C" };
// For these params, ↓ is good (green); for nutrients/temp, neutral coloring
const GOOD_WHEN_DOWN = new Set(["fishing_pressure", "pollution_index"]);

function ParamDiff({ before, after, onDismiss }: { before: EnvState; after: EnvState; onDismiss?: () => void }) {
  const rows: { key: keyof EnvState }[] = [
    { key: "fishing_pressure" },
    { key: "pollution_index" },
    { key: "nutrients" },
    { key: "temperature" },
  ];
  return (
    <div className="rounded-lg bg-[#0a1628]/95 backdrop-blur border border-[#0f2040] shadow-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#0f2040] bg-gradient-to-r from-[#0a1628] to-[#0f2040]">
        <div className="text-[10px] tracking-[0.2em] font-bold text-[#00cfff]" style={{ fontFamily: "var(--font-mono)" }}>
          POLICY APPLIED
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-[#6b8fa8] hover:text-[#ff4757] transition text-sm leading-none"
            aria-label="Dismiss"
          >
            ✕
          </button>
        )}
      </div>
      <div className="p-3 space-y-2">
        {rows.map((r) => {
          const b = before[r.key];
          const a = after[r.key];
          const delta = a - b;
          const eps = 0.005;
          const dir = delta > eps ? "up" : delta < -eps ? "down" : "flat";
          const goodDown = GOOD_WHEN_DOWN.has(r.key as string);
          const color =
            dir === "flat" ? "#6b8fa8"
            : (dir === "down" && goodDown) || (dir === "up" && !goodDown && r.key !== "temperature") ? "#00ff9d"
            : r.key === "temperature" ? "#00cfff"
            : "#ff4757";
          const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "—";
          const unit = PARAM_UNITS[r.key as string] ?? "";
          const decimals = r.key === "temperature" ? 2 : 2;
          return (
            <div
              key={r.key}
              className="flex items-center justify-between gap-3 px-2 py-1.5 rounded bg-[#050d1a]/60"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              <span className="text-[11px] text-[#e8f4f8] font-medium">{PARAM_LABELS[r.key as string]}</span>
              <div className="flex items-center gap-2 text-[11px] tabular-nums">
                <span className="text-[#6b8fa8]">{b.toFixed(decimals)}{unit}</span>
                <span className="text-[#6b8fa8]">→</span>
                <span style={{ color }} className="font-bold">{a.toFixed(decimals)}{unit}</span>
                <span style={{ color }} className="text-[10px] w-3 text-center">{arrow}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------- Simulation screen ----------------
function Simulation({
  policy,
  timeline,
  counterfactual,
  onBack,
}: {
  policy: string;
  timeline: SimTick[];
  counterfactual: SimTick[];
  onBack: () => void;
}) {
  const [yearIdx, setYearIdx] = useState(0);
  const [autoplay, setAutoplay] = useState(true);
  const [selected, setSelected] = useState<SpeciesKey | null>(null);
  const [showDiff, setShowDiff] = useState(true);

  useEffect(() => {
    if (!autoplay) return;
    const id = setInterval(() => {
      setYearIdx((i) => {
        if (i >= timeline.length - 1) { setAutoplay(false); return i; }
        return i + 1;
      });
    }, 1200);
    return () => clearInterval(id);
  }, [autoplay, timeline.length]);

  // QoL: keyboard nav (← → arrows, space = play/pause, R = restart)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight") { setYearIdx((i) => Math.min(timeline.length - 1, i + 1)); setAutoplay(false); }
      else if (e.key === "ArrowLeft") { setYearIdx((i) => Math.max(0, i - 1)); setAutoplay(false); }
      else if (e.key === " ") { e.preventDefault(); setAutoplay((a) => !a); }
      else if (e.key === "r" || e.key === "R") { setYearIdx(0); setAutoplay(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [timeline.length]);

  const tick = timeline[yearIdx];
  const cfTick = counterfactual[yearIdx];
  const narrative = generateNarrative(tick);
  const barren = isUrchinBarren(tick);
  const collapse = isAnchovyCollapse(tick);

  // History data for chart — full X axis always visible, values null beyond current year
  const historyData = timeline.map((t, i) => {
    const row: Record<string, number | string | null> = { year: `Y${t.ticks}` };
    SPECIES_ORDER.forEach((s) => { row[s] = i <= yearIdx ? t.agents[s].population : null; });
    return row;
  });

  // Environment parameter history (normalized 0-100 for shared axis)
  const envHistoryData = timeline.map((t, i) => ({
    year: `Y${t.ticks}`,
    fishing: i <= yearIdx ? Math.round(t.environment.fishing_pressure * 100) : null,
    pollution: i <= yearIdx ? Math.round(t.environment.pollution_index * 100) : null,
    nutrients: i <= yearIdx ? Math.round(t.environment.nutrients * 100) : null,
  }));

  return (
    <div key="sim" className="min-h-screen w-full animate-fade-in-slow" style={{ background: "#050d1a", color: "#e8f4f8" }}>
      <div className="flex items-center justify-between px-6 py-3 border-b border-[#0f2040]">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="text-xs text-[#6b8fa8] hover:text-[#00cfff] transition"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            ← NEW SIMULATION
          </button>
          <h1 className="text-2xl tracking-tight" style={{ fontFamily: "var(--font-display)" }}>TIDAL WAVE</h1>
          <span className="text-xs text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>
            POLICY // <span className="text-[#00cfff]">{policy.toUpperCase()}</span>
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden md:inline text-[10px] text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>
            ← → SCRUB · SPACE PLAY · R RESTART
          </span>
          <button
            onClick={() => { setYearIdx(0); setAutoplay(true); setShowDiff(true); }}
            className="text-[10px] px-2 py-1 rounded border border-[#0f2040] text-[#6b8fa8] hover:border-[#00cfff] hover:text-[#00cfff] transition"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            ↻ RESTART
          </button>
          <div className="text-xs text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>
            YEAR <span className="text-[#00ff9d] font-bold">{tick.ticks}</span> / {timeline[timeline.length - 1].ticks}
          </div>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row" style={{ height: "calc(100vh - 49px)" }}>
        {/* LEFT: Map 60% */}
        <div className="lg:w-[60%] w-full h-[50vh] lg:h-full relative border-r border-[#0f2040]">
          <CoastMap
            tick={tick}
            onSpeciesClick={(s) => setSelected(s)}
            showBarrenFlash={barren}
          />
          {showDiff && (
            <div className="absolute bottom-4 left-4 w-72 max-w-[calc(100%-2rem)] animate-fade-in z-10">
              <ParamDiff
                before={BASELINE_TICK.environment}
                after={SAMPLE_TICK.environment}
                onDismiss={() => setShowDiff(false)}
              />
            </div>
          )}
          {!showDiff && (
            <button
              onClick={() => setShowDiff(true)}
              className="absolute bottom-4 left-4 z-10 text-[10px] px-3 py-1.5 rounded bg-[#0a1628]/90 backdrop-blur border border-[#0f2040] text-[#6b8fa8] hover:text-[#00cfff] hover:border-[#00cfff] transition"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              SHOW POLICY DIFF
            </button>
          )}
        </div>

        {/* RIGHT: 40% panel */}
        <div className="lg:w-[40%] w-full overflow-y-auto p-5 space-y-4">
          {/* 1. Narrative ship's log */}
          <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-5">
            <div className="text-[10px] tracking-[0.2em] font-bold text-[#6b8fa8] mb-3" style={{ fontFamily: "var(--font-mono)" }}>
              YEAR {tick.ticks} // POST [{policy.toUpperCase()}]
            </div>
            <p
              className="text-lg leading-relaxed text-[#e8f4f8]"
              style={{ fontFamily: "var(--font-narrative)", fontStyle: "italic", fontWeight: 600, letterSpacing: "0.01em" }}
            >
              {narrative}
            </p>
            {(barren || collapse) && (
              <div
                className="mt-4 p-3 rounded border-l-4 animate-fade-in"
                style={{ background: "rgba(255,71,87,0.12)", borderColor: "#ff4757" }}
              >
                <div className="text-[10px] tracking-widest font-bold mb-1" style={{ color: "#ff4757", fontFamily: "var(--font-mono)" }}>
                  THRESHOLD EVENT
                </div>
                <div className="text-xs text-[#e8f4f8]" style={{ fontFamily: "var(--font-mono)" }}>
                  {barren && "URCHIN BARREN: kelp forest collapse imminent. "}
                  {collapse && "ANCHOVY COLLAPSE: forage fish stock critical."}
                </div>
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-3">
            <div className="text-[10px] tracking-[0.2em] font-bold text-[#6b8fa8] mb-2" style={{ fontFamily: "var(--font-mono)" }}>
              MAP LEGEND
            </div>
            <SpeciesLegend compact />
          </div>

          {/* 2. Species snapshot — 3 cols, larger text */}
          <div className="grid grid-cols-3 gap-2">
            {SPECIES_ORDER.map((sp) => {
              const a = tick.agents[sp];
              const cf = cfTick?.agents[sp];
              const meta = SPECIES_META[sp];
              const isSelected = selected === sp;
              return (
                <button
                  key={sp}
                  onClick={() => setSelected(isSelected ? null : sp)}
                  className={`rounded-md p-3 text-left border transition-all ${isSelected ? "border-[#00cfff] bg-[#0f2040]" : "border-[#0f2040] bg-[#0a1628] hover:border-[#1a3050]"}`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block rounded-full"
                      style={{ width: 8, height: 8, background: meta.color }}
                    />
                  </div>
                  <div className="text-xs font-bold tracking-wide text-[#e8f4f8] mt-2 uppercase" style={{ fontFamily: "var(--font-mono)" }}>
                    {meta.name}
                  </div>
                  <div className="mt-2">
                    <HealthBar
                      value={a.population}
                      trend={a.health_trend}
                    />
                  </div>
                  <div className="text-2xl font-bold mt-1.5 leading-none" style={{ fontFamily: "var(--font-display)", color: trendHex(a.health_trend) }}>
                    {a.population}
                  </div>
                  <div className="text-[10px] text-[#6b8fa8] mt-1 truncate" style={{ fontFamily: "var(--font-mono)" }}>
                    {a.last_action}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Population history chart for selected */}
          {selected && (
            <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-4 animate-fade-in">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] tracking-widest font-bold text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>
                  {SPECIES_META[selected].name.toUpperCase()} // POPULATION HISTORY
                </div>
                <button onClick={() => setSelected(null)} className="text-[10px] text-[#6b8fa8] hover:text-[#00cfff]">✕</button>
              </div>
              <div style={{ width: "100%", height: 160 }}>
                <ResponsiveContainer>
                  <LineChart data={historyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid stroke="#0f2040" strokeDasharray="3 3" />
                    <XAxis dataKey="year" stroke="#6b8fa8" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                    <YAxis stroke="#6b8fa8" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ background: "#0a1628", border: "1px solid #0f2040", fontFamily: "IBM Plex Mono", fontSize: 11 }}
                      labelStyle={{ color: "#e8f4f8" }}
                    />
                    <Line
                      type="monotone"
                      dataKey={selected}
                      stroke={SPECIES_META[selected].color}
                      strokeWidth={2}
                      dot={{ fill: SPECIES_META[selected].color, r: 3 }}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* 3. Environmental conditions — all 6 numeric readouts */}
          <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-4">
            <div className="text-[10px] tracking-widest font-bold text-[#6b8fa8] mb-3" style={{ fontFamily: "var(--font-mono)" }}>
              ENVIRONMENT // CALIFORNIA CURRENT
            </div>
            <div className="grid grid-cols-3 gap-2">
              <EnvReadout label="TEMP" value={tick.environment.temperature.toFixed(2)} unit="°C" color="#00cfff" />
              <EnvReadout label="NUTRIENTS" value={tick.environment.nutrients.toFixed(2)} color="#00ff9d" />
              <EnvReadout label="pH" value={tick.environment.pH.toFixed(2)} color="#00cfff" />
              <EnvReadout label="SALINITY" value={tick.environment.salinity.toFixed(1)} unit="PSU" color="#00cfff" />
              <EnvReadout label="FISHING" value={tick.environment.fishing_pressure.toFixed(2)} color={tick.environment.fishing_pressure > 0.4 ? "#ff4757" : "#00ff9d"} />
              <EnvReadout label="POLLUTION" value={tick.environment.pollution_index.toFixed(2)} color={tick.environment.pollution_index > 0.4 ? "#ff4757" : "#ffb347"} />
            </div>
          </div>

          {/* 3b. Parameter changes over time chart (bottom-right) */}
          <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] tracking-widest font-bold text-[#6b8fa8]" style={{ fontFamily: "var(--font-mono)" }}>
                PARAMETER CHANGES // OVER TIME
              </div>
              <div className="flex gap-3 text-[9px]" style={{ fontFamily: "var(--font-mono)" }}>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: "#ff4757" }} /><span className="text-[#e8f4f8]">FISHING</span></span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: "#ffb347" }} /><span className="text-[#e8f4f8]">POLLUTION</span></span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: "#00ff9d" }} /><span className="text-[#e8f4f8]">NUTRIENTS</span></span>
              </div>
            </div>
            <div style={{ width: "100%", height: 150 }}>
              <ResponsiveContainer>
                <LineChart data={envHistoryData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#0f2040" strokeDasharray="3 3" />
                  <XAxis dataKey="year" stroke="#6b8fa8" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  <YAxis stroke="#6b8fa8" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ background: "#0a1628", border: "1px solid #0f2040", fontFamily: "IBM Plex Mono", fontSize: 11 }}
                    labelStyle={{ color: "#e8f4f8" }}
                  />
                  <Line type="monotone" dataKey="fishing" stroke="#ff4757" strokeWidth={2} dot={{ r: 2 }} connectNulls={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="pollution" stroke="#ffb347" strokeWidth={2} dot={{ r: 2 }} connectNulls={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="nutrients" stroke="#00ff9d" strokeWidth={2} dot={{ r: 2 }} connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 4. Year navigation */}
          <div className="rounded-lg bg-[#0a1628] border border-[#0f2040] p-4">
            <div className="flex items-center gap-3 mb-3">
              <button
                onClick={() => setYearIdx((i) => Math.max(0, i - 1))}
                disabled={yearIdx === 0}
                className="px-3 py-1.5 rounded border border-[#0f2040] text-xs hover:border-[#00cfff] disabled:opacity-30 shrink-0"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                ◀
              </button>
              <input
                type="range"
                min={0}
                max={timeline.length - 1}
                step={1}
                value={yearIdx}
                onChange={(e) => { setYearIdx(Number(e.target.value)); setAutoplay(false); }}
                className="flex-1 h-1 rounded-full appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, #00cfff ${(yearIdx / (timeline.length - 1)) * 100}%, #0f2040 ${(yearIdx / (timeline.length - 1)) * 100}%)`,
                  accentColor: "#00ff9d",
                }}
              />
              <button
                onClick={() => setYearIdx((i) => Math.min(timeline.length - 1, i + 1))}
                disabled={yearIdx === timeline.length - 1}
                className="px-3 py-1.5 rounded border border-[#0f2040] text-xs hover:border-[#00cfff] disabled:opacity-30 shrink-0"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                ▶
              </button>
              <button
                onClick={() => setAutoplay((a) => !a)}
                className="px-3 py-1.5 rounded text-xs font-bold shrink-0"
                style={{
                  background: autoplay ? "#ff4757" : "linear-gradient(135deg, #00ff9d, #00cfff)",
                  color: "#050d1a",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {autoplay ? "■ STOP" : "▶ PLAY"}
              </button>
            </div>
            <div className="text-center mt-2 text-[10px] text-[#6b8fa8] tracking-widest" style={{ fontFamily: "var(--font-mono)" }}>
              YEAR {tick.ticks} OF {timeline[timeline.length - 1].ticks}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Root component ----------------
type Screen = "landing" | "loading" | "sim";

export default function Fathom() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [policy, setPolicy] = useState("");
  const [timeline, setTimeline] = useState<SimTick[]>([]);
  const [counterfactual, setCounterfactual] = useState<SimTick[]>([]);

  const handleSimulate = (p: string) => {
    setPolicy(p);
    setScreen("loading");
    // Simulate fetch delay
    setTimeout(() => {
      const target = { ...SAMPLE_TICK, policy: p };
      const tl = buildTimeline(target, BASELINE_TICK);
      const cf = buildCounterfactual(BASELINE_TICK, target.ticks);
      setTimeline(tl);
      setCounterfactual(cf);
      setScreen("sim");
    }, 2200);
  };

  if (screen === "landing") return <Landing onSimulate={handleSimulate} />;
  if (screen === "loading") return <LoadingScreen years={SAMPLE_TICK.ticks} />;
  return (
    <Simulation
      policy={policy}
      timeline={timeline}
      counterfactual={counterfactual}
      onBack={() => setScreen("landing")}
    />
  );
}
