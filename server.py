from flask import Flask, request, abort
import os
import requests
import json
import time

app = Flask(__name__)

SCRIPT_TOKEN   = os.environ.get("SCRIPT_TOKEN", "my_token")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER    = os.environ.get("GITHUB_USER", "MY_USERNAME")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "MY_REPO")
GITHUB_BRANCH  = os.environ.get("GITHUB_BRANCH", "main")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "spectronal")

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

# { userId: { settings: {...}, info: { username, lastSeen }, override: {...} } }
players_state = {}

def validate_token():
    token = request.args.get("token") or request.headers.get("X-Token")
    if token != SCRIPT_TOKEN:
        abort(403)

def validate_password():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
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

@app.route("/control/report", methods=["POST"])
def report_state():
    validate_token()
    data = request.get_json()
    if not data:
        abort(400)

    user_id  = str(data.get("userId"))
    username = data.get("username", "Unknown")
    settings = data.get("settings", {})

    if not user_id:
        abort(400)

    if user_id not in players_state:
        players_state[user_id] = {"settings": {}, "override": {}, "info": {}}

    players_state[user_id]["settings"] = settings
    players_state[user_id]["info"] = {
        "username": username,
        "lastSeen": time.time()
    }

    override = players_state[user_id].get("override", {})
    players_state[user_id]["override"] = {}

    return json.dumps({"override": override}), 200, {"Content-Type": "application/json"}

@app.route("/control/override/<user_id>", methods=["POST"])
def set_override(user_id):
    validate_password()
    data = request.get_json()
    if not data:
        abort(400)

    if user_id not in players_state:
        players_state[user_id] = {"settings": {}, "override": {}, "info": {}}

    for tab, settings in data.items():
        if tab not in players_state[user_id]["override"]:
            players_state[user_id]["override"][tab] = {}
        if isinstance(settings, dict):
            players_state[user_id]["override"][tab].update(settings)

    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}

@app.route("/control/players", methods=["GET"])
def get_players():
    validate_password()
    return json.dumps(players_state), 200, {"Content-Type": "application/json"}

