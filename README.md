# ScriptServer

Proxy servidor que busca os scripts do seu repositório privado no GitHub e os serve com autenticação por token.

## Fluxo

```
Executor → Railway (valida SCRIPT_TOKEN) → GitHub privado (usa GITHUB_TOKEN) → retorna o script
```

## Estrutura esperada no repositório GitHub

```
AnimeGhostBuild/
  Main.lua
  Systems/
    State.lua
  Core/
    Utils.lua
    Player.lua
    Rewards.lua
    Farm.lua
    Gamemode.lua
    Gacha.lua
```

## Variáveis de ambiente (configurar no Railway/Render)

| Variável       | Descrição                                              |
|----------------|--------------------------------------------------------|
| SCRIPT_TOKEN   | Token que o executor vai enviar pra autenticar         |
| GITHUB_TOKEN   | Personal Access Token do GitHub (com permissão repo)   |
| GITHUB_USER    | Seu usuário do GitHub                                  |
| GITHUB_REPO    | Nome do repositório privado                            |
| GITHUB_BRANCH  | Branch dos arquivos (padrão: main)                     |

## Como gerar o GITHUB_TOKEN (PAT)

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Marque apenas a permissão `repo` (acesso a repositórios privados)
4. Copie o token gerado e cole na variável GITHUB_TOKEN do Railway/Render

## Deploy no Railway

1. Crie uma conta em railway.app
2. New Project → Deploy from GitHub repo (pode ser um repo público só com o servidor)
3. Vá em Variables e adicione todas as variáveis acima
4. O Railway detecta o Procfile automaticamente e já sobe

## Deploy no Render

1. Crie uma conta em render.com
2. New → Web Service → conecta o GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn server:app`
5. Em Environment, adicione todas as variáveis acima

## URLs disponíveis

```
https://seu-app.railway.app/script/main?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/state?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/utils?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/player?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/rewards?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/farm?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/gamemode?token=SEU_SCRIPT_TOKEN
https://seu-app.railway.app/script/gacha?token=SEU_SCRIPT_TOKEN
```

## Como usar no Main.lua

```lua
local BASE_URL    = "https://seu-app.railway.app/script"
local SCRIPT_TOKEN = "SEU_SCRIPT_TOKEN"

local URLS = {
    State    = BASE_URL .. "/state?token="    .. SCRIPT_TOKEN,
    Utils    = BASE_URL .. "/utils?token="    .. SCRIPT_TOKEN,
    Player   = BASE_URL .. "/player?token="   .. SCRIPT_TOKEN,
    Rewards  = BASE_URL .. "/rewards?token="  .. SCRIPT_TOKEN,
    Farm     = BASE_URL .. "/farm?token="     .. SCRIPT_TOKEN,
    Gamemode = BASE_URL .. "/gamemode?token=" .. SCRIPT_TOKEN,
    Gacha    = BASE_URL .. "/gacha?token="    .. SCRIPT_TOKEN,
}
```

## Como atualizar os scripts

Só commitar as mudanças no repositório privado do GitHub.
O servidor sempre busca a versão mais recente a cada request, sem precisar de redeploy.
