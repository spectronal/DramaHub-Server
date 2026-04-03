from flask import Flask, request, abort
import os
import requests
import json
import time
import redis

app = Flask(__name__)

SCRIPT_TOKEN   = os.environ.get("SCRIPT_TOKEN", "my_token")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER    = os.environ.get("GITHUB_USER", "MY_USERNAME")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "MY_REPO")
GITHUB_BRANCH  = os.environ.get("GITHUB_BRANCH", "main")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "spectronal")
REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379")
LOG_WEBHOOK    = os.environ.get("LOG_WEBHOOK", "")

r = redis.from_url(REDIS_URL, decode_responses=True)

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

players_state = {}

# ── Helpers ───────────────────────────────────────────────────────────────────

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

def get_exec_count(user_id):
    val = r.get(f"exec:{user_id}")
    return int(val) if val else 0

def increment_exec(user_id):
    return r.incr(f"exec:{user_id}")

def push_log(entry):
    r.lpush("logs:global", json.dumps(entry))
    r.ltrim("logs:global", 0, 199)

def get_logs():
    raw = r.lrange("logs:global", 0, -1)
    return [json.loads(x) for x in raw]

def send_webhook(embeds):
    if not LOG_WEBHOOK:
        return
    try:
        requests.post(LOG_WEBHOOK, json={"embeds": embeds}, timeout=5)
    except:
        pass

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

# ── Execution Counter ─────────────────────────────────────────────────────────

@app.route("/control/execution", methods=["POST"])
def register_execution():
    validate_token()
    data = request.get_json()
    if not data:
        abort(400)

    user_id  = str(data.get("userId"))
    username = data.get("username", "Unknown")

    if not user_id:
        abort(400)

    count = increment_exec(user_id)
    ts    = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())

    log = {
        "type":     "execution",
        "userId":   user_id,
        "username": username,
        "count":    count,
        "ts":       ts,
    }
    push_log(log)

    send_webhook([{
        "title":       "🚀 Drama Hub executed!",
        "color":       0x22c55e,
        "thumbnail": {
            "url": "https://media.discordapp.net/attachments/1297976903428214868/1489394179242197232/images.png?ex=69d041eb&is=69cef06b&hm=910c300fedfb9fb0453c4d0694f86224a5649357df99908b7b4249fe1e7f39f0&=&format=webp&quality=lossless"
        },
        "fields": [
            {"name": "Player",     "value": f"{username} (`{user_id}`)", "inline": True},
            {"name": "Executions",  "value": str(count),                  "inline": True},
            {"name": "Timestamp",    "value": ts,                          "inline": True},
        ]
    }])

    return json.dumps({"ok": True, "count": count}), 200, {"Content-Type": "application/json"}

