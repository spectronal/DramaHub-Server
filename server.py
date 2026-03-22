# server.py

from flask import Flask, request, abort
import os
import requests

app = Flask(__name__)

SCRIPT_TOKEN  = os.environ.get("SCRIPT_TOKEN", "my_token")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER   = os.environ.get("GITHUB_USER", "MY_USERNAME")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "MY_REPO")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

BASE_PATH = "AnimeGhostBuild"

SCRIPTS = {
    # Core
    "main":     f"{BASE_PATH}/Main.lua",
    "state":    f"{BASE_PATH}/Systems/State.lua",
    "utils":    f"{BASE_PATH}/Core/Utils.lua",
    "player":   f"{BASE_PATH}/Core/Player.lua",
    "rewards":  f"{BASE_PATH}/Core/Rewards.lua",
    "farm":     f"{BASE_PATH}/Core/Farm.lua",
    "gamemode": f"{BASE_PATH}/Core/Gamemode.lua",
    "gacha":    f"{BASE_PATH}/Core/Gacha.lua",
    "scrolls":  f"{BASE_PATH}/Core/Scrolls.lua",
    "exchange":    f"{BASE_PATH}/Core/Exchange.lua",
    # UI
    "ui-about":    f"{BASE_PATH}/UI/About.lua",
    "ui-farm":     f"{BASE_PATH}/UI/Farm.lua",
    "ui-player":   f"{BASE_PATH}/UI/Player.lua",
    "ui-gamemode": f"{BASE_PATH}/UI/Gamemode.lua",
    "ui-scroll":   f"{BASE_PATH}/UI/Scroll.lua",
    "ui-exchange":   f"{BASE_PATH}/UI/Exchange.lua",
    "ui-gacha":    f"{BASE_PATH}/UI/Gacha.lua",
}

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

@app.route("/init")
def serve_init():
    content = fetch_from_github("init.lua")
    return content, 200, {"Content-Type": "text/plain"}

@app.route("/script/<name>")
def serve_script(name):
    validate_token()
    file_path = SCRIPTS.get(name)
    if not file_path:
        abort(404)
    content = fetch_from_github(file_path)
    return content, 200, {"Content-Type": "text/plain"}

@app.route("/")
def index():
    return "404 Not Found", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
