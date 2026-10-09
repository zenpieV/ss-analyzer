# SS Analyzer

Global-hotkey screenshot snip -> analyzer model -> overlay near cursor + single-file log.

## Install (shipped zip)

1. Extract anywhere, double-click **`SS-Analyzer.bat`**.
2. It checks Python 3.10+ (with download link if missing) and installs
   dependencies once (~150MB).
3. First run opens a **setup wizard**: paste your Gemini API key (required)
   and OpenCode Go key (optional). Each has a Test button. Save & Launch.
4. Tray icon appears. Press **Ctrl+LeftAlt+J** anywhere to snip.
5. Keys can be changed later via tray right-click **Set API keys…**
   (or `python app.py --setup`). Keys live in the local `config.json` only.

- Hotkey: **Ctrl + LeftAlt + J** (left-Alt enforced; right-Alt alone is ignored)
- Providers:
  - **Gemini direct** (free key): `gemini-2.5-flash-lite` default.
  - **OpenCode Go** (Go key): 33 image-input models — MiniMax M3/M2.7/M2.5, Kimi K3/K2.7-Code/K2.6/K2.5,
    GLM 5/5.1/5.2/5.3/5.3-Flash, Qwen3.5-Plus through 3.8-Max, MiMo V2 family,
    DeepSeek V4 Flash Vision, Grok 4.5/4.6/4.7, GPT 6-Luna/5.6-Luna,
    Claude Haiku 5.5, Muse Spark 1.2/1.3.
    Free with image input (all three verified live with image probes):
    LongCat 2.5 Preview Free, Step 5 Preview Free, Space Bunny Free.
  - Go wire protocol is per-model (from the Go docs endpoint table):
    chat/completions ×16, responses ×7, messages ×10. Effort-low mapping:
    `reasoning_effort`/`reasoning.effort=low` on chat+responses (bare retry on 400),
    tight `max_tokens` cap on messages. Every Go request sends a stable
    `x-opencode-session` id (one per app run, for gateway routing/cache) and
    `User-Agent: ss-analyzer/1.0`, as the Go docs require.
- Model switcher: overlay dropdown header + tray right-click **Model** submenu
  (family-separated, exclusive). Switching applies to the next analysis and
  persists to `config.json` (selection fields only — your keys/model list are yours).
- Overlay themes (tray right-click **Theme** submenu ONLY — nothing in the overlay,
  60 total). Classics: Obsidian Glass, Clawd Terminal, YoRHa, stdout, Receipt,
  Brutalist, Miku, Girly-Pop, Overload, Doge, Amogus, 404, Comic Sans, Bug,
  CRT, Blueprint, Noir, Arcade, Zen, Solarized, ADA, Win95, Hologram,
  Field Notes. Fandoms: Elden Ring, Hollow Knight, Sekiro, Minecraft,
  Pokedex FRLG, GTA Vice City / San Andreas / V, JoJo, Cuphead, Manga,
  Marvel, DC, Halo, Resident Evil, FNaF, FNF, Mario, BioShock, Borderlands,
  Persona 5, Tekken, Destiny 2, Batman, Fallout NV, Steampunk, Cyberpunk,
  Ghostwire Tokyo, Skyrim, Baldur's Gate, Dispatch SDN, Terraria, Zelda,
  RuneScape, ULTRAKILL, Stellar Blade. Feminine: Girly-Pop, Coquette,
  Strawberry Milk, Lavender Haze. App parity: Discord (exact dark tokens),
  Aseprite (verified theme accents + pixel chrome). Choice persists in `settings.json`
  (separate file — `config.json` never touched). Preview one:
  `python app.py --theme yorha`. Full catalogue + build order: `THEMES.md`.
- Cut-off header text scrolls automatically (marquee with end pauses).
  Footer button labels are kept short per theme so they always fit — no scrolling there.
- Thinking models get room: Go output budgets start at 4096 tokens with one
  escalation retry, then a thinking-trace fallback instead of FAILED.
  Flapping 429s get one automatic retry after 20s; analyses run on daemon
  workers, so quitting or re-snipping mid-run can never take the app down
  (stale results are dropped).
- Reasoning-model quirks handled generically: any 400 naming an unsupported
  field (`temperature`, `top_p`, ...) gets that field stripped with a retry,
  and `max_tokens` is swapped to `max_completion_tokens` where demanded.
- Tray toggles: **Save snip PNGs** and **Log to analyses.md** (both on by
  default, persisted in `settings.json`). Overlay always shows the result.
- No autostart: runs only when you launch it. No registry writes. Quit from tray.
- Single log: `analyses.md` (every result appended, now with provider field). Snip PNGs in `snips/`.

## Setup

1. `pip install -r requirements.txt`
2. Set keys (pick per provider you use):
   - Gemini: `setx GEMINI_API_KEY "your-key"` (restart terminal), or
     `config.json` > `gemini_api_key`, or `--key KEY` for one run.
   - Go: `setx OPENCODE_GO_API_KEY "your-go-key"` (restart terminal), or
     `config.json` > `opencode_go_api_key`.
3. Selftest: `python app.py --selftest`

## Run

- `powershell -ExecutionPolicy Bypass -File run.ps1`
- or `python app.py`
- Tray icon appears. Press **Ctrl+LeftAlt+J** anywhere to snip.
- Drag = select, drag inside = move, drag corners/edges = resize.
- Enter / double-click / Analyze button = send. Esc / right-click = cancel.
- Result overlay appears near cursor (dark glass, 93% opacity): Copy / Open log / Close. Draggable by header.

## Notes

- Windows `RegisterHotKey` cannot distinguish left/right Alt by itself, so the app
  checks `GetAsyncKeyState(VK_LMENU)` on fire and ignores right-Alt-only presses.
- Multi-monitor + DPI: capture uses Pillow `ImageGrab(all_screens=True)` in global coords.
- Requested "3.5 flash lite": no such public model id; mapped to `gemini-2.5-flash-lite`.
  If Google ships a `gemini-3.5-flash-lite` id, change one line in `config.json`.
- Go vision list is curated: the live catalog (`GET /zen/go/v1/models`, public,
  snapshot in `go_models_live.json`) carries no capability flags, so 12 Go ids
  with no public image-input claim are excluded (DeepSeek non-vision V4s,
  longcat/step/hy/omen/space-bunny). The app intersects the curated list with
  the live catalog at startup. To add an id once verified, put
  `[{"id": "...", "label": "..."}]` in `config.json` > `opencode_go_vision_models`.