# ── Control Endpoints ─────────────────────────────────────────────────────────

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
        "lastSeen": time.time(),
        "execCount": get_exec_count(user_id),
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

    username = players_state.get(user_id, {}).get("info", {}).get("username", "Unknown")
    ts       = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())

    if user_id not in players_state:
        players_state[user_id] = {"settings": {}, "override": {}, "info": {}}

    # Log e webhook por cada alteração
    for tab, settings in data.items():
        if tab == "_control":
            ctrl = settings
            action = "Kick" if ctrl.get("Kick") else "Refresh" if ctrl.get("Refresh") else "Message" if ctrl.get("mSender") else "Control"
            reason = ctrl.get("KickReason", "")

            log = {
                "type":     "control",
                "action":   action,
                "userId":   user_id,
                "username": username,
                "reason":   reason,
                "ts":       ts,
            }
            push_log(log)

            send_webhook([{
                "title": f"⚡ Control Action: {action}",
                "color": 0xef4444 if action == "Kick" else 0x3b82f6,
                "thumbnail": {
                    "url": "https://media.discordapp.net/attachments/1297976903428214868/1489394179242197232/images.png?ex=69d041eb&is=69cef06b&hm=910c300fedfb9fb0453c4d0694f86224a5649357df99908b7b4249fe1e7f39f0&=&format=webp&quality=lossless"
                },
                "fields": [
                    {"name": "Player",  "value": f"{username} (`{user_id}`)", "inline": True},
                    {"name": "Action",    "value": action,                      "inline": True},
                    {"name": "Reason",  "value": reason or "—",               "inline": True},
                    {"name": "Timestamp", "value": ts,                          "inline": False},
                ]
            }])
        elif isinstance(settings, dict):
            changes = ", ".join(f"{k}={v}" for k, v in settings.items())
            log = {
                "type":     "override",
                "userId":   user_id,
                "username": username,
                "tab":      tab,
                "changes":  changes,
                "ts":       ts,
            }
            push_log(log)

            send_webhook([{
                "title": "⚙️ Override Applied",
                "color": 0xa855f7,
                "thumbnail": {
                    "url": "https://media.discordapp.net/attachments/1297976903428214868/1489394179242197232/images.png?ex=69d041eb&is=69cef06b&hm=910c300fedfb9fb0453c4d0694f86224a5649357df99908b7b4249fe1e7f39f0&=&format=webp&quality=lossless"
                },
                "fields": [
                    {"name": "Player",    "value": f"{username} (`{user_id}`)", "inline": True},
                    {"name": "Tab",       "value": tab,                         "inline": True},
                    {"name": "Changes","value": changes,                     "inline": False},
                    {"name": "Timestamp",   "value": ts,                          "inline": False},
                ]
            }])

        if tab not in players_state[user_id]["override"]:
            players_state[user_id]["override"][tab] = {}
        if isinstance(settings, dict):
            players_state[user_id]["override"][tab].update(settings)

    return json.dumps({"ok": True}), 200, {"Content-Type": "application/json"}

@app.route("/control/players", methods=["GET"])
def get_players():
    validate_password()
    return json.dumps(players_state), 200, {"Content-Type": "application/json"}

@app.route("/control/logs", methods=["GET"])
def get_logs_endpoint():
    validate_password()
    return json.dumps(get_logs()), 200, {"Content-Type": "application/json"}

