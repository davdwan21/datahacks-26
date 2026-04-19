import argparse
import ollama
import re
import time
import webbrowser
import os
import tempfile
import anchovy as anchovy_module
import sardine as sardine_module
import kelp as kelp_module
import urchin as urchin_module
import sealion as sealion_module
import database_fetch

# ── Environment state (CalCOFI California Current baseline) ──────────────────
environment = database_fetch.BASELINE_ENVIRONMENT.copy()

# ── Agent states ─────────────────────────────────────────────────────────────
phytoplankton = {
    "population": 65,
    "last_action": None,
    "health_trend": "stable"
}

zooplankton = {
    "population": 55,
    "last_action": None,
    "health_trend": "stable"
}

anchovy = {
    "population": 50,
    "last_action": None,
    "health_trend": "stable"
}

sardine = {
    "population": 45,
    "last_action": None,
    "health_trend": "stable"
}

sea_lion = {
    "population": 50,
    "last_action": None,
    "health_trend": "stable"
}

kelp = {
    "population": 60,
    "last_action": None,
    "health_trend": "stable"
}

urchin = {
    "population": 40,
    "last_action": None,
    "health_trend": "stable"
}

# ── Behavior deltas ──────────────────────────────────────────────────────────
PHYTOPLANKTON_BEHAVIORS = {
    "bloom":          +15,
    "die_off":        -20,
    "persist":          0,
    "migrate_depth":   -5,
}

ZOOPLANKTON_BEHAVIORS = {
    "graze":      +12,
    "swarm":       +3,
    "disperse":    -3,
    "starve":     -18,
    "reproduce":  +15,
}

# ── Prompt builders ──────────────────────────────────────────────────────────
def build_phytoplankton_prompt(agent, env):
    temp = env['temperature']
    nutrient = env['nutrients']

    if temp > 18:
        temp_status = "TOO HIGH - critically stressful, die_off likely"
    elif temp > 16:
        temp_status = "ELEVATED - mild stress, avoid bloom"
    else:
        temp_status = "OPTIMAL - good for growth"

    if nutrient > 0.7:
        nutrient_status = "ABUNDANT - bloom or reproduce conditions"
    elif nutrient > 0.4:
        nutrient_status = "MODERATE - persist or graze conditions"
    else:
        nutrient_status = "SCARCE - risk of die_off"

    return f"""You are a phytoplankton colony in the California Current. Pick a survival behavior RIGHT NOW.

TEMPERATURE ({temp}°C): {temp_status}
NUTRIENTS ({nutrient}/1.0): {nutrient_status}
pH: {env['pH']} (optimal 8.1-8.3)
POLLUTION: {env['pollution_index']}/1.0
YOUR POPULATION: {agent['population']}/100
YOUR LAST ACTION: {agent['last_action'] or 'none'}

DECISION RULES — follow strictly:
- If temp TOO HIGH → die_off
- If nutrients SCARCE and temp ELEVATED → die_off or migrate_depth
- If nutrients ABUNDANT and temp OPTIMAL → bloom
- If nutrients MODERATE → persist or migrate_depth
- If population already high (>80) → persist instead of bloom

Pick exactly one from: bloom, die_off, persist, migrate_depth

BEHAVIOR: [one word]
REASON: [one sentence first person]"""


def build_zooplankton_prompt(agent, env, phyto):
    food = phyto['population']
    if food < 20:
        food_status = "CRITICALLY LOW - you must pick starve"
    elif food < 40:
        food_status = "LOW - food is scarce, avoid graze or reproduce"
    elif food < 70:
        food_status = "MODERATE - some food available"
    else:
        food_status = "ABUNDANT - graze or reproduce are good choices"

    temp = env['temperature']
    if temp > 16:
        temp_status = "TOO HIGH - stressful even with food"
    else:
        temp_status = "OPTIMAL"

    return f"""You are a zooplankton colony in the California Current. Pick a survival behavior RIGHT NOW.

FOOD (phytoplankton {food}/100): {food_status}
PHYTOPLANKTON TREND: {phyto['health_trend']} (last action: {phyto['last_action']})
TEMPERATURE ({temp}°C): {temp_status}
YOUR POPULATION: {agent['population']}/100
YOUR LAST ACTION: {agent['last_action'] or 'none'}

DECISION RULES — follow strictly:
- If food CRITICALLY LOW → starve
- If food LOW → disperse or swarm
- If food MODERATE and temp OPTIMAL → graze
- If food ABUNDANT and temp OPTIMAL → reproduce or graze
- If temp TOO HIGH regardless of food → swarm or disperse

Pick exactly one from: graze, swarm, disperse, starve, reproduce

BEHAVIOR: [one word]
REASON: [one sentence first person]"""


