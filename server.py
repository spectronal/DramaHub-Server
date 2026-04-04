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
LOGO_URL       = "https://media.discordapp.net/attachments/1297976903428214868/1489394179242197232/images.png?ex=69d1936b&is=69d041eb&hm=4ca3ff2be4198c96bff764d6e62dfea9b1644d89fb606dd3c60113aeee37339c&=&format=webp&quality=lossless"

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

def get_roblox_avatar(user_id):
    try:
        res = requests.get(
            f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png",
            timeout=3
        )
        return res.json()["data"][0]["imageUrl"]
    except:
        return None

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

    count  = increment_exec(user_id)
    ts     = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())
    avatar = get_roblox_avatar(user_id)

    log = {
        "type": "execution", "userId": user_id,
        "username": username, "count": count, "ts": ts,
    }
    push_log(log)

    embed = {
        "title": "Script Executed",
        "color": 0x22c55e,
        "thumbnail": {"url": LOGO_URL},
        "fields": [
            {"name": "Player",     "value": f"{username} (`{user_id}`)", "inline": True},
            {"name": "Executions", "value": str(count),                  "inline": True},
            {"name": "Timestamp",  "value": ts,                          "inline": True},
        ]
    }
    if avatar:
        embed["author"] = {"name": username, "icon_url": avatar}
    send_webhook([embed])

    return json.dumps({"ok": True, "count": count}), 200, {"Content-Type": "application/json"}

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
        "username":  username,
        "lastSeen":  time.time(),
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
    avatar   = get_roblox_avatar(user_id)

    if user_id not in players_state:
        players_state[user_id] = {"settings": {}, "override": {}, "info": {}}

    for tab, settings in data.items():
        if tab == "_control":
            ctrl   = settings
            action = "Kick" if ctrl.get("Kick") else "Refresh" if ctrl.get("Refresh") else "Message" if ctrl.get("mSender") else "Control"
            reason = ctrl.get("KickReason", "") or ctrl.get("sMessage", "")

            log = {
                "type": "control", "action": action,
                "userId": user_id, "username": username,
                "reason": reason, "ts": ts,
            }
            push_log(log)

            embed = {
                "title": f"Control Action: {action}",
                "color": 0xef4444 if action == "Kick" else 0x3b82f6 if action == "Refresh" else 0x22c55e,
                "thumbnail": {"url": LOGO_URL},
                "fields": [
                    {"name": "Player",    "value": f"{username} (`{user_id}`)", "inline": True},
                    {"name": "Action",    "value": action,                      "inline": True},
                    {"name": "Detail",    "value": reason or "—",               "inline": True},
                    {"name": "Timestamp", "value": ts,                          "inline": False},
                ]
            }
            if avatar:
                embed["author"] = {"name": username, "icon_url": avatar}
            send_webhook([embed])

        elif isinstance(settings, dict):
            current = players_state[user_id]["settings"].get(tab, {})
            changed = {k: v for k, v in settings.items() if current.get(k) != v}

            if changed:
                changes = ", ".join(f"{k}={v}" for k, v in changed.items())
                log = {
                    "type": "override", "userId": user_id,
                    "username": username, "tab": tab,
                    "changes": changes, "ts": ts,
                }
                push_log(log)

                embed = {
                    "title": "Override Applied",
                    "color": 0xa855f7,
                    "thumbnail": {"url": LOGO_URL},
                    "fields": [
                        {"name": "Player",    "value": f"{username} (`{user_id}`)", "inline": True},
                        {"name": "Tab",       "value": tab,                         "inline": True},
                        {"name": "Changes",   "value": changes,                     "inline": False},
                        {"name": "Timestamp", "value": ts,                          "inline": False},
                    ]
                }
                if avatar:
                    embed["author"] = {"name": username, "icon_url": avatar}
                send_webhook([embed])

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