@app.route("/script/admpanel")
def admpanel():
    validate_password()
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
        p.sub {{ color: #555; font-size: 13px; margin-bottom: 20px; }}
        .status-bar {{ margin-bottom: 20px; padding: 10px 16px; background: #1a1a1a; border-radius: 8px; font-size: 12px; color: #666; border: 1px solid #2a2a2a; display: flex; justify-content: space-between; align-items: center; }}
        .dot {{ display: inline-block; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.4; }} }}
        .players-list {{ display: flex; flex-direction: column; gap: 16px; }}
        .player-card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; overflow: hidden; }}
        .player-header {{ padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }}
        .player-header:hover {{ background: #222; }}
        .player-name {{ font-size: 15px; font-weight: 600; color: #a855f7; }}
        .player-meta {{ font-size: 12px; color: #555; margin-top: 2px; }}
        .player-body {{ padding: 20px; display: none; border-top: 1px solid #2a2a2a; }}
        .player-body.open {{ display: block; }}
        .tabs-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
        .tab-card {{ background: #111; border: 1px solid #222; border-radius: 10px; padding: 16px; }}
        .tab-card h3 {{ font-size: 11px; color: #a855f7; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }}
        .row {{ display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid #1a1a1a; gap: 10px; }}
        .row:last-child {{ border-bottom: none; }}
        .row span {{ font-size: 12px; color: #ccc; flex: 1; }}
        .toggle {{ position: relative; width: 36px; height: 20px; flex-shrink: 0; }}
        .toggle input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{ position: absolute; cursor: pointer; inset: 0; background: #333; border-radius: 20px; transition: .3s; }}
        .slider:before {{ content: ""; position: absolute; width: 14px; height: 14px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .3s; }}
        input:checked + .slider {{ background: #a855f7; }}
        input:checked + .slider:before {{ transform: translateX(16px); }}
        .input-num {{ background: #222; border: 1px solid #333; color: #fff; border-radius: 6px; padding: 4px 8px; width: 80px; font-size: 12px; }}
        .input-str {{ background: #222; border: 1px solid #333; color: #fff; border-radius: 6px; padding: 4px 8px; width: 130px; font-size: 12px; }}
        .save-btn {{ margin-top: 16px; padding: 10px 20px; background: #a855f7; border: none; color: white; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }}
        .save-btn:hover {{ background: #9333ea; }}
        .no-players {{ color: #444; font-size: 14px; padding: 40px; text-align: center; }}
        #toast {{ position: fixed; bottom: 24px; right: 24px; background: #a855f7; color: white; padding: 12px 20px; border-radius: 8px; font-size: 13px; display: none; box-shadow: 0 4px 20px rgba(168,85,247,.4); z-index: 999; }}
        .online {{ color: #22c55e; }}
        .offline {{ color: #ef4444; }}
    </style>
</head>
<body>
    <h1>DramaHub Admin Panel</h1>
    <p class="sub">Controle individual de cada player em tempo real</p>

    <div class="status-bar">
        <div><span class="dot"></span>Auto-refresh a cada 3s</div>
        <div id="player-count">0 players</div>
    </div>

    <div class="players-list" id="players-list">
        <div class="no-players">Nenhum player ativo ainda.</div>
    </div>

    <div id="toast"></div>

    <script>
        const PASSWORD = "{ADMIN_PASSWORD}"

        const TABS = {{
            FarmTab: {{
                booleans: ["AutoFarm", "AutoFarmWithScroll", "AutoFarmEasterBoss"],
                strings:  ["Priority"],
                numbers:  [],
            }},
            ScrollsTab: {{
                booleans: ["AutoOpenScroll", "TeleportToEgg"],
                strings:  ["SelectedScroll"],
                numbers:  [],
            }},
            PlayerTab: {{
                booleans: ["AutoClick", "AutoClickAnimation", "AutoAscension", "AutoRewards", "AutoAchievments", "AutoChests"],
                strings:  [],
                numbers:  [],
            }},
            GachaTab: {{
                booleans: ["AutoGacha"],
                strings:  ["SelectedGacha"],
                numbers:  ["GachaDelay"],
            }},
            GamemodesTab: {{
                booleans: ["AutoJoinPublicGamemode", "AutoJoinSelectedGamemode", "AutoCreateGamemode", "AutoLeaveGamemode", "AutoFarmMobs", "AutoEquipBest", "AutoEquipTitle"],
                strings:  ["SelectedPriority", "SelectedRaid", "SelectedDungeon", "SelectedInfinityCastle", "SelectedDefenseMode", "SelectedEasterRaid", "SelectedRaidDifficulty", "SelectedDungeonDifficulty", "SelectedInfinityCastleDifficulty", "SelectedDefenseModeDifficulty", "SelectedEasterRaidDifficulty", "SelectedEquipBestInMode", "SelectedEquipBestNoMode", "SelectedEquipTitleInMode", "SelectedEquipTitleNoMode"],
                numbers:  ["RaidToLeave", "DungeonToLeave", "InfinityCastleToLeave", "DefenseToLeave", "EasterRaidToLeave", "WorldToTeleport"],
            }},
            ExchangeTab: {{
                booleans: ["Potions.AutoPotions"],
                strings:  [],
                numbers:  [],
            }},
            PotionsTab: {{
                booleans: ["AutoPausePotions", "AutoUnPausePotions", "AutoUsePotions"],
                strings:  [],
                numbers:  ["IntervalToUse"],
            }},
        }}

        let openPlayers = new Set()

        function isOnline(lastSeen) {{
            return (Date.now() / 1000 - lastSeen) < 15
        }}

        function getVal(settings, tab, key) {{
            const parts = key.split(".")
            let val = settings?.[tab]
            for (const p of parts) val = val?.[p]
            return val ?? null
        }}

        function setVal(payload, tab, key, value) {{
            const parts = key.split(".")
            if (parts.length === 1) {{
                payload[tab][key] = value
            }} else {{
                if (!payload[tab][parts[0]]) payload[tab][parts[0]] = {{}}
                payload[tab][parts[0]][parts[1]] = value
            }}
        }}

        function buildTabCard(userId, tab, tabDef, settings) {{
            const rows = []

            for (const key of (tabDef.booleans ?? [])) {{
                const val = getVal(settings, tab, key) ?? false
                rows.push(`
                    <div class="row">
                        <span>${{key}}</span>
                        <label class="toggle">
                            <input type="checkbox" id="${{userId}}_${{tab}}_${{key}}" ${{val ? "checked" : ""}} onchange="markDirty(this)">
                            <span class="slider"></span>
                        </label>
                    </div>`)
            }}

            for (const key of (tabDef.numbers ?? [])) {{
                const val = getVal(settings, tab, key) ?? 0
                rows.push(`
                    <div class="row">
                        <span>${{key}}</span>
                        <input type="number" class="input-num" id="${{userId}}_${{tab}}_${{key}}" value="${{val}}" step="0.1" onchange="markDirty(this)">
                    </div>`)
            }}

            for (const key of (tabDef.strings ?? [])) {{
                const val = getVal(settings, tab, key) ?? ""
                rows.push(`
                    <div class="row">
                        <span>${{key}}</span>
                        <input type="text" class="input-str" id="${{userId}}_${{tab}}_${{key}}" value="${{val}}" onchange="markDirty(this)">
                    </div>`)
            }}

            return `
                <div class="tab-card">
                    <h3>${{tab.replace("Tab", "")}}</h3>
                    ${{rows.join("")}}
                </div>`
        }}

        function buildPlayerBody(userId, player) {
            const settings = player.settings ?? {}
            const cards = Object.entries(TABS).map(([tab, tabDef]) =>
                buildTabCard(userId, tab, tabDef, settings)
            ).join("")
            return `
                <div class="tabs-grid">${cards}</div>
                <div style="display:flex;gap:10px;margin-top:16px">
                    <button class="save-btn" onclick="savePlayer('${userId}')">💾 Aplicar no player</button>
                    <button class="save-btn" style="background:#ef4444" onclick="kickPlayer('${userId}')">👢 Kick</button>
                </div>`
        }

        function markDirty(el) {{
            el.dataset.dirty = "1"
        }}

        async function savePlayer(userId) {{
            const payload = {{}}
            for (const [tab, tabDef] of Object.entries(TABS)) {{
                payload[tab] = {{}}
                for (const key of (tabDef.booleans ?? [])) {{
                    const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                    if (el) {{ setVal(payload, tab, key, el.checked); delete el.dataset.dirty }}
                }}
                for (const key of (tabDef.numbers ?? [])) {{
                    const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                    if (el) {{ setVal(payload, tab, key, Number(el.value)); delete el.dataset.dirty }}
                }}
                for (const key of (tabDef.strings ?? [])) {{
                    const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                    if (el) {{ setVal(payload, tab, key, el.value); delete el.dataset.dirty }}
                }}
            }}

            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify(payload)
            }})

            showToast("✅ Override enviado!")
        }}

        async function loadPlayers() {{
            try {{
                const res = await fetch(`/control/players?password=${{PASSWORD}}`)
                const data = await res.json()
                renderPlayers(data)
            }} catch(e) {{
                console.error("Erro ao carregar players:", e)
            }}
        }}

        function renderPlayers(data) {{
            const list = document.getElementById("players-list")
            const entries = Object.entries(data)

            document.getElementById("player-count").textContent =
                `${{entries.length}} player${{entries.length !== 1 ? "s" : ""}}`

            if (entries.length === 0) {{
                list.innerHTML = '<div class="no-players">Nenhum player ativo ainda.</div>'
                return
            }}

            // Remove cards de players que saíram
            list.querySelectorAll(".player-card").forEach(card => {{
                const uid = card.id.replace("card-", "")
                if (!data[uid]) card.remove()
            }})

            entries.forEach(([userId, player]) => {{
                const online   = isOnline(player.info?.lastSeen ?? 0)
                const lastSeen = player.info?.lastSeen
                    ? new Date(player.info.lastSeen * 1000).toLocaleTimeString("pt-BR")
                    : "?"
                const statusHtml = `<span class="${{online ? "online" : "offline"}}">${{online ? "● online" : "● offline"}}</span> · último report: ${{lastSeen}}`

                const existing = document.getElementById(`card-${{userId}}`)

                if (existing) {{
                    existing.querySelector(".player-meta").innerHTML = statusHtml

                    // Atualiza só campos não sujos
                    for (const [tab, tabDef] of Object.entries(TABS)) {{
                        for (const key of [...(tabDef.booleans ?? []), ...(tabDef.numbers ?? []), ...(tabDef.strings ?? [])]) {{
                            const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                            if (el && !el.dataset.dirty) {{
                                const val = getVal(player.settings ?? {{}}, tab, key)
                                if (el.type === "checkbox") el.checked = val ?? false
                                else el.value = val ?? ""
                            }}
                        }}
                    }}
                }} else {{
                    const isOpen = openPlayers.has(userId)
                    const card   = document.createElement("div")
                    card.className = "player-card"
                    card.id = `card-${{userId}}`
                    card.innerHTML = `
                        <div class="player-header" onclick="togglePlayer('${{userId}}')">
                            <div>
                                <div class="player-name">${{player.info?.username ?? userId}}</div>
                                <div class="player-meta">${{statusHtml}}</div>
                            </div>
                            <div style="color:#555;font-size:12px">ID: ${{userId}}</div>
                        </div>
                        <div class="player-body ${{isOpen ? "open" : ""}}" id="body-${{userId}}">
                            ${{buildPlayerBody(userId, player)}}
                        </div>`
                    list.appendChild(card)
                }}
            }})
        }}

        function togglePlayer(userId) {{
            const body = document.getElementById(`body-${{userId}}`)
            body.classList.toggle("open")
            if (body.classList.contains("open")) openPlayers.add(userId)
            else openPlayers.delete(userId)
        }}

        function showToast(msg) {{
            const t = document.getElementById("toast")
            t.textContent = msg
            t.style.display = "block"
            setTimeout(() => t.style.display = "none", 3000)
        }}

        loadPlayers()
        setInterval(loadPlayers, 3000)
    </script>
</body>
</html>'''

@app.route("/")
def index():
    return "404 Not Found", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