# ── Tick functions ────────────────────────────────────────────────────────────
def parse_response(raw, behaviors, default):
    behavior = default
    for b in behaviors:
        if b in raw.lower():
            behavior = b
            break
    reason_match = re.search(r'REASON:\s*(.+)', raw)
    reason = reason_match.group(1).strip() if reason_match else "No reason provided."
    return behavior, reason


def update_agent(agent, behavior, deltas):
    delta = deltas[behavior]
    agent["population"] = max(0, min(100, agent["population"] + delta))
    agent["last_action"] = behavior
    agent["health_trend"] = "improving" if delta > 0 else "declining" if delta < 0 else "stable"
    return agent


def apply_policy_to_environment(policy_text: str, env: dict):
    """Apply a natural language policy to the environment state."""
    if not policy_text:
        return env, None

    print(f"Applying policy: {policy_text}")
    try:
        result = database_fetch.parse_policy(policy_text, baseline=env)
        env.update(result["environment"])
        print(f"Policy parse confidence: {result['confidence']:.2%}")
        print(f"Policy summary: {result['summary']}")
        print(f"Policy itself: {env}")
        return env, result
    except Exception as exc:
        print(f"  [policy parse error] {exc}")
        print("  Falling back to manual policy application.")
        fallback_env = database_fetch.apply_policy_manually(policy_text, baseline=env)
        env.update(fallback_env)
        return env, None


def tick_phytoplankton(agent, env):
    try:
        response = ollama.chat(
            model="llama3.1",
            messages=[{"role": "user", "content": build_phytoplankton_prompt(agent, env)}]
        )
        raw = response["message"]["content"]
    except Exception as e:
        print(f"  [Ollama error - phytoplankton]: {e}")
        raw = "BEHAVIOR: persist\nREASON: Defaulting due to error."

    behavior, reason = parse_response(raw, PHYTOPLANKTON_BEHAVIORS, "persist")
    agent = update_agent(agent, behavior, PHYTOPLANKTON_BEHAVIORS)
    return agent, behavior, reason


def tick_zooplankton(agent, env, phyto):
    try:
        response = ollama.chat(
            model="llama3.1",
            messages=[{"role": "user", "content": build_zooplankton_prompt(agent, env, phyto)}]
        )
        raw = response["message"]["content"]
    except Exception as e:
        print(f"  [Ollama error - zooplankton]: {e}")
        raw = "BEHAVIOR: disperse\nREASON: Defaulting due to error."

    behavior, reason = parse_response(raw, ZOOPLANKTON_BEHAVIORS, "disperse")
    agent = update_agent(agent, behavior, ZOOPLANKTON_BEHAVIORS)
    return agent, behavior, reason


# ── Map visualization ─────────────────────────────────────────────────────────
simulation_history = []

def record_year(year, agents, environment, behaviors):
    """Record the state of a simulation year for later visualization."""
    simulation_history.append({
        'year': year,
        'agents': {k: v.copy() for k, v in agents.items()},
        'environment': environment.copy(),
        'behaviors': behaviors.copy()
    })


