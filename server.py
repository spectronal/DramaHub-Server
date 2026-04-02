from flask import Flask, request, abort
import os
import requests
import json

app = Flask(__name__)

SCRIPT_TOKEN   = os.environ.get("SCRIPT_TOKEN", "my_token")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER    = os.environ.get("GITHUB_USER", "MY_USERNAME")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "MY_REPO")
GITHUB_BRANCH  = os.environ.get("GITHUB_BRANCH", "main")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

BASE_PATH = "AnimeGhostBuild"

SCRIPTS = {
    "main":          f"{BASE_PATH}/Main.lua",
    "state":         f"{BASE_PATH}/Systems/State.lua",
    "utils":         f"{BASE_PATH}/Core/Utils.lua",
    "player":        f"{BASE_PATH}/Core/Player.lua",
    "rewards":       f"{BASE_PATH}/Core/Rewards.lua",
    "farm":          f"{BASE_PATH}/Core/Farm.lua",
    "gamemode":      f"{BASE_PATH}/Core/Gamemode.lua",
    "gacha":         f"{BASE_PATH}/Core/Gacha.lua",
    "scrolls":       f"{BASE_PATH}/Core/Scrolls.lua",
    "exchange":      f"{BASE_PATH}/Core/Exchange.lua",
    "potions":       f"{BASE_PATH}/Core/Potions.lua",
    "ui-about":      f"{BASE_PATH}/UI/About.lua",
    "ui-updatelogs": f"{BASE_PATH}/UI/UpdateLogs.lua",
    "ui-farm":       f"{BASE_PATH}/UI/Farm.lua",
    "ui-player":     f"{BASE_PATH}/UI/Player.lua",
    "ui-gamemode":   f"{BASE_PATH}/UI/Gamemode.lua",
    "ui-scroll":     f"{BASE_PATH}/UI/Scroll.lua",
    "ui-potion":     f"{BASE_PATH}/UI/Potions.lua",
    "ui-exchange":   f"{BASE_PATH}/UI/Exchange.lua",
    "ui-gacha":      f"{BASE_PATH}/UI/Gacha.lua",
}

control_state = {}

# ── Helpers ──────────────────────────────────────────────────────────────────

def validate_token():
    token = request.args.get("token") or request.headers.get("X-Token")
    if token != SCRIPT_TOKEN:
        abort(403)

def fetch_from_github(file_path):
    url = (
        f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}"
        f"/contents/{file_path}?ref={GITHUB_BRANCH}"
    )
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        abort(404)
    elif response.status_code in (401, 403):
        abort(500)
    elif response.status_code != 200:
        abort(500)
    return response.text

# ── Script Endpoints ──────────────────────────────────────────────────────────

@app.route("/init")
def serve_init():
    content = fetch_from_github("init.lua")
    return content, 200, {"Content-Type": "text/plain"}

@app.route("/loader")
def serve_loader():
    url = (
        f"https://api.github.com/repos/{GITHUB_USER}/Loader"
        f"/contents/Loader.lua?ref=main"
    )
    headers = {"Accept": "application/vnd.github.v3.raw"}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        abort(404)
    elif response.status_code != 200:
        abort(500)
    return response.text, 200, {"Content-Type": "text/plain"}

@app.route("/script/<name>")
def serve_script(name):
    validate_token()
    file_path = SCRIPTS.get(name)
    if not file_path:
        abort(404)
    content = fetch_from_github(file_path)
    return content, 200, {"Content-Type": "text/plain"}

# ── Control Endpoints ─────────────────────────────────────────────────────────

@app.route("/control", methods=["GET"])
def get_control():
    validate_token()
    return json.dumps(control_state), 200, {"Content-Type": "application/json"}

@app.route("/control", methods=["POST"])
def set_control():
    validate_token()
    global control_state
    data = request.get_json()
    if not data:
        abort(400)
    for tab, settings in data.items():
        if tab not in control_state:
            control_state[tab] = {}
        control_state[tab].update(settings)
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}

@app.route("/control/reset", methods=["POST"])
def reset_control():
    validate_token()
    global control_state
    control_state = {}
    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}

# ── Admin Panel ───────────────────────────────────────────────────────────────