# ── Admin Panel ───────────────────────────────────────────────────────────────

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
        body {{ background: #0f0f0f; color: #fff; font-family: 'Segoe UI', sans-serif; }}
        .topbar {{ background: #1a1a1a; border-bottom: 1px solid #2a2a2a; padding: 16px 30px; display: flex; justify-content: space-between; align-items: center; }}
        .topbar h1 {{ color: #a855f7; font-size: 20px; }}
        .topbar span {{ color: #555; font-size: 12px; }}
        .nav {{ display: flex; gap: 4px; padding: 20px 30px 0; border-bottom: 1px solid #1a1a1a; }}
        .nav-btn {{ padding: 10px 20px; background: none; border: none; color: #555; cursor: pointer; font-size: 14px; border-bottom: 2px solid transparent; transition: .2s; }}
        .nav-btn.active {{ color: #a855f7; border-bottom-color: #a855f7; }}
        .nav-btn:hover {{ color: #ccc; }}
        .page {{ display: none; padding: 24px 30px; }}
        .page.active {{ display: block; }}
        .status-bar {{ margin-bottom: 20px; padding: 10px 16px; background: #1a1a1a; border-radius: 8px; font-size: 12px; color: #666; border: 1px solid #2a2a2a; display: flex; justify-content: space-between; }}
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
        .save-btn {{ padding: 10px 20px; background: #a855f7; border: none; color: white; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }}
        .save-btn:hover {{ background: #9333ea; }}
        .no-players {{ color: #444; font-size: 14px; padding: 40px; text-align: center; }}
        .log-entry {{ padding: 10px 14px; border-bottom: 1px solid #1a1a1a; font-size: 12px; display: flex; gap: 12px; align-items: flex-start; }}
        .log-entry:last-child {{ border-bottom: none; }}
        .log-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }}
        .badge-execution {{ background: #14532d; color: #22c55e; }}
        .badge-override {{ background: #3b0764; color: #a855f7; }}
        .badge-control {{ background: #7f1d1d; color: #ef4444; }}
        .badge-control-refresh {{ background: #1e3a5f; color: #3b82f6; }}
        .log-body {{ flex: 1; color: #ccc; line-height: 1.5; }}
        .log-ts {{ color: #444; font-size: 11px; white-space: nowrap; }}
        .logs-container {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; overflow: hidden; max-height: 600px; overflow-y: auto; }}
        .logs-toolbar {{ padding: 12px 16px; border-bottom: 1px solid #2a2a2a; display: flex; justify-content: space-between; align-items: center; }}
        .logs-toolbar span {{ font-size: 12px; color: #555; }}
        .clear-btn {{ padding: 6px 14px; background: #333; border: none; color: #ccc; border-radius: 6px; cursor: pointer; font-size: 12px; }}
        .clear-btn:hover {{ background: #444; }}
        #toast {{ position: fixed; bottom: 24px; right: 24px; background: #a855f7; color: white; padding: 12px 20px; border-radius: 8px; font-size: 13px; display: none; box-shadow: 0 4px 20px rgba(168,85,247,.4); z-index: 999; }}
        .online {{ color: #22c55e; }}
        .offline {{ color: #ef4444; }}
        .exec-badge {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 6px; padding: 2px 8px; font-size: 11px; color: #a855f7; }}
    </style>
</head>
<body>
    <div class="topbar">
        <h1>DramaHub Admin Panel</h1>
        <span id="topbar-status"><span class="dot"></span>Auto-refresh a cada 3s</span>
    </div>

    <div class="nav">
        <button class="nav-btn active" onclick="switchTab('players')">👥 Players</button>
        <button class="nav-btn" onclick="switchTab('logs')">📋 Logs</button>
    </div>

    <div id="page-players" class="page active">
        <div class="status-bar">
            <div><span class="dot"></span>Players ativos</div>
            <div id="player-count">0 players</div>
        </div>
        <div class="players-list" id="players-list">
            <div class="no-players">Nenhum player ativo ainda.</div>
        </div>
    </div>

    <div id="page-logs" class="page">
        <div class="logs-container">
            <div class="logs-toolbar">
                <span id="log-count">0 entradas</span>
                <button class="clear-btn" onclick="clearLogs()">🗑 Limpar view</button>
            </div>
            <div id="logs-list"></div>
        </div>
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
                strings:  ["SelectedGamemode", "SelectedPriority", "SelectedRaid", "SelectedDungeon", "SelectedInfinityCastle", "SelectedDefenseMode", "SelectedEasterRaid", "SelectedRaidDifficulty", "SelectedDungeonDifficulty", "SelectedInfinityCastleDifficulty", "SelectedDefenseModeDifficulty", "SelectedEasterRaidDifficulty", "SelectedEquipBestInMode", "SelectedEquipBestNoMode", "SelectedEquipTitleInMode", "SelectedEquipTitleNoMode"],
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
        let currentTab  = "players"

        function switchTab(tab) {{
            currentTab = tab
            document.querySelectorAll(".page").forEach(p => p.classList.remove("active"))
            document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"))
            document.getElementById(`page-${{tab}}`).classList.add("active")
            event.target.classList.add("active")
        }}

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

        function buildPlayerBody(userId, player) {{
            const settings = player.settings ?? {{}}
            const cards = Object.entries(TABS).map(([tab, tabDef]) =>
                buildTabCard(userId, tab, tabDef, settings)
            ).join("")
            return `
                <div class="tabs-grid">${{cards}}</div>
                <div style="display:flex;gap:10px;margin-top:16px">
                    <button class="save-btn" onclick="savePlayer('${{userId}}')">Apply Changes</button>
                    <button class="save-btn" style="background:#3b82f6" onclick="refreshPlayer('${{userId}}')">Refresh Script</button>
                    <button class="save-btn" style="background:#ef4444" onclick="kickPlayer('${{userId}}')">Kick Player</button>
                    <button class="save-btn" style="background:#42f59e" onclick="sendMessage('${{userId}}')">Send Message</button>
                </div>`
        }}

        async function kickPlayer(userId) {{
            const reason = prompt("Motivo do kick:") ?? "Removido pelo administrador."
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ _control: {{ Kick: true, KickReason: reason }} }})
            }})
            showToast("Kick enviado!")
        }}
        
        async function sendMessage(userId) {{
            const admmessage = prompt("Mensagem:") ?? "Oi"
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ _control: {{ mSender: true, sMessage: admmessage }} }})
            }})
            showToast("Mensagem enviada!")
        }}

        async function refreshPlayer(userId) {{
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ _control: {{ Refresh: true }} }})
            }})
            showToast("Refresh enviado!")
        }}

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
                const res  = await fetch(`/control/players?password=${{PASSWORD}}`)
                const data = await res.json()
                renderPlayers(data)
            }} catch(e) {{ console.error(e) }}
        }}

        async function loadLogs() {{
            try {{
                const res  = await fetch(`/control/logs?password=${{PASSWORD}}`)
                const data = await res.json()
                renderLogs(data)
            }} catch(e) {{ console.error(e) }}
        }}

        function renderPlayers(data) {{
            const list    = document.getElementById("players-list")
            const entries = Object.entries(data)

            document.getElementById("player-count").textContent =
                `${{entries.length}} player${{entries.length !== 1 ? "s" : ""}}`

            if (entries.length === 0) {{
                list.innerHTML = '<div class="no-players">Nenhum player ativo ainda.</div>'
                return
            }}

            list.querySelectorAll(".player-card").forEach(card => {{
                const uid = card.id.replace("card-", "")
                if (!data[uid]) card.remove()
            }})

            entries.forEach(([userId, player]) => {{
                const online   = isOnline(player.info?.lastSeen ?? 0)
                const lastSeen = player.info?.lastSeen
                    ? new Date(player.info.lastSeen * 1000).toLocaleTimeString("pt-BR")
                    : "?"
                const execCount  = player.info?.execCount ?? 0
                const statusHtml = `
                    <span class="${{online ? "online" : "offline"}}">${{online ? "● online" : "● offline"}}</span>
                    · último report: ${{lastSeen}}
                    · <span class="exec-badge">🚀 ${{execCount}}x executado</span>`

                const existing = document.getElementById(`card-${{userId}}`)
                if (existing) {{
                    existing.querySelector(".player-meta").innerHTML = statusHtml
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

        function renderLogs(logs) {{
            const container = document.getElementById("logs-list")
            document.getElementById("log-count").textContent = `${{logs.length}} entradas`

            container.innerHTML = logs.map(log => {{
                let badge, body
                if (log.type === "execution") {{
                    badge = `<span class="log-badge badge-execution">EXEC</span>`
                    body  = `<b>${{log.username}}</b> executou o script · execução #${{log.count}}`
                }} else if (log.type === "override") {{
                    badge = `<span class="log-badge badge-override">OVERRIDE</span>`
                    body  = `<b>${{log.username}}</b> · ${{log.tab}} → ${{log.changes}}`
                }} else if (log.type === "control") {{
                    const isRefresh = log.action === "Refresh"
                    badge = `<span class="log-badge ${{isRefresh ? "badge-control-refresh" : "badge-control"}}">${{log.action.toUpperCase()}}</span>`
                    body  = `<b>${{log.username}}</b>${{log.reason ? ` · motivo: ${{log.reason}}` : ""}}`
                }}
                return `
                    <div class="log-entry">
                        ${{badge}}
                        <div class="log-body">${{body}}</div>
                        <div class="log-ts">${{log.ts}}</div>
                    </div>`
            }}).join("")
        }}

        function clearLogs() {{
            document.getElementById("logs-list").innerHTML = ""
            document.getElementById("log-count").textContent = "0 entradas"
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
        loadLogs()
        setInterval(() => {{ loadPlayers(); loadLogs() }}, 3000)
    </script>
</body>
</html>'''

@app.route("/")
def index():
    return "404 Not Found", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