def generate_final_map():
    """Generate a single interactive HTML file with all simulation years."""
    
    # Convert simulation history to JavaScript data
    import json
    years_data = json.dumps(simulation_history, indent=2)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TIDAL WAVE - California Current Ecosystem Simulation</title>
    <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Crimson Pro', serif;
            background: linear-gradient(135deg, #0a1828 0%, #1a3a52 50%, #2a5a7a 100%);
            color: #e8f4f8;
            min-height: 100vh;
            padding: 2rem;
            overflow-x: hidden;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 2rem;
            position: relative;
        }}
        
        h1 {{
            font-size: 3.5rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #4dd0e1 0%, #80deea 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 0 0 40px rgba(77, 208, 225, 0.3);
        }}
        
        .map-container {{
            background: rgba(10, 24, 40, 0.6);
            border-radius: 1.5rem;
            padding: 2rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(77, 208, 225, 0.2);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }}
        
        .map-title {{
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: #80deea;
            margin-bottom: 1rem;
            text-align: center;
        }}
        
        #regionMap {{
            height: 400px;
            border-radius: 1rem;
            overflow: hidden;
            border: 2px solid rgba(77, 208, 225, 0.3);
        }}
        
        .controls {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1.5rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }}
        
        .year-nav {{
            display: flex;
            align-items: center;
            gap: 1rem;
            background: rgba(10, 24, 40, 0.6);
            padding: 1rem 2rem;
            border-radius: 2rem;
            border: 1px solid rgba(77, 208, 225, 0.3);
        }}
        
        .nav-button {{
            background: rgba(77, 208, 225, 0.2);
            border: 1px solid rgba(77, 208, 225, 0.4);
            color: #4dd0e1;
            font-family: 'Space Mono', monospace;
            font-size: 1rem;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 700;
        }}
        
        .nav-button:hover:not(:disabled) {{
            background: rgba(77, 208, 225, 0.3);
            border-color: rgba(77, 208, 225, 0.6);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(77, 208, 225, 0.3);
        }}
        
        .nav-button:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}
        
        .year-display {{
            font-family: 'Space Mono', monospace;
            font-size: 1.8rem;
            color: #80deea;
            font-weight: 700;
            min-width: 120px;
            text-align: center;
        }}
        
        .year-dots {{
            display: flex;
            gap: 0.5rem;
        }}
        
        .year-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: rgba(77, 208, 225, 0.3);
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }}
        
        .year-dot.active {{
            background: #4dd0e1;
            box-shadow: 0 0 12px rgba(77, 208, 225, 0.6);
            transform: scale(1.3);
        }}
        
        .year-dot:hover {{
            background: #80deea;
            transform: scale(1.2);
        }}
        
        .ocean-map {{
            background: linear-gradient(180deg, rgba(26, 58, 82, 0.4) 0%, rgba(10, 24, 40, 0.6) 100%);
            border-radius: 1.5rem;
            padding: 3rem;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(77, 208, 225, 0.2);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }}
        
        .ocean-map::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 30%, rgba(77, 208, 225, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 70%, rgba(128, 222, 234, 0.03) 0%, transparent 50%);
            pointer-events: none;
        }}
        
        .depth-layers {{
            display: grid;
            gap: 2rem;
            position: relative;
            z-index: 1;
        }}
        
        .layer {{
            background: rgba(255, 255, 255, 0.03);
            border-left: 4px solid;
            padding: 2rem;
            border-radius: 0.75rem;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }}
        
        .layer:hover {{
            background: rgba(255, 255, 255, 0.06);
            transform: translateX(10px);
        }}
        
        .layer.surface {{ border-color: #4dd0e1; }}
        .layer.mid-water {{ border-color: #26c6da; }}
        .layer.benthic {{ border-color: #00acc1; }}
        
        .layer-title {{
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: #80deea;
            margin-bottom: 1.5rem;
            opacity: 0.7;
        }}
        
        .species-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
        }}
        
        .species-card {{
            background: rgba(10, 24, 40, 0.4);
            border-radius: 0.75rem;
            padding: 1.5rem;
            border: 1px solid rgba(77, 208, 225, 0.15);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }}
        
        .species-card:hover {{
            border-color: rgba(77, 208, 225, 0.4);
            box-shadow: 0 10px 30px rgba(77, 208, 225, 0.1);
        }}
        
        .species-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .species-icon {{
            font-size: 2.5rem;
            line-height: 1;
        }}
        
        .species-name {{
            font-size: 1.4rem;
            font-weight: 600;
            color: #e8f4f8;
        }}
        
        .population-bar {{
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 1rem;
            overflow: hidden;
            margin: 1rem 0;
            position: relative;
        }}
        
        .population-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4dd0e1, #80deea);
            border-radius: 1rem;
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            box-shadow: 0 0 10px rgba(77, 208, 225, 0.5);
        }}
        
        .population-fill::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            animation: shimmer 2s infinite;
        }}
        
        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}
        
        .population-value {{
            font-family: 'Space Mono', monospace;
            font-size: 1.8rem;
            font-weight: 700;
            color: #4dd0e1;
            margin: 0.5rem 0;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 0.35rem 0.85rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            font-family: 'Space Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.5rem;
        }}
        
        .status-improving {{
            background: rgba(102, 187, 106, 0.2);
            color: #66bb6a;
            border: 1px solid rgba(102, 187, 106, 0.3);
        }}
        
        .status-stable {{
            background: rgba(77, 208, 225, 0.2);
            color: #4dd0e1;
            border: 1px solid rgba(77, 208, 225, 0.3);
        }}
        
        .status-declining {{
            background: rgba(239, 83, 80, 0.2);
            color: #ef5350;
            border: 1px solid rgba(239, 83, 80, 0.3);
        }}
        
        .behavior {{
            font-size: 0.9rem;
            color: #b0bec5;
            margin-top: 0.75rem;
            font-style: italic;
            line-height: 1.4;
        }}
        
        .behavior strong {{
            color: #80deea;
            font-style: normal;
        }}
        
        .environment-panel {{
            background: rgba(10, 24, 40, 0.6);
            border-radius: 1rem;
            padding: 2rem;
            margin-top: 3rem;
            border: 1px solid rgba(77, 208, 225, 0.2);
        }}
        
        .env-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
        }}
        
        .env-stat {{
            text-align: center;
        }}
        
        .env-label {{
            font-family: 'Space Mono', monospace;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #80deea;
            opacity: 0.7;
            margin-bottom: 0.5rem;
        }}
        
        .env-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #4dd0e1;
            font-family: 'Space Mono', monospace;
        }}
        
        .env-unit {{
            font-size: 1rem;
            color: #b0bec5;
            margin-left: 0.25rem;
        }}
        
        /* Leaflet customizations */
        .leaflet-container {{
            background: #1a3a52;
        }}
        
        .leaflet-popup-content-wrapper {{
            background: rgba(10, 24, 40, 0.95);
            color: #e8f4f8;
            border: 1px solid rgba(77, 208, 225, 0.3);
            border-radius: 0.5rem;
        }}
        
        .leaflet-popup-tip {{
            background: rgba(10, 24, 40, 0.95);
        }}
        
        .leaflet-popup-content {{
            font-family: 'Crimson Pro', serif;
            margin: 1rem;
        }}
        
        .leaflet-popup-content h3 {{
            color: #4dd0e1;
            margin-bottom: 0.5rem;
        }}
        
        @media (max-width: 768px) {{
            h1 {{
                font-size: 2.5rem;
            }}
            
            .ocean-map {{
                padding: 1.5rem;
            }}
            
            .species-grid {{
                grid-template-columns: 1fr;
            }}
            
            .controls {{
                flex-direction: column;
            }}
            
            #regionMap {{
                height: 300px;
            }}
        }}
        
        .wave {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 200%;
            height: 100px;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 100'%3E%3Cpath fill='rgba(77, 208, 225, 0.05)' d='M0,50 Q300,0 600,50 T1200,50 L1200,100 L0,100 Z'/%3E%3C/svg%3E");
            background-size: 1200px 100px;
            animation: wave 20s linear infinite;
            pointer-events: none;
            z-index: 0;
        }}
        
        @keyframes wave {{
            0% {{ transform: translateX(0); }}
            100% {{ transform: translateX(-1200px); }}
        }}
        
        .fade-in {{
            animation: fadeIn 0.4s ease-in;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <div class="wave"></div>
    <div class="container">
        <header>
            <h1>TIDAL WAVE</h1>
        </header>
        
        <div class="controls">
            <div class="year-nav">
                <button class="nav-button" id="prevBtn" onclick="changeYear(-1)">← PREV</button>
                <div class="year-display" id="yearDisplay">YEAR 1</div>
                <button class="nav-button" id="nextBtn" onclick="changeYear(1)">NEXT →</button>
            </div>
            <div class="year-dots" id="yearDots"></div>
        </div>
        
        <div class="map-container">
            <div class="map-title">California Current Ecosystem Region</div>
            <div id="regionMap"></div>
        </div>
        
        <div id="mapContainer"></div>
    </div>
    
    <script>
        const simulationData = {years_data};
        let currentYearIndex = 0;
        
        // Initialize the California Current map
        function initRegionMap() {{
            const map = L.map('regionMap').setView([35.5, -121.5], 6);
            
            // Use ocean-themed tiles
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri',
                maxZoom: 13,
                minZoom: 5
            }}).addTo(map);
            
            // Define the California Current region polygon
            const californiaCurrentZone = [
                [41.0, -125.0],  // Northern California
                [41.0, -121.0],
                [32.5, -117.0],  // Southern California/Baja
                [32.5, -122.0],
                [41.0, -125.0]
            ];
            
            // Add the California Current zone
            L.polygon(californiaCurrentZone, {{
                color: '#4dd0e1',
                fillColor: '#4dd0e1',
                fillOpacity: 0.15,
                weight: 2,
                dashArray: '5, 10'
            }}).addTo(map).bindPopup('<h3>California Current System</h3><p>Cold-water upwelling zone supporting rich marine biodiversity</p>');
            
            // Add key location markers
            const locations = [
                {{
                    name: 'Monterey Bay',
                    coords: [36.8, -121.9],
                    description: 'Major upwelling center and kelp forest habitat'
                }},
                {{
                    name: 'Channel Islands',
                    coords: [34.0, -119.8],
                    description: 'Critical breeding grounds for sea lions and seabirds'
                }},
                {{
                    name: 'Point Conception',
                    coords: [34.45, -120.47],
                    description: 'Biogeographic boundary - warm and cold currents meet'
                }},
                {{
                    name: 'San Diego',
                    coords: [32.7, -117.2],
                    description: 'Southern extent of simulation region'
                }}
            ];
            
            locations.forEach(loc => {{
                L.circleMarker(loc.coords, {{
                    radius: 6,
                    fillColor: '#80deea',
                    color: '#4dd0e1',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                }}).addTo(map).bindPopup(`<h3>${{loc.name}}</h3><p>${{loc.description}}</p>`);
            }});
            
            // Add current flow arrows (simplified)
            const currentArrows = [
                [[40.0, -124.5], [38.0, -123.5]],
                [[38.0, -123.5], [36.0, -122.0]],
                [[36.0, -122.0], [34.0, -120.5]],
                [[34.0, -120.5], [33.0, -118.5]]
            ];
            
            currentArrows.forEach(arrow => {{
                L.polyline(arrow, {{
                    color: '#26c6da',
                    weight: 3,
                    opacity: 0.6,
                    dashArray: '10, 5'
                }}).addTo(map).bindPopup('<h3>California Current Flow</h3><p>Southward cold-water flow along the coast</p>');
            }});
        }}
        
        function renderYear(index) {{
            const data = simulationData[index];
            const agents = data.agents;
            const env = data.environment;
            const behaviors = data.behaviors;
            
            const html = `
                <div class="ocean-map fade-in">
                    <div class="depth-layers">
                        <div class="layer surface">
                            <div class="layer-title">Surface Waters (0-50m)</div>
                            <div class="species-grid">
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🌿</span>
                                        <span class="species-name">Phytoplankton</span>
                                    </div>
                                    <div class="population-value">${{agents.phytoplankton.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.phytoplankton.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.phytoplankton.health_trend}}">${{agents.phytoplankton.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.phytoplankton.action}}</strong> — ${{behaviors.phytoplankton.reason}}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="layer mid-water">
                            <div class="layer-title">Mid-Water Zone (50-200m)</div>
                            <div class="species-grid">
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🦐</span>
                                        <span class="species-name">Zooplankton</span>
                                    </div>
                                    <div class="population-value">${{agents.zooplankton.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.zooplankton.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.zooplankton.health_trend}}">${{agents.zooplankton.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.zooplankton.action}}</strong> — ${{behaviors.zooplankton.reason}}</div>
                                </div>
                                
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🐟</span>
                                        <span class="species-name">Anchovy</span>
                                    </div>
                                    <div class="population-value">${{agents.anchovy.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.anchovy.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.anchovy.health_trend}}">${{agents.anchovy.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.anchovy.action}}</strong> — ${{behaviors.anchovy.reason}}</div>
                                </div>
                                
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🐟</span>
                                        <span class="species-name">Sardine</span>
                                    </div>
                                    <div class="population-value">${{agents.sardine.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.sardine.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.sardine.health_trend}}">${{agents.sardine.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.sardine.action}}</strong> — ${{behaviors.sardine.reason}}</div>
                                </div>
                                
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🦁</span>
                                        <span class="species-name">Sea Lion</span>
                                    </div>
                                    <div class="population-value">${{agents.sea_lion.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.sea_lion.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.sea_lion.health_trend}}">${{agents.sea_lion.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.sea_lion.action}}</strong> — ${{behaviors.sea_lion.reason}}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="layer benthic">
                            <div class="layer-title">Benthic Zone (Seafloor)</div>
                            <div class="species-grid">
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🌱</span>
                                        <span class="species-name">Kelp</span>
                                    </div>
                                    <div class="population-value">${{agents.kelp.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.kelp.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.kelp.health_trend}}">${{agents.kelp.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.kelp.action}}</strong> — ${{behaviors.kelp.reason}}</div>
                                </div>
                                
                                <div class="species-card">
                                    <div class="species-header">
                                        <span class="species-icon">🦀</span>
                                        <span class="species-name">Urchin</span>
                                    </div>
                                    <div class="population-value">${{agents.urchin.population}}<span style="font-size: 1rem; color: #b0bec5;">/100</span></div>
                                    <div class="population-bar">
                                        <div class="population-fill" style="width: ${{agents.urchin.population}}%"></div>
                                    </div>
                                    <span class="status-badge status-${{agents.urchin.health_trend}}">${{agents.urchin.health_trend}}</span>
                                    <div class="behavior"><strong>${{behaviors.urchin.action}}</strong> — ${{behaviors.urchin.reason}}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="environment-panel fade-in">
                    <h2 style="font-size: 1.5rem; margin-bottom: 1rem; color: #80deea;">Environmental Conditions</h2>
                    <div class="env-grid">
                        <div class="env-stat">
                            <div class="env-label">Temperature</div>
                            <div class="env-value">${{env.temperature}}<span class="env-unit">°C</span></div>
                        </div>
                        <div class="env-stat">
                            <div class="env-label">Nutrients</div>
                            <div class="env-value">${{env.nutrients.toFixed(2)}}<span class="env-unit">/1.0</span></div>
                        </div>
                        <div class="env-stat">
                            <div class="env-label">pH Level</div>
                            <div class="env-value">${{env.pH.toFixed(2)}}</div>
                        </div>
                        <div class="env-stat">
                            <div class="env-label">Pollution</div>
                            <div class="env-value">${{env.pollution_index.toFixed(2)}}<span class="env-unit">/1.0</span></div>
                        </div>
                        <div class="env-stat">
                            <div class="env-label">Fishing Pressure</div>
                            <div class="env-value">${{env.fishing_pressure.toFixed(2)}}<span class="env-unit">/1.0</span></div>
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('mapContainer').innerHTML = html;
            document.getElementById('yearDisplay').textContent = `YEAR ${{data.year}}`;
            
            // Update navigation buttons
            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === simulationData.length - 1;
            
            // Update dots
            updateDots();
        }}
        
        function changeYear(delta) {{
            const newIndex = currentYearIndex + delta;
            if (newIndex >= 0 && newIndex < simulationData.length) {{
                currentYearIndex = newIndex;
                renderYear(currentYearIndex);
            }}
        }}
        
        function jumpToYear(index) {{
            currentYearIndex = index;
            renderYear(currentYearIndex);
        }}
        
        function updateDots() {{
            const dotsContainer = document.getElementById('yearDots');
            dotsContainer.innerHTML = '';
            
            simulationData.forEach((_, index) => {{
                const dot = document.createElement('div');
                dot.className = 'year-dot' + (index === currentYearIndex ? ' active' : '');
                dot.onclick = () => jumpToYear(index);
                dot.title = `Year ${{index + 1}}`;
                dotsContainer.appendChild(dot);
            }});
        }}
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') changeYear(-1);
            if (e.key === 'ArrowRight') changeYear(1);
        }});
        
        // Initialize everything
        initRegionMap();
        renderYear(0);
    </script>
</body>
</html>"""
    
    return html


def display_final_map():
    """Generate and open the final interactive map with all years."""
    html_content = generate_final_map()
    
    # Save to current directory
    output_path = os.path.join(os.getcwd(), 'fathom_simulation.html')
    with open(output_path, 'w') as f:
        f.write(html_content)
    
    # Open in browser
    webbrowser.open('file://' + os.path.abspath(output_path))
    print(f"\n✓ Interactive map generated: {output_path}")
    print(f"✓ Opened in browser (use ← → arrows or dots to navigate years)")
    
    return output_path


# ── Main simulation loop ──────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the California Current ecosystem simulation.")
    parser.add_argument("--policy", type=str, default="",
                        help="Natural language policy to apply before running the simulation.")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open browser maps (just run simulation in terminal)")
    args = parser.parse_args()

    if args.policy:
        apply_policy_to_environment(args.policy, environment)

    print("=" * 60)
    print("  TIDAL WAVE — California Current Ecosystem Simulation")
    print("=" * 60)
    print(f"Starting conditions: temp={environment['temperature']}°C | "
          f"nutrients={environment['nutrients']} | "
          f"fishing={environment['fishing_pressure']}\n")

    for tick_num in range(1, 6):
        print(f"── YEAR {tick_num} {'─' * 50}")

        # Each species runs in order — bottom of food chain first
        # State from lower species feeds into the next one
        phytoplankton, p_behavior, p_reason = tick_phytoplankton(phytoplankton, environment)
        zooplankton, z_behavior, z_reason   = tick_zooplankton(zooplankton, environment, phytoplankton)
        anchovy, a_behavior, a_reason       = anchovy_module.tick(anchovy, environment, zooplankton)
        sardine, s_behavior, s_reason       = sardine_module.tick(sardine, environment, zooplankton, anchovy)
        sea_lion, sl_behavior, sl_reason    = sealion_module.tick(sea_lion, environment, anchovy, sardine)
        urchin, u_behavior, u_reason       = urchin_module.tick(urchin, environment, kelp)
        kelp, k_behavior, k_reason         = kelp_module.tick(kelp, environment, urchin)

        # Print results
        print(f"🌿 Phytoplankton | {p_behavior:<20} | pop: {phytoplankton['population']:>3}/100 | {phytoplankton['health_trend']}")
        print(f"   → {p_reason}")
        print(f"🦐 Zooplankton   | {z_behavior:<20} | pop: {zooplankton['population']:>3}/100 | {zooplankton['health_trend']}")
        print(f"   → {z_reason}")
        print(f"🐟 Anchovy       | {a_behavior:<20} | pop: {anchovy['population']:>3}/100 | {anchovy['health_trend']}")
        print(f"   → {a_reason}")
        print(f"🐟 Sardine       | {s_behavior:<20} | pop: {sardine['population']:>3}/100 | {sardine['health_trend']}")
        print(f"   → {s_reason}")
        print(f"🦁 Sea Lion      | {sl_behavior:<20} | pop: {sea_lion['population']:>3}/100 | {sea_lion['health_trend']}")
        print(f"   → {sl_reason}")
        print(f"🌱 Kelp          | {k_behavior:<20} | pop: {kelp['population']:>3}/100 | {kelp['health_trend']}")
        print(f"   → {k_reason}")
        print(f"🦀 Urchin        | {u_behavior:<20} | pop: {urchin['population']:>3}/100 | {urchin['health_trend']}")
        print(f"   → {u_reason}")
        print()

        # Record this year's state for the final map
        agents_snapshot = {
            'phytoplankton': phytoplankton.copy(),
            'zooplankton': zooplankton.copy(),
            'anchovy': anchovy.copy(),
            'sardine': sardine.copy(),
            'sea_lion': sea_lion.copy(),
            'kelp': kelp.copy(),
            'urchin': urchin.copy()
        }
        
        behaviors_snapshot = {
            'phytoplankton': {'action': p_behavior, 'reason': p_reason},
            'zooplankton': {'action': z_behavior, 'reason': z_reason},
            'anchovy': {'action': a_behavior, 'reason': a_reason},
            'sardine': {'action': s_behavior, 'reason': s_reason},
            'sea_lion': {'action': sl_behavior, 'reason': sl_reason},
            'kelp': {'action': k_behavior, 'reason': k_reason},
            'urchin': {'action': u_behavior, 'reason': u_reason}
        }
        
        record_year(tick_num, agents_snapshot, environment, behaviors_snapshot)

        time.sleep(0.3)

    print("=" * 60)
    print("FINAL STATE")
    print(f"🌿 Phytoplankton: {phytoplankton['population']}/100 ({phytoplankton['health_trend']})")
    print(f"🦐 Zooplankton:   {zooplankton['population']}/100 ({zooplankton['health_trend']})")
    print(f"🐟 Anchovy:       {anchovy['population']}/100 ({anchovy['health_trend']})")
    print(f"🐟 Sardine:       {sardine['population']}/100 ({sardine['health_trend']})")
    print(f"🦁 Sea Lion:      {sea_lion['population']}/100 ({sea_lion['health_trend']})")
    print(f"🌱 Kelp:          {kelp['population']}/100 ({kelp['health_trend']})")
    print(f"🦀 Urchin:        {urchin['population']}/100 ({urchin['health_trend']})")
    print("=" * 60)
    
    # Generate and display the interactive map with all years
    if not args.no_browser:
        display_final_map()