@app.route("/script/admpanel")
def admpanel():
    validate_password()
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DramaHub Admin</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --bg:      #060606;
            --bg2:     #0e0e0e;
            --bg3:     #141414;
            --border:  #1c1c1c;
            --red:     #dc2626;
            --red2:    #ef4444;
            --red-dim: #7f1d1d;
            --text:    #e5e5e5;
            --muted:   #444;
        }}
        body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }}

        .topbar {{
            background: linear-gradient(90deg, #0a0303 0%, #110505 40%, #0a0303 100%);
            border-bottom: 1px solid #1a0505;
            padding: 12px 28px;
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .topbar img {{ width: 34px; height: 34px; border-radius: 6px; object-fit: cover; }}
        .topbar-title {{
            font-size: 15px; font-weight: 700; letter-spacing: 2px;
            background: linear-gradient(90deg, #dc2626, #f87171);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .topbar-sub {{ font-size: 11px; color: var(--muted); letter-spacing: .5px; }}
        .topbar-right {{ margin-left: auto; display: flex; align-items: center; gap: 16px; font-size: 11px; color: var(--muted); }}
        .dot {{ display: inline-block; width: 6px; height: 6px; background: #22c55e; border-radius: 50%; margin-right: 5px; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.3; }} }}

        .nav {{ display: flex; padding: 0 28px; background: var(--bg2); border-bottom: 1px solid var(--border); }}
        .nav-btn {{
            padding: 11px 20px; background: none; border: none; color: var(--muted);
            cursor: pointer; font-size: 12px; font-weight: 600;
            border-bottom: 2px solid transparent; transition: .2s;
            letter-spacing: .5px; text-transform: uppercase;
        }}
        .nav-btn.active {{ color: var(--red2); border-bottom-color: var(--red); }}
        .nav-btn:hover {{ color: #aaa; }}

        .page {{ display: none; padding: 20px 28px; }}
        .page.active {{ display: block; }}

        .status-bar {{
            margin-bottom: 16px; padding: 8px 14px;
            background: var(--bg2); border-radius: 6px;
            font-size: 11px; color: var(--muted);
            border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
        }}

        .players-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .player-card {{
            background: var(--bg2); border: 1px solid var(--border);
            border-radius: 8px; overflow: hidden; transition: border-color .2s;
        }}
        .player-card:hover {{ border-color: #2a0808; }}
        .player-header {{
            padding: 12px 18px; display: flex;
            justify-content: space-between; align-items: center;
            cursor: pointer; user-select: none;
        }}
        .player-header:hover {{ background: #111; }}
        .player-name {{ font-size: 13px; font-weight: 700; color: var(--red2); letter-spacing: .3px; }}
        .player-meta {{ font-size: 10px; color: var(--muted); margin-top: 3px; }}
        .player-id {{ font-size: 10px; color: #2a2a2a; font-family: monospace; }}
        .player-body {{ padding: 16px 18px; display: none; border-top: 1px solid var(--border); }}
        .player-body.open {{ display: block; }}

        .tabs-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
            gap: 10px;
        }}
        .tab-card {{
            background: var(--bg3); border: 1px solid var(--border);
            border-radius: 7px; padding: 12px;
            max-height: 280px; overflow-y: auto;
        }}
        .tab-card::-webkit-scrollbar {{ width: 3px; }}
        .tab-card::-webkit-scrollbar-thumb {{ background: var(--red-dim); border-radius: 3px; }}
        .tab-card h3 {{
            font-size: 9px; color: var(--red); text-transform: uppercase;
            letter-spacing: 1.5px; margin-bottom: 8px;
            position: sticky; top: 0; background: var(--bg3);
            padding-bottom: 6px; border-bottom: 1px solid var(--border);
        }}
        .row {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 5px 0; border-bottom: 1px solid #0f0f0f; gap: 8px;
        }}
        .row:last-child {{ border-bottom: none; }}
        .row span {{ font-size: 10px; color: #888; flex: 1; }}

        .toggle {{ position: relative; width: 32px; height: 17px; flex-shrink: 0; }}
        .toggle input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{
            position: absolute; cursor: pointer; inset: 0;
            background: #1a1a1a; border-radius: 17px; transition: .3s;
            border: 1px solid #222;
        }}
        .slider:before {{
            content: ""; position: absolute; width: 11px; height: 11px;
            left: 2px; bottom: 2px; background: #333;
            border-radius: 50%; transition: .3s;
        }}
        input:checked + .slider {{ background: #3f0000; border-color: var(--red-dim); }}
        input:checked + .slider:before {{ background: var(--red2); transform: translateX(15px); }}

        .input-num, .input-str {{
            background: #0a0a0a; border: 1px solid #1a1a1a; color: #ccc;
            border-radius: 4px; padding: 3px 6px; font-size: 10px;
        }}
        .input-num {{ width: 65px; }}
        .input-str {{ width: 100px; }}
        .input-num:focus, .input-str:focus {{ border-color: var(--red-dim); outline: none; }}

        .action-bar {{ display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }}
        .btn {{
            padding: 7px 14px; border: none; border-radius: 5px;
            cursor: pointer; font-size: 11px; font-weight: 700;
            letter-spacing: .5px; text-transform: uppercase;
            transition: filter .2s;
        }}
        .btn:hover {{ filter: brightness(1.3); }}
        .btn-apply   {{ background: linear-gradient(135deg, #7f1d1d, #dc2626); color: #fff; }}
        .btn-refresh {{ background: #0f1e33; color: #60a5fa; border: 1px solid #1e3a5f; }}
        .btn-kick    {{ background: #0f0505; color: var(--red2); border: 1px solid var(--red-dim); }}
        .btn-msg     {{ background: #0a140a; color: #4ade80; border: 1px solid #14532d; }}

        .online  {{ color: #22c55e; }}
        .offline {{ color: #3a1a1a; }}
        .exec-badge {{
            background: #0f0505; border: 1px solid #1a0808;
            border-radius: 4px; padding: 1px 6px;
            font-size: 10px; color: var(--red2); font-family: monospace;
        }}

        .logs-container {{
            background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
        }}
        .logs-toolbar {{
            padding: 9px 14px; border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
        }}
        .logs-toolbar span {{ font-size: 11px; color: var(--muted); }}
        .clear-btn {{
            padding: 4px 10px; background: #0f0505; border: 1px solid var(--red-dim);
            color: var(--red2); border-radius: 4px; cursor: pointer; font-size: 10px;
            font-weight: 700; text-transform: uppercase; letter-spacing: .5px;
        }}
        .logs-scroll {{ max-height: 600px; overflow-y: auto; }}
        .log-entry {{
            padding: 8px 14px; border-bottom: 1px solid #0f0f0f;
            font-size: 11px; display: flex; gap: 10px; align-items: flex-start;
        }}
        .log-entry:last-child {{ border-bottom: none; }}
        .log-badge {{
            padding: 1px 6px; border-radius: 3px; font-size: 9px;
            font-weight: 700; white-space: nowrap; flex-shrink: 0;
            letter-spacing: .5px; text-transform: uppercase;
        }}
        .badge-execution {{ background: #14532d; color: #4ade80; }}
        .badge-override  {{ background: #1e1b4b; color: #818cf8; }}
        .badge-control   {{ background: var(--red-dim); color: var(--red2); }}
        .badge-refresh   {{ background: #1e3a5f; color: #60a5fa; }}
        .badge-message   {{ background: #0f2a0f; color: #4ade80; }}
        .log-body {{ flex: 1; color: #666; line-height: 1.5; }}
        .log-body b {{ color: #aaa; }}
        .log-ts {{ color: #222; font-size: 10px; white-space: nowrap; font-family: monospace; }}

        .no-players {{ color: #1e1e1e; font-size: 12px; padding: 60px; text-align: center; letter-spacing: 1px; }}

        #toast {{
            position: fixed; bottom: 20px; right: 20px;
            background: linear-gradient(135deg, #7f1d1d, #dc2626);
            color: #fff; padding: 10px 16px; border-radius: 6px;
            font-size: 12px; font-weight: 600; display: none;
            box-shadow: 0 4px 20px rgba(220,38,38,.4); z-index: 999;
            letter-spacing: .3px;
        }}
    </style>
</head>
<body>
    <div class="topbar">
        <img src="{LOGO_URL}" alt="logo">
        <div>
            <div class="topbar-title">DRAMAHUB</div>
            <div class="topbar-sub">Admin Panel</div>
        </div>
        <div class="topbar-right">
            <span><span class="dot"></span>Live</span>
            <span id="player-count">0 players</span>
        </div>
    </div>

    <div class="nav">
        <button class="nav-btn active" onclick="switchTab(event,'players')">Players</button>
        <button class="nav-btn" onclick="switchTab(event,'logs')">Logs</button>
    </div>

    <div id="page-players" class="page active">
        <div class="status-bar">
            <span><span class="dot"></span>Connected players</span>
            <span id="player-count2">0 players</span>
        </div>
        <div class="players-list" id="players-list">
            <div class="no-players">NO ACTIVE PLAYERS</div>
        </div>
    </div>

    <div id="page-logs" class="page">
        <div class="logs-container">
            <div class="logs-toolbar">
                <span id="log-count">0 entries</span>
                <button class="clear-btn" onclick="clearLogs()">Clear View</button>
            </div>
            <div class="logs-scroll" id="logs-list"></div>
        </div>
    </div>

    <div id="toast"></div>

    <script>
        const PASSWORD = "{ADMIN_PASSWORD}"
        let openPlayers = new Set()
        let latestData  = {{}}

        function switchTab(e, tab) {{
            document.querySelectorAll(".page").forEach(p => p.classList.remove("active"))
            document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"))
            document.getElementById(`page-${{tab}}`).classList.add("active")
            e.target.classList.add("active")
        }}

        function isOnline(lastSeen) {{ return (Date.now() / 1000 - lastSeen) < 15 }}
        function markDirty(el) {{ el.dataset.dirty = "1" }}

        function buildTabCard(userId, tab, settings) {{
            const tabData = settings[tab]
            if (!tabData || typeof tabData !== "object") return ""
            const rows = []
            for (const [key, val] of Object.entries(tabData)) {{
                if (Array.isArray(val) || (typeof val === "object" && val !== null)) continue
                const id = `${{userId}}_${{tab}}_${{key}}`
                if (typeof val === "boolean") {{
                    rows.push(`<div class="row"><span>${{key}}</span><label class="toggle"><input type="checkbox" id="${{id}}" ${{val ? "checked" : ""}} onchange="markDirty(this)"><span class="slider"></span></label></div>`)
                }} else if (typeof val === "number") {{
                    rows.push(`<div class="row"><span>${{key}}</span><input type="number" class="input-num" id="${{id}}" value="${{val}}" step="0.1" onchange="markDirty(this)"></div>`)
                }} else if (typeof val === "string") {{
                    rows.push(`<div class="row"><span>${{key}}</span><input type="text" class="input-str" id="${{id}}" value="${{val}}" onchange="markDirty(this)"></div>`)
                }}
            }}
            if (rows.length === 0) return ""
            return `<div class="tab-card"><h3>${{tab.replace("Tab","")}}</h3>${{rows.join("")}}</div>`
        }}

        function buildPlayerBody(userId, player) {{
            const settings = player.settings ?? {{}}
            const cards = Object.keys(settings)
                .filter(tab => tab !== "Roles")
                .map(tab => buildTabCard(userId, tab, settings))
                .filter(c => c !== "").join("")
            return `
                <div class="tabs-grid">${{cards}}</div>
                <div class="action-bar">
                    <button class="btn btn-apply"   onclick="savePlayer('${{userId}}')">Apply Changes</button>
                    <button class="btn btn-refresh" onclick="refreshPlayer('${{userId}}')">Refresh Script</button>
                    <button class="btn btn-kick"    onclick="kickPlayer('${{userId}}')">Kick Player</button>
                    <button class="btn btn-msg"     onclick="sendMessage('${{userId}}')">Send Message</button>
                </div>`
        }}

        async function savePlayer(userId) {{
            const player   = latestData[userId]
            if (!player) return
            const settings = player.settings ?? {{}}
            const payload  = {{}}
            for (const tab of Object.keys(settings)) {{
                if (tab === "Roles") continue
                const tabData = settings[tab]
                if (!tabData || typeof tabData !== "object") continue
                payload[tab] = {{}}
                for (const [key, val] of Object.entries(tabData)) {{
                    if (Array.isArray(val) || (typeof val === "object" && val !== null)) continue
                    const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                    if (!el) continue
                    if (el.type === "checkbox") payload[tab][key] = el.checked
                    else if (el.type === "number") payload[tab][key] = Number(el.value)
                    else payload[tab][key] = el.value
                    delete el.dataset.dirty
                }}
            }}
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST", headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify(payload)
            }})
            showToast("Override sent!")
        }}

        async function kickPlayer(userId) {{
            const reason = prompt("Kick reason:") ?? "Removed by administrator."
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST", headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{ _control: {{ Kick: true, KickReason: reason }} }})
            }})
            showToast("Kick sent!")
        }}

        async function refreshPlayer(userId) {{
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST", headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{ _control: {{ Refresh: true }} }})
            }})
            showToast("Refresh sent!")
        }}

        async function sendMessage(userId) {{
            const msg = prompt("Message:")
            if (!msg) return
            await fetch(`/control/override/${{userId}}?password=${{PASSWORD}}`, {{
                method: "POST", headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{ _control: {{ mSender: true, sMessage: msg }} }})
            }})
            showToast("Message sent!")
        }}

        async function loadPlayers() {{
            try {{
                const res = await fetch(`/control/players?password=${{PASSWORD}}`)
                latestData = await res.json()
                renderPlayers(latestData)
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
            const count   = `${{entries.length}} player${{entries.length !== 1 ? "s" : ""}}`
            document.getElementById("player-count").textContent  = count
            document.getElementById("player-count2").textContent = count

            if (entries.length === 0) {{
                list.innerHTML = '<div class="no-players">NO ACTIVE PLAYERS</div>'
                return
            }}

            list.querySelectorAll(".player-card").forEach(card => {{
                if (!data[card.id.replace("card-","")]) card.remove()
            }})

            entries.forEach(([userId, player]) => {{
                const online    = isOnline(player.info?.lastSeen ?? 0)
                const lastSeen  = player.info?.lastSeen
                    ? new Date(player.info.lastSeen * 1000).toLocaleTimeString("en-US") : "?"
                const execCount = player.info?.execCount ?? 0
                const statusHtml = `
                    <span class="${{online ? "online" : "offline"}}">${{online ? "online" : "offline"}}</span>
                    &nbsp;·&nbsp;${{lastSeen}}
                    &nbsp;·&nbsp;<span class="exec-badge">${{execCount}}x</span>`

                const existing = document.getElementById(`card-${{userId}}`)
                if (existing) {{
                    existing.querySelector(".player-meta").innerHTML = statusHtml
                    const settings = player.settings ?? {{}}
                    for (const tab of Object.keys(settings)) {{
                        const tabData = settings[tab]
                        if (!tabData || typeof tabData !== "object") continue
                        for (const [key, val] of Object.entries(tabData)) {{
                            if (Array.isArray(val) || (typeof val === "object" && val !== null)) continue
                            const el = document.getElementById(`${{userId}}_${{tab}}_${{key}}`)
                            if (!el || el.dataset.dirty) continue
                            if (el.type === "checkbox") el.checked = val ?? false
                            else el.value = val ?? ""
                        }}
                    }}
                }} else {{
                    const card = document.createElement("div")
                    card.className = "player-card"
                    card.id = `card-${{userId}}`
                    card.innerHTML = `
                        <div class="player-header" onclick="togglePlayer('${{userId}}')">
                            <div>
                                <div class="player-name">${{player.info?.username ?? userId}}</div>
                                <div class="player-meta">${{statusHtml}}</div>
                            </div>
                            <div class="player-id">${{userId}}</div>
                        </div>
                        <div class="player-body ${{openPlayers.has(userId) ? "open" : ""}}" id="body-${{userId}}">
                            ${{buildPlayerBody(userId, player)}}
                        </div>`
                    list.appendChild(card)
                }}
            }})
        }}

        function renderLogs(logs) {{
            const container = document.getElementById("logs-list")
            document.getElementById("log-count").textContent = `${{logs.length}} entries`
            container.innerHTML = logs.map(log => {{
                let badge, body
                if (log.type === "execution") {{
                    badge = `<span class="log-badge badge-execution">exec</span>`
                    body  = `<b>${{log.username}}</b> executed the script &middot; run #${{log.count}}`
                }} else if (log.type === "override") {{
                    badge = `<span class="log-badge badge-override">override</span>`
                    body  = `<b>${{log.username}}</b> &middot; ${{log.tab}} &rarr; ${{log.changes}}`
                }} else if (log.type === "control") {{
                    const cls = log.action === "Refresh" ? "badge-refresh" : log.action === "Message" ? "badge-message" : "badge-control"
                    badge = `<span class="log-badge ${{cls}}">${{log.action.toLowerCase()}}</span>`
                    body  = `<b>${{log.username}}</b>${{log.reason ? ` &middot; ${{log.reason}}` : ""}}`
                }}
                return `<div class="log-entry">${{badge}}<div class="log-body">${{body}}</div><div class="log-ts">${{log.ts}}</div></div>`
            }}).join("")
        }}

        function clearLogs() {{
            document.getElementById("logs-list").innerHTML = ""
            document.getElementById("log-count").textContent = "0 entries"
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
            setTimeout(() => t.style.display = "none", 2500)
        }}

        loadPlayers(); loadLogs()
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