@app.route("/script/admpanel")
def admpanel():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        abort(403)
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DramaHub Admin Panel</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #0f0f0f; color: #fff; font-family: 'Segoe UI', sans-serif; padding: 30px; }}
        h1 {{ color: #a855f7; margin-bottom: 5px; font-size: 22px; }}
        p.sub {{ color: #555; font-size: 13px; margin-bottom: 30px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
        .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; }}
        .card h2 {{ font-size: 12px; color: #a855f7; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; }}
        .row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #222; }}
        .row:last-child {{ border-bottom: none; }}
        .row label.name {{ font-size: 13px; color: #ccc; }}
        .toggle {{ position: relative; width: 40px; height: 22px; flex-shrink: 0; }}
        .toggle input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{ position: absolute; cursor: pointer; inset: 0; background: #333; border-radius: 22px; transition: .3s; }}
        .slider:before {{ content: ""; position: absolute; width: 16px; height: 16px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .3s; }}
        input:checked + .slider {{ background: #a855f7; }}
        input:checked + .slider:before {{ transform: translateX(18px); }}
        .actions {{ margin-top: 24px; display: flex; gap: 10px; }}
        .btn {{ flex: 1; padding: 11px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: .2s; }}
        .btn-save {{ background: #a855f7; color: white; }}
        .btn-save:hover {{ background: #9333ea; }}
        .btn-reset {{ background: #ef4444; color: white; }}
        .btn-reset:hover {{ background: #dc2626; }}
        #toast {{ position: fixed; bottom: 24px; right: 24px; background: #a855f7; color: white; padding: 12px 20px; border-radius: 8px; font-size: 13px; display: none; box-shadow: 0 4px 20px rgba(168,85,247,.4); }}
        .status-bar {{ margin-bottom: 20px; padding: 10px 16px; background: #1a1a1a; border-radius: 8px; font-size: 12px; color: #666; border: 1px solid #2a2a2a; }}
        .dot {{ display: inline-block; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .4; }} }}
    </style>
</head>
<body>
    <h1>DramaHub Admin Panel</h1>
    <p class="sub">Controle remoto do script em tempo real</p>

    <div class="status-bar">
        <span class="dot"></span>Conectado ao servidor · Auto-refresh a cada 5s
    </div>

    <div class="grid" id="panel">Carregando...</div>

    <div class="actions">
        <button class="btn btn-save" onclick="saveAll()">💾 Salvar tudo</button>
        <button class="btn btn-reset" onclick="resetAll()">🔄 Resetar tudo</button>
    </div>

    <div id="toast"></div>

    <script>
        const TOKEN = "{SCRIPT_TOKEN}"
        const BASE  = "/control"

        const TABS = {{
            FarmTab:      ["AutoFarm", "AutoFarmEasterBoss", "AutoFarmWithScroll"],
            GamemodesTab: ["AutoFarmMobs", "AutoJoinPublicGamemode", "AutoJoinSelectedGamemode", "AutoCreateGamemode", "AutoLeaveGamemode", "AutoEquipBest", "AutoEquipTitle"],
            PlayerTab:    ["AutoClick", "AutoClickAnimation", "AutoAscension", "AutoRewards", "AutoAchievments", "AutoChests"],
            GachaTab:     ["AutoGacha"],
            ScrollsTab:   ["AutoOpenScroll"],
            PotionsTab:   ["AutoUsePotions", "AutoPausePotions", "AutoUnPausePotions"],
        }}

        let currentState = {{}}

        async function loadState() {{
            try {{
                const res = await fetch(`${{BASE}}?token=${{TOKEN}}`)
                currentState = await res.json()
                renderPanel()
            }} catch(e) {{
                console.error("Erro ao carregar estado:", e)
            }}
        }}

        function renderPanel() {{
            const grid = document.getElementById("panel")
            grid.innerHTML = ""

            for (const [tab, keys] of Object.entries(TABS)) {{
                if (keys.length === 0) continue

                const card = document.createElement("div")
                card.className = "card"
                card.innerHTML = `<h2>${{tab.replace("Tab", "")}}</h2>`

                for (const key of keys) {{
                    const val = currentState[tab]?.[key] ?? false
                    const row = document.createElement("div")
                    row.className = "row"
                    row.innerHTML = `
                        <label class="name">${{key}}</label>
                        <label class="toggle">
                            <input type="checkbox" id="${{tab}}_${{key}}" ${{val ? "checked" : ""}}>
                            <span class="slider"></span>
                        </label>`
                    card.appendChild(row)
                }}

                grid.appendChild(card)
            }}
        }}

        async function saveAll() {{
            const payload = {{}}
            for (const [tab, keys] of Object.entries(TABS)) {{
                payload[tab] = {{}}
                for (const key of keys) {{
                    const el = document.getElementById(`${{tab}}_${{key}}`)
                    if (el) payload[tab][key] = el.checked
                }}
            }}

            await fetch(`${{BASE}}?token=${{TOKEN}}`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify(payload)
            }})

            showToast("✅ Salvo com sucesso!")
        }}

        async function resetAll() {{
            await fetch(`${{BASE}}/reset?token=${{TOKEN}}`, {{ method: "POST" }})
            await loadState()
            showToast("🔄 Resetado!")
        }}

        function showToast(msg) {{
            const t = document.getElementById("toast")
            t.textContent = msg
            t.style.display = "block"
            setTimeout(() => t.style.display = "none", 3000)
        }}

        loadState()
        setInterval(loadState, 5000)
    </script>
</body>
</html>'''

# ── Root ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return "404 Not Found", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
