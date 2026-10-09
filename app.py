#!/usr/bin/env python3
"""SS Analyzer - global-hotkey screenshot snip -> Gemini analysis -> overlay + log.

Hotkey : Ctrl + LeftAlt + J  (RegisterHotKey MOD_CONTROL|MOD_ALT, VK_J;
         left-Alt enforced by checking GetAsyncKeyState(VK_LMENU) on fire)
Flow   : hotkey -> fullscreen snip overlay (drag, move, resize handles) ->
         confirm -> Pillow grab -> Gemini Flash-Lite -> result overlay near
         cursor + append to single analyses.md log.
Autostart: none. Runs only when explicitly launched. No registry writes.
"""
import sys
import os
import io
import json
import re
import ctypes
import base64
import uuid
import traceback
from ctypes import wintypes
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULT_LOG = os.path.join(APP_DIR, "analyses.md")
SNIPS_DIR = os.path.join(APP_DIR, "snips")

VERSION = "1.0"

HOTKEY_ID = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_J = 0x4A
VK_LMENU = 0xA4  # left Alt
WM_HOTKEY = 0x0312

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # free-tier Flash-Lite id (2.5 ids are gated to past users), overridable
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# ---------------------------------------------------------------- OpenCode Go
# Go gateway: OpenAI-compatible chat/completions, Bearer <Go key>.
# Live catalog: GET https://opencode.ai/zen/go/v1/models (public, no key).
# The catalog carries no capability flags, so the vision list below is curated
# from model-family knowledge + the one explicit vision id, intersected at
# startup with the live catalog (vanished ids drop out). Override/add via
# config.json > opencode_go_vision_models (list of {"id","label"}).
GO_BASE = "https://opencode.ai/zen/go/v1"
GO_CHAT_URL = GO_BASE + "/chat/completions"
GO_RESP_URL = GO_BASE + "/responses"
GO_MSG_URL = GO_BASE + "/messages"
GO_MODELS_URL = GO_BASE + "/models"
GO_UA = "ss-analyzer/1.0"
GO_EFFORT = "low"  # reasoning-effort equivalent applied to every Go request
GO_429_RETRY_SECONDS = 0  # delayed retry after a 429; 0 = DISABLED for now (set e.g. 20 to re-enable)
# Per-model wire protocol, from the Go docs endpoint table
# (chat = OpenAI chat/completions, resp = OpenAI responses, msg = Anthropic messages).
GO_ENDPOINTS = {
    "minimax-m3": "msg", "minimax-m2.7": "msg", "minimax-m2.5": "msg",
    "kimi-k3": "chat", "kimi-k2.7-code": "chat", "kimi-k2.6": "chat", "kimi-k2.5": "chat",
    "glm-5.3": "chat", "glm-5.3-flash": "chat", "glm-5.2": "chat",
    "glm-5.1": "chat", "glm-5": "chat",
    "qwen3.8-max": "msg", "qwen3.8-flash": "msg", "qwen3.7-max": "msg",
    "qwen3.7-plus": "msg", "qwen3.6-plus": "msg", "qwen3.5-plus": "msg",
    "mimo-v2-omni": "chat", "mimo-v2.6-pro": "chat", "mimo-v2.6-flash": "chat",
    "mimo-v2.5-pro": "chat", "mimo-v2.5": "chat", "mimo-v2-pro": "chat",
    "deepseek-v4-flash-vision-exp": "chat",
    "grok-4.7": "resp", "grok-4.6": "resp", "grok-4.5": "resp",
    "gpt-6-luna": "resp", "gpt-5.6-luna": "resp",
    "claude-haiku-5-5": "msg",
    "muse-spark-1.3-contributor": "resp", "muse-spark-1.2-contributor": "resp",
    "longcat-2.5-preview-free": "chat", "step-5-preview-free": "chat",
    "space-bunny": "chat",
}


def go_endpoint_for(model):
    return GO_ENDPOINTS.get(model, "chat")

GO_VISION_MODELS = [  # (model id, switcher label) — image-input capable
    ("minimax-m3", "MiniMax M3"),
    ("minimax-m2.7", "MiniMax M2.7"),
    ("minimax-m2.5", "MiniMax M2.5"),
    ("kimi-k3", "Kimi K3"),
    ("kimi-k2.7-code", "Kimi K2.7 Code"),
    ("kimi-k2.6", "Kimi K2.6"),
    ("kimi-k2.5", "Kimi K2.5"),
    ("glm-5.3", "GLM 5.3"),
    ("glm-5.3-flash", "GLM 5.3 Flash"),
    ("glm-5.2", "GLM 5.2"),
    ("glm-5.1", "GLM 5.1"),
    ("glm-5", "GLM 5"),
    ("qwen3.8-max", "Qwen3.8 Max"),
    ("qwen3.8-flash", "Qwen3.8 Flash"),
    ("qwen3.7-max", "Qwen3.7 Max"),
    ("qwen3.7-plus", "Qwen3.7 Plus"),
    ("qwen3.6-plus", "Qwen3.6 Plus"),
    ("qwen3.5-plus", "Qwen3.5 Plus"),
    ("mimo-v2-omni", "MiMo V2 Omni"),
    ("mimo-v2.6-pro", "MiMo V2.6 Pro"),
    ("mimo-v2.6-flash", "MiMo V2.6 Flash"),
    ("mimo-v2.5-pro", "MiMo V2.5 Pro"),
    ("mimo-v2.5", "MiMo V2.5"),
    ("mimo-v2-pro", "MiMo V2 Pro"),
    ("deepseek-v4-flash-vision-exp", "DeepSeek V4 Flash Vision"),
    ("grok-4.7", "Grok 4.7"),
    ("grok-4.6", "Grok 4.6"),
    ("grok-4.5", "Grok 4.5"),
    ("gpt-6-luna", "GPT 6 Luna"),
    ("gpt-5.6-luna", "GPT 5.6 Luna"),
    ("claude-haiku-5-5", "Claude Haiku 5.5"),
    ("muse-spark-1.3-contributor", "Muse Spark 1.3"),
    ("muse-spark-1.2-contributor", "Muse Spark 1.2"),
    ("longcat-2.5-preview-free", "LongCat 2.5 Preview Free"),
    ("step-5-preview-free", "Step 5 Preview Free"),
    ("space-bunny", "Space Bunny Free"),
]
# Go ids with no public image-input claim — excluded from the switcher.
# Add any of these via config.json override once verified.
GO_EXCLUDED_UNCERTAIN = [
    "deepseek-v4-pro", "deepseek-v4-flash", "deepseek-flash",
    "deepseek-v4.1-flash", "longcat-2.0",
    "hy4-preview", "hy3", "hy3-preview", "omen-alpha",
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a precise screenshot analyst embedded in a desktop overlay. "
    "Analyze the provided screenshot snip. Return: 1) one-line summary, "
    "2) key elements and any visible text transcribed exactly, "
    "3) suggested next actions. Be concise, no fluff, no markdown tables. "
    "If nothing is readable, say so plainly."
)
DEFAULT_USER_PROMPT = "Analyze this screenshot snip."


# ---------------------------------------------------------------- config

def load_config():
    cfg = {
        "hotkey": "ctrl+leftalt+j",
        "provider": "gemini",  # "gemini" (direct free key) | "go" (OpenCode Go key)
        "model": DEFAULT_MODEL,  # active model for the active provider
        "gemini_model": DEFAULT_MODEL,
        "go_model": "minimax-m3",
        "gemini_api_key": "",
        "opencode_go_api_key": "",
        "opencode_go_vision_models": None,  # override: [{"id":..,"label":..}] or null=curated
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "user_prompt": DEFAULT_USER_PROMPT,
        "log_file": DEFAULT_LOG,
        "overlay_opacity": 0.93,
    }
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update(user)
    except Exception as e:
        print(f"[config] warning: could not read config.json: {e}")
    # env overrides (env wins, never commit keys)
    if os.environ.get("GEMINI_API_KEY"):
        cfg["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("OPENCODE_GO_API_KEY"):
        cfg["opencode_go_api_key"] = os.environ["OPENCODE_GO_API_KEY"]
    if os.environ.get("SS_MODEL"):
        cfg["model"] = os.environ["SS_MODEL"]
    if cfg.get("provider") not in ("gemini", "go"):
        cfg["provider"] = "gemini"
    if not os.path.isabs(cfg.get("log_file", "")):
        cfg["log_file"] = os.path.join(APP_DIR, cfg.get("log_file", "analyses.md"))
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[config] warning: could not write config.json: {e}")


def save_setup_keys(gemini_key, go_key):
    """Write a fresh/merged config.json from code defaults + wizard keys."""
    cfg = load_config()
    cfg["gemini_api_key"] = (gemini_key or "").strip()
    cfg["opencode_go_api_key"] = (go_key or "").strip()
    save_config(cfg)
    return cfg


def _probe_image():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return buf.getvalue()


def probe_gemini_key(key, timeout=30):
    return analyze_with_gemini(_probe_image(), key, DEFAULT_MODEL,
                               "Reply with exactly: OK", "Reply with exactly: OK",
                               timeout=timeout)


def probe_go_key(key, timeout=45):
    chat_model = next((mid for mid, _ in GO_VISION_MODELS
                       if go_endpoint_for(mid) == "chat"), "minimax-m3")
    return analyze_with_go(_probe_image(), key, chat_model,
                           "Reply with exactly: OK", "Reply with exactly: OK",
                           session_id="ss-analyzer-setup", timeout=timeout)


def run_setup_wizard(app, initial_gemini="", initial_go="", first_run=False):
    """Modal key-setup dialog. Returns (gemini, go) or None on cancel."""
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QApplication)
    from PySide6.QtCore import Qt
    dlg = QDialog()
    dlg.setWindowTitle("SS Analyzer Setup" + (" — first run" if first_run else ""))
    dlg.setMinimumWidth(440)
    lay = QVBoxLayout(dlg)
    info = QLabel("Analyzer keys live in this folder's config.json only — "
                  "nothing is sent anywhere except the model APIs.\n"
                  "Gemini key: required. OpenCode Go key: optional.")
    info.setWordWrap(True)
    lay.addWidget(info)

    def key_row(label_text, initial):
        lab = QLabel(label_text)
        edit = QLineEdit(initial or "")
        edit.setEchoMode(QLineEdit.Password)
        test = QPushButton("Test")
        stat = QLabel("")
        stat.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(lab)
        row.addWidget(edit, 1)
        row.addWidget(test)
        lay.addWidget(QLabel(""))  # spacer rhythm
        lay.addLayout(row)
        lay.addWidget(stat)
        return edit, test, stat

    g_edit, g_test, g_stat = key_row("Gemini key:", initial_gemini)
    o_edit, o_test, o_stat = key_row("Go key:", initial_go)

    def do_test(edit, stat, probe, name):
        key = edit.text().strip()
        if not key:
            stat.setText(f"{name}: empty — paste a key first.")
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()
            out = probe(key)
            stat.setText(f"{name}: OK ({str(out)[:40]})")
        except Exception as e:
            stat.setText(f"{name}: FAILED — {str(e)[:220]}")
        finally:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    g_test.clicked.connect(lambda: do_test(g_edit, g_stat, probe_gemini_key, "Gemini"))
    o_test.clicked.connect(lambda: do_test(o_edit, o_stat, probe_go_key, "Go"))

    btn_row = QHBoxLayout()
    save = QPushButton("Save & Launch" if first_run else "Save")
    cancel = QPushButton("Cancel")
    btn_row.addStretch(1)
    btn_row.addWidget(save)
    btn_row.addWidget(cancel)
    lay.addLayout(btn_row)

    def on_save():
        if not g_edit.text().strip():
            g_stat.setText("Gemini: a key is required to continue.")
            return
        dlg.accept()

    save.clicked.connect(on_save)
    cancel.clicked.connect(dlg.reject)
    if dlg.exec() != QDialog.Accepted:
        return None
    return g_edit.text().strip(), o_edit.text().strip()


def resolve_api_key(cfg, cli_key=None):
    if cli_key:
        return cli_key
    return (cfg.get("gemini_api_key") or "").strip()


# ---------------------------------------------------------------- logging (single file)

LOG_HEADER = "# SS Analyzer - analyses log\n\nAll screenshot analyses, newest appended at bottom. Single file by design.\n\n---\n"

def ensure_log(path):
    try:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(LOG_HEADER)
    except Exception as e:
        print(f"[log] warning: cannot init log: {e}")


def append_log(path, model, bbox, image_path, prompt, output, error=None, provider="gemini"):
    ensure_log(path)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    x, y, w, h = bbox
    entry = (
        f"\n## {ts}\n\n"
        f"- provider: `{provider}`\n"
        f"- model: `{model}`\n"
        f"- bbox: x={x} y={y} w={w} h={h}\n"
        f"- image: `{image_path}`\n"
        f"- prompt: {prompt}\n\n"
        f"```text\n{(error or output or '(empty)').strip()}\n```\n\n---\n"
    )
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[log] warning: cannot append to log: {e}")
    return path


# ---------------------------------------------------------------- Gemini client (requests, no extra SDK)

def analyze_with_gemini(image_bytes, api_key, model, system_prompt, user_prompt, timeout=60):
    import requests
    if not (api_key or "").strip():
        raise RuntimeError("No GEMINI_API_KEY set. Run: setx GEMINI_API_KEY \"your-key\" "
                           "(restart terminal), or put it in config.json > gemini_api_key.")
    url = GEMINI_URL.format(model=model) + f"?key={api_key}"
    b64 = base64.b64encode(image_bytes).decode("ascii")

    def shapes(budget):
        return [
            {  # attempt 1: system_instruction (correct snake_case for v1beta REST)
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [
                    {"text": user_prompt},
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                ]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": budget},
            },
            {  # attempt 2 fallback: system prompt merged into user text
                "contents": [{"parts": [
                    {"text": system_prompt + "\n\n" + user_prompt},
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                ]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": budget},
            },
        ]

    last_err = "unknown error"
    # Thinking models can length-exhaust a small budget the same way Go
    # thinkers do: escalate 1024 -> 4096 -> 8192 before giving up.
    for budget in (1024, 4096, 8192):
        for i, body in enumerate(shapes(budget)):
            try:
                r = requests.post(url, json=body, timeout=timeout)
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code}: {r.text[:500]}"
                    if r.status_code == 400 and i == 0:
                        continue  # retry with merged-prompt body
                    raise RuntimeError(last_err)
                data = r.json()
                cands = data.get("candidates") or []
                if not cands:
                    # API-level block / empty
                    last_err = f"no candidates: {json.dumps(data)[:500]}"
                    raise RuntimeError(last_err)
                parts = ((cands[0].get("content") or {}).get("parts")) or []
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                if not text:
                    if (cands[0].get("finishReason") or "").upper() == "MAX_TOKENS":
                        last_err = "length: output budget exhausted"
                        break  # escalate budget
                    raise RuntimeError(f"empty text in response: {json.dumps(data)[:500]}")
                return text
            except RuntimeError:
                if i == len(shapes(budget)) - 1 and budget == 8192:
                    raise
                last_err = traceback.format_exc(limit=3)
                continue
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                if i == len(shapes(budget)) - 1 and budget == 8192:
                    raise RuntimeError(last_err) from e
                continue
    raise RuntimeError(last_err)


# ---------------------------------------------------------------- OpenCode Go client (OpenAI-compatible)

class _BudgetExhausted(Exception):
    """Model stopped with content null on length: thinking ate the budget."""
    def __init__(self, message, data=None):
        super().__init__(message)
        self.data = data


def _reasoning_tail(endpoint, data, limit=800):
    """Salvage thinking trace when the answer itself never fit."""
    try:
        if endpoint == "chat":
            ch = (data.get("choices") or [{}])[0]
            txt = (ch.get("message") or {}).get("reasoning") or ""
        elif endpoint == "resp":
            parts = []
            for item in data.get("output") or []:
                if isinstance(item, dict) and item.get("type") == "reasoning":
                    for s in item.get("summary") or []:
                        if isinstance(s, dict) and s.get("type") == "summary_text":
                            parts.append(s.get("text", ""))
            txt = "\n".join(parts)
        else:
            return ""
        txt = (txt or "").strip()
        return txt[-limit:] if txt else ""
    except Exception:
        return ""


def fetch_go_catalog(timeout=15):
    """Live Go model ids from the public endpoint. Returns list or None."""
    import requests
    r = requests.get(GO_MODELS_URL, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
    return ids or None


def resolve_go_vision_models(cfg, live_ids=None):
    """Curated vision list, intersected with the live catalog when available.

    live_ids=None -> skip intersection (offline). Config override wins.
    Returns list of (id, label)."""
    override = cfg.get("opencode_go_vision_models")
    if isinstance(override, list) and override:
        out = []
        for item in override:
            if isinstance(item, dict) and item.get("id"):
                out.append((item["id"], item.get("label") or item["id"]))
            elif isinstance(item, str):
                out.append((item, item))
        return out
    labels = {mid: lbl for mid, lbl in GO_VISION_MODELS}
    if live_ids is None:
        return list(GO_VISION_MODELS)
    live = set(live_ids)
    kept = [(mid, labels[mid]) for mid, _ in GO_VISION_MODELS if mid in live]
    return kept or list(GO_VISION_MODELS)


def build_go_payload(model, system_prompt, user_prompt, image_b64, with_effort=True,
                     budget=4096):
    return build_go_chat(model, system_prompt, user_prompt, image_b64, with_effort, budget)


def build_go_chat(model, system_prompt, user_prompt, image_b64, with_effort=True,
                  budget=4096):
    body = {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": budget,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
            ]},
        ],
    }
    if with_effort:
        # effort-low equivalent; gateway normalizes per provider.
        # Both spellings sent; stripped on 400-retry (see analyze_with_go).
        body["reasoning_effort"] = GO_EFFORT
        body["reasoning"] = {"effort": GO_EFFORT}
    return body


def build_go_responses(model, system_prompt, user_prompt, image_b64, with_effort=True,
                       budget=4096):
    body = {
        "model": model,
        "stream": False,
        "store": False,
        "max_output_tokens": budget,
        "temperature": 0.2,
        "input": [
            {"role": "system", "content": [
                {"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [
                {"type": "input_text", "text": user_prompt},
                {"type": "input_image",
                 "image_url": "data:image/png;base64," + image_b64},
            ]},
        ],
    }
    if with_effort:
        body["reasoning"] = {"effort": GO_EFFORT}
    return body


def build_go_messages(model, system_prompt, user_prompt, image_b64, with_effort=True,
                      budget=4096):
    # Anthropic Messages wire format. No portable effort knob exists here;
    # effort-low is expressed via the tight max_tokens cap (+ low temperature).
    # `with_effort` kept for a uniform retry shape; body is already minimal.
    return {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": budget,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": user_prompt},
            ]},
        ],
    }


def go_url_for(endpoint):
    return {"chat": GO_CHAT_URL, "resp": GO_RESP_URL, "msg": GO_MSG_URL}[endpoint]


def parse_go_response(data):
    return parse_go_chat(data)


def parse_go_chat(data):
    try:
        ch = data["choices"][0]
        msg = ch["message"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"unexpected Go response shape: {json.dumps(data)[:500]}")
    content = msg.get("content", "")
    if isinstance(content, list):  # content-part array variant
        chunks = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                chunks.append(p.get("text", ""))
            elif isinstance(p, str):
                chunks.append(p)
        content = "".join(chunks)
    text = (content or "").strip()
    if not text:
        if msg.get("refusal"):
            raise RuntimeError(f"model refused: {msg['refusal'][:500]}")
        if ch.get("finish_reason") == "length":
            raise _BudgetExhausted("length: thinking consumed the output budget", data)
        raise RuntimeError(f"empty text in Go response: {json.dumps(data)[:500]}")
    return text


def parse_go_responses(data):
    try:
        out = data["output"]
    except (KeyError, TypeError):
        raise RuntimeError(f"unexpected Responses shape: {json.dumps(data)[:500]}")
    chunks = []
    for item in out:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content", []):
                if isinstance(part, dict) and part.get("type") == "output_text":
                    chunks.append(part.get("text", ""))
        elif item.get("type") == "refusal":
            raise RuntimeError(f"model refused: {json.dumps(item)[:300]}")
    text = "".join(chunks).strip()
    if not text:
        if isinstance(data, dict) and isinstance(data.get("incomplete_details"), dict) \
                and data["incomplete_details"].get("reason") == "max_output_tokens":
            raise _BudgetExhausted("length: thinking consumed the output budget", data)
        raise RuntimeError(f"empty text in Responses output: {json.dumps(data)[:500]}")
    return text


def parse_go_messages(data):
    try:
        blocks = data["content"]
    except (KeyError, TypeError):
        raise RuntimeError(f"unexpected Messages shape: {json.dumps(data)[:500]}")
    chunks = [b.get("text", "") for b in blocks
              if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(chunks).strip()
    if not text:
        if isinstance(data, dict) and data.get("stop_reason") == "max_tokens":
            raise _BudgetExhausted("length: thinking consumed the output budget", data)
        raise RuntimeError(f"empty text in Messages output: {json.dumps(data)[:500]}")
    return text


def _unsupported_param(err_text):
    """Name of the rejected top-level request field in a 400 message, if any.

    Covers the whole family: temperature/top_p rejected by reasoning models,
    unknown reasonings spellings on strict gateways, max_tokens vs
    max_completion_tokens, stray response_format/logprobs, etc."""
    text = err_text or ""
    patterns = (
        r"[Uu]nrecognized request argument supplied:\s*([A-Za-z_][\w.]*)",
        r"[Uu]nrecognized request argument[s]?:?\s*['\"]?([A-Za-z_]\w*)",
        r"['\"]([A-Za-z_]\w*)['\"] is not (?:a )?supported",
        r"([A-Za-z_]\w*) is not (?:a )?supported (?:as (?:a )?parameter|parameter)",
        r"[Uu]nsupported parameter:?\s*['\"]?([A-Za-z_]\w*)",
        r"Additional properties are not allowed\s*\(\s*['\"]([A-Za-z_]\w*)",
        r"unknown field:\s*['\"]?([A-Za-z_]\w*)",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).split(".")[-1]
    lowered = text.lower()
    for known in ("temperature", "top_p", "reasoning_effort", "reasoning",
                  "max_tokens", "max_completion_tokens", "response_format",
                  "logprobs", "top_logprobs", "seed", "stop", "store"):
        if known in lowered:
            return known
    return None


def analyze_with_go(image_bytes, api_key, model, system_prompt, user_prompt,
                    session_id="", timeout=90):
    import requests
    if not (api_key or "").strip():
        raise RuntimeError("No OpenCode Go key set. Run: setx OPENCODE_GO_API_KEY \"your-key\" "
                           "(restart terminal), or put it in config.json > opencode_go_api_key.")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    endpoint = go_endpoint_for(model)
    builders = {"chat": build_go_chat, "resp": build_go_responses, "msg": build_go_messages}
    parsers = {"chat": parse_go_chat, "resp": parse_go_responses, "msg": parse_go_messages}
    headers = {"Authorization": f"Bearer {api_key.strip()}",
               "Content-Type": "application/json",
               "User-Agent": GO_UA,
               "x-opencode-session": session_id or ("ss-analyzer-" + uuid.uuid4().hex[:12])}
    last_err = "unknown error"
    data = None
    waited = False  # one delayed retry on flapping StepFun-style 429s
    for budget in (4096, 16384):
        # Two starting shapes: full (effort fields) then bare. Each shape then
        # goes through the param-strip loop, which deletes whatever top-level
        # field a 400 names (temperature, top_p, ...) and swaps max_tokens to
        # max_completion_tokens where demanded. Caps the whole family.
        for start_bare in (False, True):
            body = builders[endpoint](model, system_prompt, user_prompt, b64,
                                      with_effort=not start_bare, budget=budget)
            for _ in range(5):  # strip loop
                try:
                    r = requests.post(go_url_for(endpoint), headers=headers, json=body, timeout=timeout)
                    if r.status_code == 429 and not waited and GO_429_RETRY_SECONDS > 0:
                        waited = True
                        try:
                            import time
                            time.sleep(GO_429_RETRY_SECONDS)
                        except Exception:
                            pass
                        r = requests.post(go_url_for(endpoint), headers=headers, json=body, timeout=timeout)
                    if r.status_code != 200:
                        last_err = f"HTTP {r.status_code}: {r.text[:500]}"
                        if r.status_code != 400:
                            raise RuntimeError(_friendly_go_error(last_err))
                        param = _unsupported_param(r.text)
                        if param == "max_tokens" and endpoint == "chat" and "max_tokens" in body:
                            body["max_completion_tokens"] = body.pop("max_tokens")
                            continue
                        if param and param in body:
                            del body[param]
                            continue
                        raise RuntimeError(_friendly_go_error(last_err))
                    data = r.json()
                except _BudgetExhausted as be:
                    last_err = str(be)
                    data = be.data
                    break  # escalate: retry whole request at a bigger budget
                except RuntimeError:
                    raise
                except Exception as e:
                    raise RuntimeError(f"{type(e).__name__}: {e}") from e
                try:
                    return parsers[endpoint](data)
                except _BudgetExhausted as be:
                    last_err = str(be)
                    data = be.data
                    break  # escalate: retry whole request at a bigger budget
            else:
                continue
            break
    # Still empty after the big budget: salvage the thinking trace if present.
    tail = _reasoning_tail(endpoint, data)
    if tail:
        return "[partial — model ran out of room; thinking trace]\n" + tail
    raise RuntimeError(_friendly_go_error(last_err))


def _friendly_go_error(err):
    if "429" in err:
        return (err + " — provider endpoint is flapping; wait a minute and snip again, "
                "or switch models from the tray menu.")
    return err


def analyze_dispatch(provider, image_bytes, gemini_key, go_key, model,
                      system_prompt, user_prompt, session_id=""):
    if provider == "go":
        return analyze_with_go(image_bytes, go_key, model, system_prompt, user_prompt,
                               session_id=session_id)
    return analyze_with_gemini(image_bytes, gemini_key, model, system_prompt, user_prompt)


# ---------------------------------------------------------------- selftest (no GUI needed)

def run_selftest(cli_model=None, cli_key=None, cli_log=None):
    print("== SS Analyzer selftest ==")
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            detail = fn()
            print(f"PASS  {name}" + (f"  ({detail})" if detail else ""))
        except Exception as e:
            ok = False
            print(f"FAIL  {name}: {e}")

    def t_config():
        cfg = load_config()
        assert cfg.get("model"), "empty model"
        return f"model={cli_model or cfg['model']}"

    def t_log():
        path = cli_log or load_config().get("log_file", DEFAULT_LOG)
        ensure_log(path)
        assert os.path.exists(path), "log not created"
        assert os.access(path, os.W_OK), "log not writable"
        return path

    def t_hotkey():
        u32 = ctypes.windll.user32
        reg = u32.RegisterHotKey(None, 9999, MOD_CONTROL | MOD_ALT, VK_J)
        if not reg:
            code = ctypes.GetLastError()
            if code == 1409:
                return "already registered (app running?) - hotkey path OK"
            raise RuntimeError(f"RegisterHotKey failed, WinError {code}")
        u32.UnregisterHotKey(None, 9999)
        return "Ctrl+Alt+J registrable"

    def t_grab():
        from PIL import ImageGrab
        assert hasattr(ImageGrab, "grab"), "no ImageGrab.grab"
        return "Pillow ImageGrab available"

    def t_qt():
        import PySide6
        return f"PySide6 {PySide6.__version__}"

    def t_key():
        cfg = load_config()
        gem = cli_key or (cfg.get("gemini_api_key") or "")
        go = cfg.get("opencode_go_api_key") or ""
        bits = []
        bits.append("gemini key present" if gem else "no GEMINI_API_KEY")
        bits.append("Go key present" if go else "no OPENCODE_GO_API_KEY")
        return "; ".join(bits) + " (see README)"

    def t_go_registry():
        cfg = load_config()
        items = resolve_go_vision_models(cfg, live_ids=None)
        assert len(items) >= 30, f"vision registry too small: {len(items)}"
        assert all(mid and lbl for mid, lbl in items), "blank id/label"
        return f"{len(items)} vision models curated"

    def t_go_payload():
        body = build_go_payload("minimax-m3", "sys", "hi", "QUJD", with_effort=True)
        assert body["reasoning_effort"] == "low" and body["reasoning"] == {"effort": "low"}
        assert body["max_tokens"] == 4096, "default budget too small for thinkers"
        assert build_go_payload("x", "s", "h", "Q", budget=8192)["max_tokens"] == 8192
        assert build_go_responses("x", "s", "h", "Q")["max_output_tokens"] == 4096
        assert build_go_messages("x", "s", "h", "Q")["max_tokens"] == 4096
        parts = body["messages"][1]["content"]
        assert any(p.get("type") == "image_url" for p in parts), "no image_url part"
        bare = build_go_payload("minimax-m3", "sys", "hi", "QUJD", with_effort=False)
        assert "reasoning_effort" not in bare and "reasoning" not in bare
        resp = build_go_responses("gpt-6-luna", "sys", "hi", "QUJD", with_effort=True)
        assert resp["reasoning"] == {"effort": "low"}
        assert resp["input"][1]["content"][1]["type"] == "input_image"
        msg = build_go_messages("minimax-m3", "sys", "hi", "QUJD")
        assert msg["messages"][0]["content"][0]["type"] == "image"
        assert parse_go_messages({"content": [{"type": "text", "text": "hello"}]}) == "hello"
        assert parse_go_responses({"output": [{"type": "message", "content": [
            {"type": "output_text", "text": "hi"}]}]}) == "hi"
        # length-exhaustion (the step-5 failure): parsers must signal budget,
        # not report generic emptiness
        try:
            parse_go_chat({"choices": [{"finish_reason": "length",
                                        "message": {"role": "assistant", "content": None,
                                                    "reasoning": "thinking trace here"}}]})
            raise AssertionError("no budget signal")
        except _BudgetExhausted as be:
            tail = _reasoning_tail("chat", be.data)
            assert tail == "thinking trace here", f"tail lost: {tail!r}"
        return "chat/resp/msg builders + parsers ok, effort=low"

    def t_gemini_budget():
        import requests as _R
        budgets = []
        real_post = _R.post

        class _Resp:
            def __init__(self, code, payload):
                self.status_code = code
                self.text = "" if code == 200 else "err"
                self._payload = payload

            def json(self):
                return self._payload

        def fake_post(url, json=None, timeout=None):
            budgets.append(json["generationConfig"]["maxOutputTokens"])
            if len(budgets) == 1:
                return _Resp(200, {"candidates": [{"finishReason": "MAX_TOKENS",
                                 "content": {"parts": []}}]})
            return _Resp(200, {"candidates": [{"finishReason": "STOP",
                             "content": {"parts": [{"text": "escalated-ok"}]}}]})

        _R.post = fake_post
        try:
            out = analyze_with_gemini(b"x", "k", "m", "s", "h")
        finally:
            _R.post = real_post
        assert out == "escalated-ok", f"no escalation: {out!r}"
        assert budgets[0] == 1024 and budgets[1] == 4096, f"budgets: {budgets}"
        return "length-exhaustion escalates 1024->4096"

    def t_go_param_strip():
        assert _unsupported_param("'temperature' is not supported") == "temperature"
        assert _unsupported_param("Unsupported parameter: 'top_p'") == "top_p"
        assert _unsupported_param("unrecognized request argument supplied: reasoning_effort") == "reasoning_effort"
        assert _unsupported_param("all good") is None
        import requests as _R
        seen = []
        real_post = _R.post

        class _Resp:
            def __init__(self, code, text="", payload=None):
                self.status_code = code
                self.text = text
                self._payload = payload

            def json(self):
                return self._payload

        def fake_post(url, headers=None, json=None, timeout=None):
            seen.append(sorted(json.keys()))
            if "temperature" in json:
                return _Resp(400, "\"temperature\" is not supported in this model")
            return _Resp(200, "", {"choices": [{"finish_reason": "stop",
                             "message": {"role": "assistant", "content": "stripped-ok"}}]})

        _R.post = fake_post
        try:
            out = analyze_with_go(b"x", "k", "kimi-k3", "s", "h", session_id="t")
        finally:
            _R.post = real_post
        assert out == "stripped-ok", f"no recovery: {out!r}"
        assert len(seen) == 2 and "temperature" not in seen[1], f"no strip: {seen}"
        return "temperature-class 400s stripped and retried"

    def t_go_endpoints():
        cfg = load_config()
        items = resolve_go_vision_models(cfg, live_ids=None)
        unmapped = [mid for mid, _ in items if mid not in GO_ENDPOINTS]
        assert not unmapped, f"no endpoint mapping: {unmapped}"
        kinds = {go_endpoint_for(mid) for mid, _ in items}
        assert kinds == {"chat", "resp", "msg"}, f"expected all 3 protocols, got {kinds}"
        counts = {k: sum(1 for mid, _ in items if go_endpoint_for(mid) == k) for k in kinds}
        return f"{len(items)} models mapped {counts}"

    def t_themes():
        assert set(THEME_ORDER) <= set(THEMES), "order lists unknown theme"
        assert len(THEME_ORDER) >= 16, "pass 2 added fewer than 10"
        for tid in THEME_ORDER:
            t = THEMES[tid]
            for k in ("label", "title", "dot", "min_w", "max_w", "opacity",
                      "reveal", "footer", "autohide", "tear", "buttons", "qss"):
                assert k in t, f"{tid} missing {k}"
            assert t["reveal"] in ("instant", "type", "print"), tid
            assert t["footer"] in ("always", "hover"), tid
            assert len(t["buttons"]) == 3, tid
            assert t["qss"].count("{") == t["qss"].count("}"), f"{tid} braces"
            for fl in t.get("floaters", []):
                assert len(fl) == 6, f"{tid} floater shape {fl}"
                assert fl[1] in ("tl", "tr", "bl", "br"), f"{tid} floater corner {fl}"
            for k in ("note_top", "note_bot", "ticker_text", "alarm_text",
                      "status_ok", "status_err"):
                assert isinstance(t.get(k, ""), str), f"{tid} {k} not str"
        assert get_theme("nope")["label"] == "Obsidian Glass", "fallback broken"
        return f"{len(THEME_ORDER)} themes, engine fields ok"

    def t_go_catalog_live():
        try:
            ids = fetch_go_catalog(timeout=15)
        except Exception as e:
            return f"WARN offline ({type(e).__name__}) — baked list used"
        assert ids, "empty live catalog"
        return f"live catalog reachable ({len(ids)} ids)"

    check("config loads", t_config)
    check("single log file writable", t_log)
    check("global hotkey registrable", t_hotkey)
    check("screenshot grab backend", t_grab)
    check("Qt backend", t_qt)
    check("api keys", t_key)
    check("go vision registry", t_go_registry)
    check("go payloads (effort low)", t_go_payload)
    check("gemini budget escalation", t_gemini_budget)
    check("go param strip", t_go_param_strip)
    check("go endpoint map", t_go_endpoints)
    check("overlay themes", t_themes)
    check("go live catalog", t_go_catalog_live)
    print("RESULT:", "OK - ready to run `python app.py`" if ok else "FAILED - see FAIL lines")
    return 0 if ok else 1


SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")  # UI prefs (theme). NOT config.json.


def load_settings():
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[settings] warning: {e}")
    return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[settings] warning: could not write settings.json: {e}")


# ---------------------------------------------------------------- overlay themes
# Each theme = layout + tokens + motion. Full QSS per theme (self-contained),
# plus structural flags the overlay honors: geometry, reveal mode, footer
# visibility, auto-hide, tear rows, per-theme button labels.

THEMES = {
    "obsidian": {
        "label": "Obsidian Glass",
        "title": "SS Analyzer", "dot": "\u25cf",
        "min_w": 380, "max_w": 520, "opacity": 0.93,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Copy", "Open log", "Close"),
        "qss": """
                #card { background: rgba(17,22,32,242); border: 1px solid #3d4a6b;
                        border-radius: 14px; }
                #dot { color: #7c9cff; font-size: 14px; }
                #title { color: #f2f5fb; font-size: 14px; font-weight: 700; }
                #x { background: transparent; color: #8b96b0; border: none;
                     font-size: 13px; padding: 2px 8px; border-radius: 6px; }
                #x:hover { background: rgba(255,255,255,24); color: #fff; }
                #body { background: rgba(255,255,255,10); color: #e8ecf4;
                        border: 1px solid #2b3550; border-radius: 9px;
                        font-size: 12.5px; padding: 4px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #7c9cff; border-radius: 3px; }
                #status { color: #8b96b0; font-size: 11px; }
                #btn { background: rgba(255,255,255,16); color: #e8ecf4;
                       border: 1px solid #3a4358; border-radius: 7px; padding: 6px 12px; }
                #btn:hover { background: rgba(255,255,255,32); }
                #btnPri { background: #4f7cff; color: white; border: none;
                          border-radius: 7px; padding: 6px 14px; font-weight: 600; }
                #btnPri:hover { background: #638bff; }
                #modelCombo { background: rgba(255,255,255,14); color: #dfe6f3;
                              border: 1px solid #3a4358; border-radius: 7px;
                              padding: 4px 8px; font-size: 11.5px; max-width: 220px; }
                #modelCombo:hover { background: rgba(255,255,255,26); }
                #modelCombo QAbstractItemView { background: #1a2130; color: #e8ecf4;
                              selection-background-color: #4f7cff; border: 1px solid #3d4a6b; }
                """,
    },
    "clawd": {
        "label": "Clawd Terminal",
        "title": "$ ss-analyze --model {model}", "dot": "\u276f",
        "min_w": 520, "max_w": 560, "opacity": 0.96,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("[copy]", "[open-log]", "[close]"),
        "qss": """
                #card { background: rgba(26,26,26,245); border: 1px solid #3a3a3a;
                        border-radius: 6px; }
                #dot { color: #d87757; font-size: 14px; font-weight: bold; }
                #title { color: #c3c1ba; font-size: 12px; font-family: Consolas, monospace; }
                #x { background: transparent; color: #6b6560; border: none;
                     font-size: 12px; padding: 2px 8px; }
                #x:hover { color: #ff5555; }
                #body { background: transparent; color: #c3c1ba; border: none;
                        font-family: Consolas, monospace; font-size: 12px; padding: 2px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #d87757; }
                #status { color: #6b6560; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #8b96b0; border: none;
                       font-family: Consolas, monospace; padding: 6px 8px; }
                #btn:hover { color: #d87757; }
                #btnPri { background: transparent; color: #d87757; border: none;
                          font-family: Consolas, monospace; font-weight: bold; padding: 6px 8px; }
                #btnPri:hover { color: #f09274; }
                #modelCombo { background: #2a2a2a; color: #c3c1ba;
                              border: 1px solid #3a3a3a; border-radius: 4px;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 230px; }
                #modelCombo QAbstractItemView { background: #2a2a2a; color: #c3c1ba;
                              selection-background-color: #d87757; selection-color: #1a1a1a; }
                """,
    },
    "yorha": {
        "label": "YoRHa Interface",
        "title": "POD 042 \u2014 SUPPORT UNIT : {model}", "dot": "\u25c6",
        "min_w": 460, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Record", "Archive", "Dismiss"),
        "qss": """
                #card { background: #c3bda8; border: none; border-radius: 2px; }
                #dot { color: #4b413d; font-size: 13px; }
                #title { color: #f2eee0; font-size: 13px; font-weight: 700;
                         letter-spacing: 2px; background: #4b413d; padding: 4px 10px; }
                #x { background: #4b413d; color: #f2eee0; border: none;
                     font-size: 12px; padding: 4px 10px; }
                #x:hover { background: #594e4a; }
                #body { background: #b8b29d; color: #2e2825; border: none;
                        border-top: 2px solid #4b413d; font-size: 13px; padding: 8px; }
                #spin { height: 5px; border: none; background: #b0ab98; }
                #spin::chunk { background: #4b413d; }
                #status { color: #594e4a; font-size: 11px; letter-spacing: 1px; }
                #btn { background: #b0ab98; color: #2e2825; border: 1px solid #4b413d;
                       border-radius: 0px; padding: 7px 14px; letter-spacing: 1px; }
                #btn:hover { background: #c3bda8; }
                #btnPri { background: #4b413d; color: #f2eee0; border: none;
                          border-radius: 0px; padding: 7px 16px; font-weight: 700;
                          letter-spacing: 1px; }
                #btnPri:hover { background: #594e4a; }
                #modelCombo { background: #b0ab98; color: #2e2825;
                              border: 1px solid #4b413d; border-radius: 0px;
                              padding: 4px 8px; font-size: 11.5px; max-width: 220px; }
                #modelCombo QAbstractItemView { background: #c3bda8; color: #2e2825;
                              selection-background-color: #4b413d; selection-color: #f2eee0; }
                """,
    },
    "stdout": {
        "label": "stdout (minimal)",
        "title": "", "dot": "",
        "min_w": 420, "max_w": 460, "opacity": 1.0,
        "reveal": "instant", "footer": "hover", "autohide": 12, "tear": False,
        "buttons": ("copy", "log", "x"),
        "qss": """
                #card { background: rgba(0,0,0,110); border: none; border-radius: 8px; }
                #dot { color: transparent; font-size: 1px; }
                #title { color: transparent; font-size: 1px; }
                #x { background: transparent; color: #8b96b0; border: none; font-size: 11px; }
                #x:hover { color: #fff; }
                #body { background: transparent; color: #e8e8e8; border: none;
                        font-family: Consolas, monospace; font-size: 12px; padding: 6px 8px; }
                #spin { height: 3px; border: none; background: transparent; }
                #spin::chunk { background: #8b96b0; }
                #status { color: #777; font-size: 10px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #8b96b0; border: none;
                       font-family: Consolas, monospace; font-size: 11px; }
                #btn:hover { color: #fff; }
                #btnPri { background: transparent; color: #bbb; border: none;
                          font-family: Consolas, monospace; font-size: 11px; }
                #btnPri:hover { color: #fff; }
                #modelCombo { background: transparent; color: #777; border: none;
                              font-family: Consolas, monospace; font-size: 10px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: #111; color: #e8e8e8; }
                """,
    },
    "receipt": {
        "label": "Thermal Receipt",
        "title": "SS MART \u00b7 ORDER", "dot": "*",
        "min_w": 320, "max_w": 340, "opacity": 1.0,
        "reveal": "print", "footer": "always", "autohide": 0, "tear": True,
        "buttons": ("PRINT", "LEDGER", "NO RECEIPT"),
        "qss": """
                #card { background: #fafafa; border: none; border-radius: 0px; }
                #dot { color: #222; font-size: 12px; }
                #title { color: #222; font-size: 13px; font-weight: 700;
                         font-family: Consolas, monospace; letter-spacing: 1px; }
                #x { background: transparent; color: #222; border: none;
                     font-size: 12px; font-family: Consolas, monospace; }
                #x:hover { background: #e4e4e4; }
                #body { background: #fafafa; color: #222; border: none;
                        border-top: 1px dashed #999; border-bottom: 1px dashed #999;
                        font-family: Consolas, monospace; font-size: 12px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #222; }
                #status { color: #666; font-size: 10px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #222;
                       border: 1px dashed #999; border-radius: 0px;
                       font-family: Consolas, monospace; padding: 6px 10px; }
                #btn:hover { background: #eee; }
                #btnPri { background: #222; color: #fafafa; border: none;
                          border-radius: 0px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 12px; }
                #modelCombo { background: #fafafa; color: #222;
                              border: 1px dashed #999; border-radius: 0px;
                              font-family: Consolas, monospace; font-size: 10.5px;
                              max-width: 180px; }
                #modelCombo QAbstractItemView { background: #fafafa; color: #222; }
                #tear { color: #999; font-family: Consolas, monospace; font-size: 10px; }
                """,
    },
    "brutalist": {
        "label": "Brutalist Slab",
        "title": "SS ANALYZER", "dot": "\u25fc",
        "min_w": 420, "max_w": 520, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("COPY", "LOG", "CLOSE"),
        "qss": """
                #card { background: #f2f2f2; border: 3px solid #000; border-radius: 0px; }
                #dot { color: #ff4d00; font-size: 14px; }
                #title { color: #000; font-size: 15px; font-weight: 900; }
                #x { background: #000; color: #fff; border: none;
                     font-size: 13px; font-weight: bold; padding: 2px 10px; }
                #x:hover { background: #ff4d00; }
                #body { background: #fff; color: #000; border: 3px solid #000;
                        border-radius: 0px; font-size: 13px; padding: 6px; }
                #spin { height: 8px; border: 2px solid #000; background: #fff; }
                #spin::chunk { background: #ff4d00; }
                #status { color: #000; font-size: 11px; font-weight: bold; }
                #btn { background: #f2f2f2; color: #000; border: 3px solid #000;
                       border-radius: 0px; font-weight: bold; padding: 8px 14px; }
                #btn:hover { background: #000; color: #fff; }
                #btnPri { background: #ff4d00; color: #000; border: 3px solid #000;
                          border-radius: 0px; font-weight: 900; padding: 8px 16px; }
                #btnPri:hover { background: #000; color: #ff4d00; }
                #modelCombo { background: #fff; color: #000; border: 3px solid #000;
                              border-radius: 0px; padding: 4px 8px;
                              font-size: 11.5px; max-width: 220px; }
                #modelCombo QAbstractItemView { background: #fff; color: #000;
                              selection-background-color: #000; selection-color: #ff4d00; }
                """,
    },
    "miku": {
        "label": "Digital Diva 01",
        "title": "DIGITAL DIVA 01 \u266a {model}", "dot": "\u266a",
        "min_w": 340, "max_w": 380, "opacity": 0.95,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "eq": True,
        "buttons": ("Lyrics", "Setlist", "Close"),
        "qss": """
                #card { background: rgba(11,14,20,244); border: 1px solid #39c5cf;
                        border-radius: 14px; }
                #dot { color: #39c5cf; font-size: 14px; }
                #title { color: #ffffff; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
                #x { background: transparent; color: #5e7a80; border: none; font-size: 13px; }
                #x:hover { color: #ff5c8a; }
                #body { background: rgba(57,197,207,12); color: #eafcff;
                        border: 1px solid #1e3a3e; border-radius: 9px; font-size: 12.5px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #39c5cf; }
                #status { color: #5e7a80; font-size: 11px; }
                #btn { background: rgba(57,197,207,20); color: #d8f7fa;
                       border: 1px solid #2a5a5e; border-radius: 8px; padding: 6px 12px; }
                #btn:hover { background: rgba(57,197,207,45); }
                #btnPri { background: #39c5cf; color: #062a2e; border: none;
                          border-radius: 8px; padding: 6px 14px; font-weight: 700; }
                #btnPri:hover { background: #5fd6de; }
                #modelCombo { background: #0e1a1d; color: #bfeef2;
                              border: 1px solid #2a5a5e; border-radius: 7px;
                              font-size: 11px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: #0e1a1d; color: #bfeef2;
                              selection-background-color: #39c5cf; selection-color: #062a2e; }
                #eqbar { background: #39c5cf; border-radius: 2px; }
                """,
    },
    "girly": {
        "label": "Girly-Pop Overdrive",
        "title": "omg results!! \u273f", "dot": "\u2661",
        "min_w": 400, "max_w": 460, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u22c6", "tr", 8, 6, -14, "#ff5c8a"),
                     ("\u2661", "tl", 10, 26, 10, "#a78bfa"),
                     ("\u273f", "br", 12, 30, -8, "#ff8fc7")],
        "buttons": ("Copy!!", "Log \u2661", "Close \u273f"),
        "qss": """
                #card { background: #fff3f8; border: 3px solid #ff8fc7; border-radius: 18px; }
                #dot { color: #ff5c8a; font-size: 16px; }
                #title { color: #5b2340; font-size: 15px; font-weight: 900; }
                #x { background: #ffd6e8; color: #5b2340; border: 2px solid #ff8fc7;
                     border-radius: 10px; font-size: 12px; font-weight: bold; padding: 2px 10px; }
                #x:hover { background: #ff8fc7; color: white; }
                #body { background: #fffdfd; color: #5b2340; border: 2px solid #f3c6dd;
                        border-radius: 12px; font-size: 13px; }
                #spin { height: 8px; border: none; background: transparent; }
                #spin::chunk { background: #ff8fc7; border-radius: 4px; }
                #status { color: #b07a9b; font-size: 11px; }
                #btn { background: white; color: #5b2340; border: 3px solid #c9b6ff;
                       border-radius: 14px; padding: 7px 14px; font-weight: 700; }
                #btn:hover { background: #efe8ff; }
                #btnPri { background: #ff8fc7; color: white; border: 3px solid #5b2340;
                          border-radius: 14px; padding: 7px 16px; font-weight: 900; }
                #btnPri:hover { background: #ff5c8a; }
                #modelCombo { background: white; color: #5b2340; border: 2px solid #f3c6dd;
                              border-radius: 10px; font-size: 11px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: white; color: #5b2340;
                              selection-background-color: #ff8fc7; selection-color: white; }
                #floater { font-size: 20px; }
                """,
    },
    "overstim": {
        "label": "Sensory Overload",
        "title": "\u26a1 WOW RESULTS \u26a1", "dot": "\u25c9",
        "min_w": 560, "max_w": 620, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "ticker": True,
        "ticker_text": "\u2728 FRESH \u2726 100% AI \u2726 NO HUMANS \u2726 WOW \u2726 PIXELS DETECTED \u2726 BREAKING: SCREENSHOT ANALYZED \u2726 ",
        "note_top": "\u2728 FRESH \u00b7 100% AI \u00b7 NO HUMANS \u00b7 LIVE \u25cf viewrs: 1337",
        "buttons": ("GRAB IT", "RECEIPTS", "BYEEE"),
        "status_ok": "served fresh \u00b7 saved to analyses.md",
        "qss": """
                #card { background: rgba(10,10,14,246); border: 2px solid #b6ff2e;
                        border-radius: 12px; }
                #dot { color: #ff2fb3; font-size: 15px; }
                #title { color: #ffe94d; font-size: 15px; font-weight: 900; letter-spacing: 1px; }
                #x { background: #ff2fb3; color: white; border: none;
                     font-size: 12px; font-weight: bold; padding: 2px 10px; border-radius: 6px; }
                #tear { color: #00e5ff; font-family: Consolas, monospace; font-size: 11px; }
                #ticker { color: #b6ff2e; font-family: Consolas, monospace;
                          font-size: 12px; font-weight: bold; }
                #body { background: #f5f2ea; color: #1c1c22; border: 2px solid #ffe94d;
                        border-radius: 8px; font-size: 13px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #ff2fb3; }
                #status { color: #8b96b0; font-size: 11px; }
                #btn { background: #00e5ff; color: #062a2e; border: none;
                       border-radius: 8px; padding: 8px 14px; font-weight: 900; }
                #btnPri { background: #ff2fb3; color: white; border: none;
                          border-radius: 8px; padding: 8px 16px; font-weight: 900; }
                #modelCombo { background: #1a1a22; color: #ffe94d; border: 1px solid #b6ff2e;
                              border-radius: 6px; font-size: 11px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: #1a1a22; color: #ffe94d; }
                """,
    },
    "doge": {
        "label": "Doge",
        "title": "much results. wow.", "dot": "\u25cf",
        "min_w": 400, "max_w": 480, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("wow", "tr", 14, 8, -10, "#7a4fd0"),
                     ("such pixels", "tl", 12, 40, 7, "#2e7d32"),
                     ("very analyze", "bl", 14, 36, -6, "#c75400"),
                     ("much results", "br", 16, 64, 9, "#1565c0")],
        "buttons": ("pls copy", "such log", "wow close"),
        "status_ok": "such saved. wow.",
        "qss": """
                #card { background: #f4ecd8; border: 2px solid #6b4a2f; border-radius: 10px; }
                #dot { color: #6b4a2f; font-size: 14px; }
                #title { color: #6b4a2f; font-size: 14px; font-weight: bold;
                         font-family: "Comic Sans MS", cursive; }
                #x { background: transparent; color: #6b4a2f; border: none; font-size: 13px; }
                #body { background: #faf6ea; color: #3d2f23; border: 1px solid #d8b078;
                        border-radius: 6px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #6b4a2f; }
                #status { color: #8a7a5f; font-size: 11px; font-family: "Comic Sans MS", cursive; }
                #btn { background: #e8d5ae; color: #3d2f23; border: 2px solid #6b4a2f;
                       border-radius: 8px; padding: 6px 12px; }
                #btnPri { background: #6b4a2f; color: #faf6ea; border: none;
                          border-radius: 8px; padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: #faf6ea; color: #3d2f23; border: 1px solid #d8b078;
                              border-radius: 6px; font-size: 11px; max-width: 200px; }
                #floater { font-family: "Comic Sans MS", cursive; font-size: 15px; }
                """,
    },
    "amogus": {
        "label": "Emergency Meeting",
        "title": "EMERGENCY MEETING", "dot": "\u26a0",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "alarm": True, "alarm_text": "\u26a0 EMERGENCY MEETING \u26a0",
        "buttons": ("Skip Vote", "Call Log", "EJECT"),
        "status_ok": "meeting adjourned \u00b7 1 impostor was the screenshot \u00b7 saved",
        "qss": """
                #card { background: #16181d; border: 3px solid #c51111; border-radius: 8px; }
                #dot { color: #c51111; font-size: 16px; }
                #title { color: #ffffff; font-size: 16px; font-weight: 900; letter-spacing: 2px; }
                #x { background: #c51111; color: white; border: none;
                     font-size: 13px; font-weight: bold; padding: 2px 10px; }
                #alarm { font-size: 14px; font-weight: 900; letter-spacing: 2px; border-radius: 4px; }
                #body { background: #0c0e11; color: #e8ecf4; border: 1px solid #3a3f47;
                        border-radius: 6px; font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #c51111; }
                #status { color: #8b96b0; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: #22262c; color: #e8ecf4; border: 2px solid #3a3f47;
                       border-radius: 6px; padding: 8px 14px; font-weight: bold; }
                #btnPri { background: #c51111; color: white; border: none;
                          border-radius: 6px; padding: 8px 16px; font-weight: 900; }
                #btnPri:hover { background: #e01b1b; }
                #modelCombo { background: #22262c; color: #e8ecf4; border: 1px solid #3a3f47;
                              border-radius: 4px; font-family: Consolas, monospace;
                              font-size: 11px; max-width: 210px; }
                #modelCombo QAbstractItemView { background: #22262c; color: #e8ecf4; }
                """,
    },
    "e404": {
        "label": "404 Theme Not Found",
        "title": "the theme you requested could not be found", "dot": "?",
        "min_w": 420, "max_w": 480, "opacity": 0.96,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "404",
        "buttons": ("Report Issue", "Server Log", "Go Back"),
        "status_ok": "200 OK (ironic) \u00b7 saved to analyses.md",
        "status_err": "500 actually \u00b7 attempt logged",
        "qss": """
                #card { background: #2b2f36; border: 1px solid #e8a33d; border-radius: 8px; }
                #dot { color: #e8a33d; font-size: 14px; }
                #title { color: #e8e4de; font-size: 13px; }
                #x { background: transparent; color: #8b96b0; border: none; font-size: 13px; }
                #tear { color: #e8a33d; font-size: 44px; font-weight: 900;
                        font-family: Consolas, monospace; }
                #body { background: #1c1f24; color: #e8e4de; border: 1px solid #3a3f47;
                        border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #e8a33d; }
                #status { color: #8b96b0; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #e8e4de; border: 1px solid #3a3f47;
                       border-radius: 6px; padding: 6px 12px; }
                #btnPri { background: #e8a33d; color: #1c1f24; border: none;
                          border-radius: 6px; padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: #1c1f24; color: #e8e4de; border: 1px solid #3a3f47;
                              border-radius: 4px; font-size: 11px; max-width: 210px; }
                #modelCombo QAbstractItemView { background: #1c1f24; color: #e8e4de; }
                """,
    },
    "comic": {
        "label": "Comic Sans-ational",
        "title": "RE: YOUR SCREENSHOT \u2014 FINDINGS (FORMAL-ish)", "dot": "\u00a7",
        "min_w": 420, "max_w": 500, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("CERTIFIED SILLY", "br", 16, 56, -14, "#c0392b")],
        "buttons": ("Noted!!", "File Away", "Sign Off"),
        "qss": """
                #card { background: #f7f1de; border: 1px solid #b8ab7e; border-radius: 4px; }
                #dot { color: #33302a; font-size: 14px; }
                #title { color: #33302a; font-size: 13px; font-weight: bold;
                         font-family: "Comic Sans MS", cursive; }
                #x { background: transparent; color: #33302a; border: none;
                     font-family: "Comic Sans MS", cursive; }
                #body { background: #fdfaf0; color: #33302a; border: none;
                        border-top: 2px solid #b8ab7e;
                        font-family: "Comic Sans MS", cursive; font-size: 12pt; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #b8ab7e; }
                #status { color: #7a6f52; font-size: 11px; font-family: "Comic Sans MS", cursive; }
                #btn { background: transparent; color: #33302a;
                       border: 2px solid #b8ab7e; border-radius: 8px;
                       font-family: "Comic Sans MS", cursive; padding: 6px 12px; }
                #btnPri { background: #33302a; color: #fdfaf0; border: none;
                          border-radius: 8px; font-family: "Comic Sans MS", cursive;
                          padding: 6px 14px; }
                #modelCombo { background: #fdfaf0; color: #33302a; border: 1px solid #b8ab7e;
                              border-radius: 6px; font-family: "Comic Sans MS", cursive;
                              font-size: 11px; max-width: 200px; }
                #floater { font-family: "Comic Sans MS", cursive; font-size: 18px; }
                """,
    },
    "bug": {
        "label": "It's Not a Bug",
        "title": "ISSUE #404 \u2014 screenshot observed", "dot": "\u25cf",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "[wontfix] [works-on-my-machine] assignee: you",
        "buttons": ("Copy trace", "Ticket log", "Close issue"),
        "status_ok": "marked as completed \u00b7 saved to analyses.md",
        "status_err": "reopened \u00b7 attempt logged",
        "qss": """
                #card { background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; }
                #dot { color: #1a7f37; font-size: 13px; }
                #title { color: #1f2328; font-size: 14px; font-weight: 700; }
                #x { background: transparent; color: #59636e; border: none; font-size: 13px; }
                #tear { color: #59636e; font-size: 11px; font-family: Consolas, monospace; }
                #body { background: #f6f8fa; color: #1f2328; border: 1px solid #d0d7de;
                        border-radius: 6px; font-size: 13px; }
                #spin { height: 5px; border: none; background: #f6f8fa; }
                #spin::chunk { background: #0969da; }
                #status { color: #59636e; font-size: 11px; }
                #btn { background: #f6f8fa; color: #1f2328; border: 1px solid #d0d7de;
                       border-radius: 6px; padding: 6px 12px; }
                #btn:hover { background: #eef1f4; }
                #btnPri { background: #1a7f37; color: white; border: none;
                          border-radius: 6px; padding: 6px 14px; font-weight: 600; }
                #modelCombo { background: #f6f8fa; color: #1f2328; border: 1px solid #d0d7de;
                              border-radius: 6px; font-size: 11px; max-width: 210px; }
                """,
    },
    "crt": {
        "label": "CRT Phosphor",
        "title": "C:\\SS>", "dot": ">",
        "min_w": 480, "max_w": 540, "opacity": 0.97,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "scan": True,
        "buttons": ("[copy]", "[log]", "[exit]"),
        "qss": """
                #card { background: #0a0f0a; border: 1px solid #1e3a1e; border-radius: 10px; }
                #dot { color: #33ff66; font-size: 14px; }
                #title { color: #33ff66; font-size: 13px; font-family: Consolas, monospace;
                         font-weight: bold; }
                #x { background: transparent; color: #1e5a1e; border: none;
                     font-family: Consolas, monospace; }
                #x:hover { color: #33ff66; }
                #body { background: transparent; color: #33ff66; border: none;
                        font-family: Consolas, monospace; font-size: 13px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #33ff66; }
                #status { color: #1e5a1e; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #1e7a1e; border: none;
                       font-family: Consolas, monospace; }
                #btn:hover { color: #33ff66; }
                #btnPri { background: transparent; color: #33ff66; border: 1px solid #1e5a1e;
                          border-radius: 4px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 12px; }
                #modelCombo { background: #0a0f0a; color: #33ff66; border: 1px solid #1e5a1e;
                              border-radius: 4px; font-family: Consolas, monospace;
                              font-size: 11px; max-width: 210px; }
                #modelCombo QAbstractItemView { background: #0a0f0a; color: #33ff66; }
                """,
    },
    "blueprint": {
        "label": "Blueprint",
        "title": "FIELD DRAWING // SS-01", "dot": "\u2316",
        "min_w": 460, "max_w": 540, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "DWG NO. SS-01 \u00b7 SCALE 1:1 \u00b7 GRID 4PX \u00b7 SHEET 1/1",
        "buttons": ("REV A \u2014 Copy", "Archive", "Approve"),
        "status_ok": "checked \u00b7 scale verified \u00b7 saved",
        "qss": """
                #card { background: #1e4d8c; border: 2px solid #ffffff; border-radius: 2px; }
                #dot { color: #ffffff; font-size: 14px; }
                #title { color: #ffffff; font-size: 13px; font-weight: 700;
                         letter-spacing: 2px; font-family: Consolas, monospace; }
                #x { background: transparent; color: #9dbfe8; border: 1px solid #ffffff;
                     font-family: Consolas, monospace; padding: 2px 10px; }
                #x:hover { background: #ffffff; color: #1e4d8c; }
                #tear { color: #9dbfe8; font-size: 10px; font-family: Consolas, monospace;
                        letter-spacing: 1px; }
                #body { background: #1a457e; color: #ffffff; border: 1px dashed #9dbfe8;
                        border-radius: 0px; font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #ffffff; }
                #status { color: #9dbfe8; font-size: 10px; font-family: Consolas, monospace;
                          letter-spacing: 1px; }
                #btn { background: transparent; color: #ffffff; border: 1px solid #ffffff;
                       border-radius: 0px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btn:hover { background: rgba(255,255,255,25); }
                #btnPri { background: #ffffff; color: #1e4d8c; border: none;
                          border-radius: 0px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #1a457e; color: #ffffff; border: 1px solid #9dbfe8;
                              border-radius: 0px; font-family: Consolas, monospace;
                              font-size: 11px; max-width: 220px; }
                #modelCombo QAbstractItemView { background: #1a457e; color: #ffffff; }
                """,
    },
    "noir": {
        "label": "Noir Typewriter",
        "title": "CASE FILE \u2014 {model}", "dot": "\u2767",
        "min_w": 420, "max_w": 500, "opacity": 1.0,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("File It", "Evidence", "Close Case"),
        "status_ok": "case closed \u00b7 filed",
        "qss": """
                #card { background: #e8dcc0; border: 1px solid #5a4a32; border-radius: 2px; }
                #dot { color: #a33b2e; font-size: 14px; }
                #title { color: #2a241d; font-size: 13px; font-weight: bold;
                         font-family: "Courier New", monospace; letter-spacing: 2px; }
                #x { background: transparent; color: #2a241d; border: none;
                     font-family: "Courier New", monospace; }
                #body { background: #f0e6cc; color: #2a241d; border: none;
                        border-top: 2px solid #2a241d;
                        font-family: "Courier New", monospace; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #2a241d; }
                #status { color: #6b5d43; font-size: 11px; font-family: "Courier New", monospace; }
                #btn { background: transparent; color: #2a241d; border: 2px solid #2a241d;
                       border-radius: 0px; font-family: "Courier New", monospace; padding: 6px 12px; }
                #btnPri { background: #2a241d; color: #f0e6cc; border: none;
                          border-radius: 0px; font-family: "Courier New", monospace; padding: 6px 14px; }
                #modelCombo { background: #f0e6cc; color: #2a241d; border: 1px solid #5a4a32;
                              font-family: "Courier New", monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "arcade": {
        "label": "Arcade Cabinet",
        "title": "\u2605 SS ANALYZER \u2605", "dot": "\u25cf",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u2605 \u2605 \u2605 INSERT COIN \u2605 \u2605 \u2605",
        "buttons": ("1P START", "HI-SCORE", "GAME OVER"),
        "status_ok": "1UP \u00b7 saved",
        "qss": """
                #card { background: #0a0a10; border: 3px solid #ff2fb3; border-radius: 16px; }
                #dot { color: #00e5ff; font-size: 14px; }
                #title { color: #ffffff; font-size: 16px; font-weight: 900; letter-spacing: 3px; }
                #x { background: #ff2fb3; color: white; border: none;
                     font-size: 12px; font-weight: bold; padding: 2px 10px; border-radius: 8px; }
                #tear { color: #00e5ff; font-size: 11px; letter-spacing: 2px; }
                #body { background: #050508; color: #e8ecf4; border: 2px solid #00e5ff;
                        border-radius: 8px; font-size: 13px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #ff2fb3; }
                #status { color: #8b96b0; font-size: 11px; }
                #btn { background: #f7d51d; color: #0a0a10; border: none;
                       border-radius: 14px; padding: 8px 14px; font-weight: 900; }
                #btnPri { background: #e01b1b; color: white; border: none;
                          border-radius: 14px; padding: 8px 16px; font-weight: 900; }
                #modelCombo { background: #050508; color: #00e5ff; border: 1px solid #ff2fb3;
                              border-radius: 8px; font-size: 11px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: #050508; color: #00e5ff; }
                """,
    },
    "zen": {
        "label": "Zen Garden",
        "title": "still water", "dot": "\u25cb",
        "min_w": 440, "max_w": 520, "opacity": 0.96,
        "reveal": "instant", "footer": "hover", "autohide": 0, "tear": False,
        "buttons": ("Copy", "Log", "Close"),
        "status_ok": "pixels settle \u00b7 saved",
        "qss": """
                #card { background: #faf8f2; border: 1px solid rgba(74,103,65,120);
                        border-radius: 6px; }
                #dot { color: #4a6741; font-size: 12px; }
                #title { color: #4a6741; font-size: 13px; font-weight: 300; letter-spacing: 4px; }
                #x { background: transparent; color: #9aa893; border: none; font-size: 12px; }
                #body { background: transparent; color: #2e362b; border: none;
                        font-size: 14px; }
                #spin { height: 3px; border: none; background: transparent; }
                #spin::chunk { background: #4a6741; }
                #status { color: #9aa893; font-size: 11px; }
                #btn { background: transparent; color: #4a6741; border: 1px solid #b9c4b2;
                       border-radius: 8px; padding: 8px 16px; }
                #btnPri { background: #4a6741; color: #faf8f2; border: none;
                          border-radius: 8px; padding: 8px 18px; }
                #modelCombo { background: transparent; color: #6b7a64;
                              border: 1px solid #d5dcd0; border-radius: 6px;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "solar": {
        "label": "Solarized Lab",
        "title": "CALIBRATION \u2014 {model}", "dot": "\u25c8",
        "min_w": 440, "max_w": 520, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Sample", "Record", "Seal"),
        "status_ok": "\u00b10.0 fluff \u00b7 calibrated \u00b7 saved",
        "qss": """
                #card { background: #fdf6e3; border: 1px solid #93a1a1; border-radius: 4px; }
                #dot { color: #268bd2; font-size: 13px; }
                #title { color: #586e75; font-size: 13px; font-weight: bold; letter-spacing: 2px;
                         font-family: Consolas, monospace; }
                #x { background: transparent; color: #93a1a1; border: none; }
                #body { background: #eee8d5; color: #073642; border: 1px solid #93a1a1;
                        border-radius: 3px; font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 5px; border: none; background: #eee8d5; }
                #spin::chunk { background: #268bd2; }
                #status { color: #93a1a1; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: #eee8d5; color: #586e75; border: 1px solid #93a1a1;
                       border-radius: 3px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: #268bd2; color: #fdf6e3; border: none;
                          border-radius: 3px; font-family: Consolas, monospace; padding: 6px 14px; }
                #modelCombo { background: #eee8d5; color: #586e75; border: 1px solid #93a1a1;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 210px; }
                """,
    },
    "ada": {
        "label": "High-Contrast ADA",
        "title": "HIGH CONTRAST", "dot": "\u25c9",
        "min_w": 520, "max_w": 620, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("COPY", "LOG", "CLOSE"),
        "qss": """
                #card { background: #000000; border: 3px solid #ffd800; border-radius: 4px; }
                #dot { color: #ffd800; font-size: 16px; }
                #title { color: #ffd800; font-size: 17px; font-weight: 900; letter-spacing: 2px; }
                #x { background: #ffd800; color: #000000; border: none;
                     font-size: 15px; font-weight: 900; padding: 4px 14px; }
                #body { background: #000000; color: #ffffff; border: 2px solid #ffd800;
                        border-radius: 2px; font-size: 16px; font-weight: bold; }
                #spin { height: 8px; border: 2px solid #ffd800; background: #000000; }
                #spin::chunk { background: #ffd800; }
                #status { color: #ffd800; font-size: 13px; font-weight: bold; }
                #btn { background: #000000; color: #ffd800; border: 3px solid #ffd800;
                       border-radius: 4px; font-size: 15px; font-weight: 900; padding: 12px 18px; }
                #btnPri { background: #ffd800; color: #000000; border: none;
                          border-radius: 4px; font-size: 15px; font-weight: 900; padding: 12px 20px; }
                #modelCombo { background: #000000; color: #ffffff; border: 2px solid #ffd800;
                              font-size: 13px; max-width: 240px; }
                #modelCombo QAbstractItemView { background: #000000; color: #ffffff;
                              selection-background-color: #ffd800; selection-color: #000000; }
                """,
    },
    "win95": {
        "label": "Win95 Chrome",
        "title": "SS Analyzer", "dot": "\u25a0",
        "min_w": 400, "max_w": 500, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Copy", "View Log", "Close"),
        "note_bot": "Ready",
        "qss": """
                #card { background: #c0c0c0; border: 2px solid;
                        border-color: #ffffff #404040 #404040 #ffffff; border-radius: 0px; }
                #dot { color: #000080; font-size: 12px; }
                #title { background: #000080; color: #ffffff; font-size: 12px; font-weight: bold;
                         padding: 3px 6px; }
                #x { background: #c0c0c0; color: #000000; border: 2px solid;
                     border-color: #ffffff #404040 #404040 #ffffff; font-size: 11px;
                     font-weight: bold; padding: 0px 8px; }
                #body { background: #ffffff; color: #000000; border: 2px solid;
                        border-color: #404040 #ffffff #ffffff #404040; border-radius: 0px;
                        font-size: 12px; }
                #spin { height: 12px; border: 2px solid;
                        border-color: #404040 #ffffff #ffffff #404040; background: #ffffff; }
                #spin::chunk { background: #000080; }
                #status { color: #000000; font-size: 11px; }
                #tear { color: #000000; font-size: 11px; }
                #btn { background: #c0c0c0; color: #000000; border: 2px solid;
                       border-color: #ffffff #404040 #404040 #ffffff; border-radius: 0px;
                       padding: 5px 14px; }
                #btnPri { background: #c0c0c0; color: #000000; border: 2px solid;
                          border-color: #ffffff #404040 #404040 #ffffff; border-radius: 0px;
                          font-weight: bold; padding: 5px 16px; }
                #modelCombo { background: #ffffff; color: #000000; border: 2px solid;
                              border-color: #404040 #ffffff #ffffff #404040;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "holo": {
        "label": "Hologram",
        "title": "\u25e4 SCAN // SS-ANALYZER", "dot": "\u25c8",
        "min_w": 420, "max_w": 520, "opacity": 0.94,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "scan": True,
        "buttons": ("[ COPY ]", "[ LOG ]", "[ CLOSE ]"),
        "status_ok": "scan complete \u00b7 holo-stable \u00b7 saved",
        "qss": """
                #card { background: rgba(5,10,20,242); border: 1px solid #7df9ff;
                        border-radius: 2px; }
                #dot { color: #7df9ff; font-size: 14px; }
                #title { color: #7df9ff; font-size: 13px; letter-spacing: 3px;
                         font-family: Consolas, monospace; }
                #x { background: transparent; color: #3d7a86; border: 1px solid #7df9ff;
                     font-size: 12px; padding: 2px 8px; }
                #body { background: transparent; color: #eaf6ff; border: 1px solid rgba(125,249,255,90);
                        font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #7df9ff; }
                #status { color: #3d7a86; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #7df9ff; border: 1px solid #7df9ff;
                       font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: rgba(125,249,255,40); color: #eaf6ff;
                          border: 1px solid #7df9ff; font-family: Consolas, monospace;
                          padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: transparent; color: #7df9ff; border: 1px solid #2a5a62;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 210px; }
                #modelCombo QAbstractItemView { background: #050a14; color: #7df9ff; }
                """,
    },
    "field": {
        "label": "Field Notes",
        "title": "FIELD NOTES \u270e {model}", "dot": "\u2605",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Clip It", "File It", "Close Book"),
        "status_ok": "\u2605 important \u00b7 saved",
        "qss": """
                #card { background: #fff3a3; border: 1px solid #c9a227; border-radius: 2px; }
                #dot { color: #c0392b; font-size: 14px; }
                #title { color: #33302a; font-size: 14px; font-weight: bold; }
                #x { background: transparent; color: #33302a; border: none; font-size: 13px; }
                #body { background: #fff9c9; color: #33302a;
                        border: none; border-left: 3px solid #e88a8a;
                        font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #c9a227; }
                #status { color: #7a6f52; font-size: 11px; }
                #btn { background: #fffdf0; color: #33302a; border: 2px solid #c9a227;
                       border-radius: 10px; padding: 6px 12px; }
                #btnPri { background: #33302a; color: #fff9c9; border: none;
                          border-radius: 10px; padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: #fffdf0; color: #33302a; border: 1px solid #c9a227;
                              border-radius: 8px; font-size: 11px; max-width: 200px; }
                """,
    },
    "elden": {
        "label": "Elden Ring",
        "title": "\u2726 GUIDED BY GRACE", "dot": "\u2726",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u2500\u2500 TRANSMITTED VIA GRACE \u2500\u2500",
        "buttons": ("Read Message", "Leave Message", "Close"),
        "status_ok": "message appraised \u00b7 saved",
        "status_err": "YOU DIED \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(14,13,11,246); border: 1px solid #c9a227;
                        border-radius: 2px; }
                #dot { color: #c9a227; font-size: 14px; }
                #title { color: #e5c15d; font-size: 14px; letter-spacing: 3px;
                         font-family: Georgia, serif; }
                #x { background: transparent; color: #8a7a4a; border: 1px solid #6b5f2e;
                     font-size: 12px; padding: 2px 8px; }
                #tear { color: #6b5f2e; font-size: 10px; letter-spacing: 2px; }
                #body { background: transparent; color: #ded5bd; border: none;
                        border-top: 1px solid #6b5f2e; font-family: Georgia, serif;
                        font-size: 13.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #c9a227; }
                #status { color: #8a7a4a; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: transparent; color: #ded5bd; border: 1px solid #6b5f2e;
                       font-family: Georgia, serif; padding: 7px 14px; }
                #btn:hover { background: rgba(201,162,39,30); }
                #btnPri { background: #4a0d0d; color: #e8b4b4; border: 1px solid #8a0303;
                          font-family: Georgia, serif; padding: 7px 16px; }
                #modelCombo { background: #0e0d0b; color: #ded5bd; border: 1px solid #6b5f2e;
                              font-family: Georgia, serif; font-size: 11px; max-width: 210px; }
                #modelCombo QAbstractItemView { background: #0e0d0b; color: #ded5bd; }
                """,
    },
    "hollow": {
        "label": "Hollow Knight",
        "title": "\u2756 ECHOES OF HALLONEST", "dot": "\u2756",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Focus", "Dream Nail", "Rest"),
        "status_ok": "soul refilled \u00b7 saved",
        "qss": """
                #card { background: rgba(10,14,26,246); border: 1px solid #3d4a6b;
                        border-radius: 12px; }
                #dot { color: #e8e8e8; font-size: 13px; }
                #title { color: #e8e8e8; font-size: 14px; letter-spacing: 4px;
                         font-family: Georgia, serif; }
                #x { background: transparent; color: #5f7396; border: none; font-size: 13px; }
                #body { background: transparent; color: #cfd8ea; border: none;
                        border-top: 1px solid #3d4a6b; font-family: Georgia, serif;
                        font-size: 13.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #7fd4c1; }
                #status { color: #5f7396; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: transparent; color: #cfd8ea; border: 1px solid #3d4a6b;
                       border-radius: 8px; font-family: Georgia, serif; padding: 7px 14px; }
                #btnPri { background: #e8e8e8; color: #0a0e1a; border: none;
                          border-radius: 8px; font-family: Georgia, serif;
                          font-weight: bold; padding: 7px 16px; }
                #modelCombo { background: #0a0e1a; color: #cfd8ea; border: 1px solid #3d4a6b;
                              border-radius: 6px; font-size: 11px; max-width: 200px; }
                """,
    },
    "sekiro": {
        "label": "Sekiro",
        "title": "\u96bb\u72fc SHADOWS DIE TWICE", "dot": "\u6b7b",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Strike", "Deflect", "Resurrect"),
        "status_ok": "posture intact \u00b7 saved",
        "status_err": "\u6b7b \u2014 hesitation is defeat \u00b7 logged",
        "qss": """
                #card { background: rgba(13,13,15,246); border: none;
                        border-left: 4px solid #b3122e; border-radius: 0px; }
                #dot { color: #b3122e; font-size: 16px; font-weight: 900; }
                #title { color: #ece8df; font-size: 14px; font-weight: bold; letter-spacing: 3px; }
                #x { background: transparent; color: #6e6a60; border: none; font-size: 13px; }
                #body { background: transparent; color: #ece8df; border: none;
                        font-size: 13px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #b3122e; }
                #status { color: #6e6a60; font-size: 11px; letter-spacing: 1px; }
                #btn { background: transparent; color: #ece8df; border: 1px solid #4a4640;
                       border-radius: 0px; padding: 7px 14px; letter-spacing: 1px; }
                #btnPri { background: #b3122e; color: #ffffff; border: none;
                          border-radius: 0px; padding: 7px 16px; font-weight: bold; }
                #modelCombo { background: #0d0d0f; color: #ece8df; border: 1px solid #4a4640;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "minecraft": {
        "label": "Minecraft",
        "title": "\u2593 SS CRAFT \u2014 {model}", "dot": "\u25a0",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("100% BLOCKY!", "tr", 8, 6, -12, "#ffff54")],
        "buttons": ("Mine", "Craft", "Quit Game"),
        "status_ok": "achievement get! \u00b7 saved",
        "qss": """
                #card { background: rgba(16,12,8,245); border: 2px solid #000000;
                        border-radius: 0px; }
                #dot { color: #4caf50; font-size: 14px; }
                #title { color: #ffffff; font-size: 13px; font-family: Consolas, monospace; }
                #x { background: #707070; color: #ffffff; border: 2px solid #000000;
                     font-family: Consolas, monospace; font-size: 11px; padding: 0px 8px; }
                #body { background: rgba(0,0,0,120); color: #ffffff;
                        border: 2px solid #000000; border-radius: 0px;
                        font-family: Consolas, monospace; font-size: 12px; }
                #spin { height: 8px; border: 2px solid #000000; background: #1a1a1a; }
                #spin::chunk { background: #4caf50; }
                #status { color: #aaaaaa; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: #707070; color: #ffffff; border: 2px solid #000000;
                       border-radius: 0px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btn:hover { background: #5f7fd6; }
                #btnPri { background: #4caf50; color: #ffffff; border: 2px solid #000000;
                          border-radius: 0px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #000000; color: #ffffff; border: 2px solid #000000;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                #floater { color: #ffff54; font-family: Consolas, monospace; font-size: 14px; }
                """,
    },
    "pokefrlg": {
        "label": "Pok\u00e9dex FRLG",
        "title": "\u25c9 POK\u00e9DEX v1.0", "dot": "\u25cf",
        "min_w": 400, "max_w": 460, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_bot": "\u25bc A: continue",
        "buttons": ("DATA", "CRY", "CLOSE"),
        "status_ok": "registered! \u00b7 saved",
        "qss": """
                #card { background: #f8f8f8; border: 3px solid #1c2c5c; border-radius: 10px; }
                #dot { color: #e03030; font-size: 14px; }
                #title { color: #1c2c5c; font-size: 13px; font-weight: bold;
                         font-family: Consolas, monospace; letter-spacing: 1px; }
                #x { background: #e03030; color: #ffffff; border: 2px solid #1c2c5c;
                     border-radius: 6px; font-size: 11px; font-weight: bold; padding: 0px 8px; }
                #body { background: #ffffff; color: #202020; border: 2px solid #1c2c5c;
                        border-radius: 6px; font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #e03030; }
                #status { color: #5a6a8a; font-size: 11px; font-family: Consolas, monospace; }
                #tear { color: #5a6a8a; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: #e8ecf4; color: #1c2c5c; border: 2px solid #1c2c5c;
                       border-radius: 6px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: #e03030; color: #ffffff; border: 2px solid #1c2c5c;
                          border-radius: 6px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #ffffff; color: #1c2c5c; border: 2px solid #1c2c5c;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 190px; }
                """,
    },
    "gtavc": {
        "label": "GTA Vice City",
        "title": "\u2600 VICE CITY \u2014 {model}", "dot": "\u2600",
        "min_w": 420, "max_w": 500, "opacity": 0.96,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u00b7 \u00b7 \u00b7 OCEAN DRIVE \u00b7 1986 \u00b7 \u00b7 \u00b7",
        "buttons": ("Replay", "Stats", "Change Disk"),
        "status_ok": "mission passed! \u00b7 saved",
        "qss": """
                #card { background: rgba(13,11,38,246); border: 2px solid #ff9ecb;
                        border-radius: 12px; }
                #dot { color: #ff9ecb; font-size: 15px; }
                #title { color: #ffd7ec; font-size: 16px; font-weight: 900; letter-spacing: 2px; }
                #x { background: #ff9ecb; color: #0d0b26; border: none;
                     font-size: 12px; font-weight: bold; padding: 2px 10px; border-radius: 8px; }
                #tear { color: #4de3c2; font-size: 10px; letter-spacing: 3px; }
                #body { background: rgba(0,0,0,110); color: #f2ecff; border: 1px solid #4de3c2;
                        border-radius: 8px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                              stop:0 #ff9ecb, stop:1 #4de3c2); }
                #status { color: #8f86b8; font-size: 11px; }
                #btn { background: transparent; color: #ffd7ec; border: 2px solid #4de3c2;
                       border-radius: 10px; padding: 7px 14px; font-weight: bold; }
                #btnPri { background: #ff9ecb; color: #0d0b26; border: none;
                          border-radius: 10px; padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #0d0b26; color: #ffd7ec; border: 1px solid #ff9ecb;
                              border-radius: 8px; font-size: 11px; max-width: 200px; }
                """,
    },
    "gtasa": {
        "label": "GTA San Andreas",
        "title": "\u2605 GROVE STREET \u2014 {model}", "dot": "\u2605",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "SAN ANDREAS \u00b7 1992 \u00b7 WEST COAST",
        "buttons": ("Respect+", "Stats", "Busted"),
        "status_ok": "mission passed \u00b7 respect+ \u00b7 saved",
        "status_err": "busted \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(12,12,12,246); border: 3px solid #3fa34d;
                        border-radius: 4px; }
                #dot { color: #3fa34d; font-size: 15px; }
                #title { color: #ffffff; font-size: 16px; font-weight: 900; letter-spacing: 1px; }
                #x { background: #3fa34d; color: #0c0c0c; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #tear { color: #ff7b00; font-size: 10px; letter-spacing: 2px;
                        font-weight: bold; }
                #body { background: #111111; color: #f2f2f2; border: 1px solid #3fa34d;
                        font-size: 13px; }
                #spin { height: 6px; border: none; background: #111111; }
                #spin::chunk { background: #3fa34d; }
                #status { color: #ff7b00; font-size: 11px; font-weight: bold; }
                #btn { background: #1a1a1a; color: #ffffff; border: 2px solid #3fa34d;
                       padding: 7px 14px; font-weight: 900; }
                #btnPri { background: #ff7b00; color: #0c0c0c; border: none;
                          padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #1a1a1a; color: #ffffff; border: 1px solid #3fa34d;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "gta5": {
        "label": "GTA V",
        "title": "$ LOS SANTOS \u2014 {model}", "dot": "$",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Switch", "Stocks", "Busted"),
        "status_ok": "mission passed \u00b7 saved",
        "status_err": "busted \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(10,10,10,246); border: 2px solid #6abe30;
                        border-radius: 4px; }
                #dot { color: #6abe30; font-size: 15px; font-weight: 900; }
                #title { color: #ffffff; font-size: 17px; font-weight: 900; letter-spacing: 1px; }
                #x { background: #6abe30; color: #0a0a0a; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #body { background: #101010; color: #f2f2f2; border: 1px solid #2a2a2a;
                        font-size: 13px; }
                #spin { height: 6px; border: none; background: #101010; }
                #spin::chunk { background: #6abe30; }
                #status { color: #6abe30; font-size: 11px; font-weight: bold; }
                #btn { background: #161616; color: #ffffff; border: 2px solid #6abe30;
                       padding: 7px 14px; font-weight: 900; }
                #btnPri { background: #6abe30; color: #0a0a0a; border: none;
                          padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #161616; color: #ffffff; border: 1px solid #6abe30;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "jojo": {
        "label": "JoJo",
        "title": "\u30b8\u30e7\u30b8\u30e7 \u2014 STAND ANALYSIS", "dot": "\u2606",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u30b4", "tl", 8, 26, -12, "#c084ff"),
                     ("\u30b4", "tr", 8, 26, 12, "#c084ff"),
                     ("\u30b4", "br", 10, 70, 8, "#c084ff")],
        "buttons": ("ORAORA", "MUDA", "To Be Continued"),
        "status_ok": "to be continued\u2026 \u00b7 saved",
        "qss": """
                #card { background: rgba(22,10,46,246); border: 2px solid #ffd700;
                        border-radius: 6px; }
                #dot { color: #ffd700; font-size: 15px; }
                #title { color: #ffd700; font-size: 15px; font-weight: 900; letter-spacing: 2px; }
                #x { background: #ffd700; color: #160a2e; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #body { background: rgba(0,0,0,130); color: #f5ecff;
                        border: 1px solid #7a4fd0; border-radius: 4px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #ffd700; }
                #status { color: #a78bfa; font-size: 11px; font-style: italic; }
                #btn { background: transparent; color: #ffd700; border: 2px solid #ffd700;
                       padding: 7px 14px; font-weight: 900; font-style: italic; }
                #btnPri { background: #e62429; color: #ffffff; border: 2px solid #ffd700;
                          padding: 7px 16px; font-weight: 900; font-style: italic; }
                #modelCombo { background: #160a2e; color: #ffd700; border: 1px solid #7a4fd0;
                              font-size: 11px; max-width: 200px; }
                #floater { font-size: 24px; }
                """,
    },
    "cuphead": {
        "label": "Cuphead",
        "title": "\u266a CUPHEAD REVUE \u2014 {model}", "dot": "\u266a",
        "min_w": 420, "max_w": 500, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u00b7 IN LIVING TECHNICOLOR \u00b7",
        "buttons": ("Applaud", "Encore", "Exit Stage"),
        "status_ok": "a swell battle \u00b7 saved",
        "qss": """
                #card { background: #f5e6c8; border: 3px solid #2a1f14; border-radius: 12px; }
                #dot { color: #c1272d; font-size: 15px; }
                #title { color: #2a1f14; font-size: 15px; font-weight: 900;
                         font-family: Georgia, serif; letter-spacing: 1px; }
                #x { background: #c1272d; color: #f5e6c8; border: 2px solid #2a1f14;
                     border-radius: 8px; font-size: 12px; font-weight: bold; padding: 0px 8px; }
                #tear { color: #8a6f4d; font-size: 10px; letter-spacing: 2px; }
                #body { background: #faf0d7; color: #2a1f14; border: 2px solid #2a1f14;
                        border-radius: 8px; font-family: Georgia, serif; font-size: 13px; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #c1272d; }
                #status { color: #8a6f4d; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: #faf0d7; color: #2a1f14; border: 2px solid #2a1f14;
                       border-radius: 10px; font-family: Georgia, serif; padding: 6px 12px; }
                #btnPri { background: #c1272d; color: #faf0d7; border: 2px solid #2a1f14;
                          border-radius: 10px; font-family: Georgia, serif;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #faf0d7; color: #2a1f14; border: 2px solid #2a1f14;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "manga": {
        "label": "Manga",
        "title": "\u7b2c1\u8a71 \u2014 {model}", "dot": "\u25cf",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u30c9\u30f3!!", "tr", 6, 8, -10, "#000000")],
        "buttons": ("Next Page", "Bookmark", "Close Book"),
        "status_ok": "\u3064\u3065\u304f \u00b7 saved",
        "qss": """
                #card { background: #ffffff; border: 4px solid #000000; border-radius: 0px; }
                #dot { color: #000000; font-size: 13px; }
                #title { color: #000000; font-size: 15px; font-weight: 900; }
                #x { background: #000000; color: #ffffff; border: none;
                     font-size: 12px; font-weight: bold; padding: 2px 10px; }
                #body { background: #ffffff; color: #000000; border: 3px solid #000000;
                        border-radius: 0px; font-size: 13px; font-weight: 600; }
                #spin { height: 6px; border: 2px solid #000000; background: #ffffff; }
                #spin::chunk { background: #000000; }
                #status { color: #444444; font-size: 11px; }
                #btn { background: #ffffff; color: #000000; border: 3px solid #000000;
                       border-radius: 0px; padding: 6px 12px; font-weight: bold; }
                #btnPri { background: #000000; color: #ffffff; border: none;
                          border-radius: 0px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #ffffff; color: #000000; border: 2px solid #000000;
                              font-size: 11px; max-width: 200px; }
                #floater { font-size: 22px; }
                """,
    },
    "marvel": {
        "label": "Marvel",
        "title": "MARVEL \u2014 {model}", "dot": "M",
        "min_w": 420, "max_w": 500, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Excelsior!", "No-Prize", "Close"),
        "status_ok": "excelsior! \u00b7 saved",
        "qss": """
                #card { background: #ffffff; border: 3px solid #000000; border-radius: 4px; }
                #dot { color: #e62429; font-size: 15px; font-weight: 900; }
                #title { background: #e62429; color: #ffffff; font-size: 15px;
                         font-weight: 900; font-style: italic; padding: 4px 12px; letter-spacing: 1px; }
                #x { background: #000000; color: #ffffff; border: none;
                     font-size: 12px; font-weight: bold; padding: 2px 10px; }
                #body { background: #ffffff; color: #151515; border: 2px solid #000000;
                        font-size: 13px; font-weight: 600; }
                #spin { height: 6px; border: 2px solid #000000; background: #ffffff; }
                #spin::chunk { background: #e62429; }
                #status { color: #555555; font-size: 11px; font-style: italic; }
                #btn { background: #ffffff; color: #151515; border: 3px solid #000000;
                       padding: 6px 12px; font-weight: 900; font-style: italic; }
                #btnPri { background: #e62429; color: #ffffff; border: 3px solid #000000;
                          padding: 6px 14px; font-weight: 900; font-style: italic; }
                #modelCombo { background: #ffffff; color: #151515; border: 2px solid #000000;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "dc": {
        "label": "DC",
        "title": "\u25c9 DC \u2014 {model}", "dot": "\u25c9",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Copy", "Case File", "Close"),
        "status_ok": "justice logged \u00b7 saved",
        "qss": """
                #card { background: rgba(10,22,40,246); border: 2px solid #0078f0;
                        border-radius: 6px; }
                #dot { color: #0078f0; font-size: 15px; }
                #title { color: #e8edf3; font-size: 14px; font-weight: 900; letter-spacing: 3px; }
                #x { background: transparent; color: #7a8ba0; border: 1px solid #0078f0;
                     font-size: 12px; padding: 2px 8px; }
                #body { background: rgba(0,0,0,140); color: #e8edf3;
                        border: 1px solid #2a4a73; border-radius: 4px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #0078f0; }
                #status { color: #7a8ba0; font-size: 11px; }
                #btn { background: transparent; color: #e8edf3; border: 2px solid #0078f0;
                       border-radius: 4px; padding: 6px 12px; font-weight: bold; }
                #btnPri { background: #0078f0; color: #ffffff; border: none;
                          border-radius: 4px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #0a1628; color: #e8edf3; border: 1px solid #2a4a73;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "halo": {
        "label": "Halo",
        "title": "\u2b22 UNSC // {model}", "dot": "\u2b22",
        "min_w": 440, "max_w": 520, "opacity": 0.95,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "scan": True,
        "note_top": "CORTANA LINK: STABLE \u00b7 SHIELD 100%",
        "buttons": ("Spartan Copy", "Cortana Log", "Power Down"),
        "status_ok": "reclaimer acknowledged \u00b7 saved",
        "qss": """
                #card { background: rgba(11,15,12,244); border: 1px solid #6fd8e7;
                        border-radius: 3px; }
                #dot { color: #6fd8e7; font-size: 14px; }
                #title { color: #6fd8e7; font-size: 13px; letter-spacing: 3px;
                         font-family: Consolas, monospace; }
                #x { background: transparent; color: #4a6b54; border: 1px solid #6b7a3a;
                     font-size: 12px; font-family: Consolas, monospace; }
                #tear { color: #6b7a3a; font-size: 10px; font-family: Consolas, monospace;
                        letter-spacing: 1px; }
                #body { background: transparent; color: #d8e8d0;
                        border: 1px solid rgba(111,216,231,80);
                        font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #6fd8e7; }
                #status { color: #4a6b54; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #d8e8d0; border: 1px solid #6b7a3a;
                       font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: rgba(111,216,231,35); color: #eafcff;
                          border: 1px solid #6fd8e7; font-family: Consolas, monospace;
                          padding: 6px 14px; }
                #modelCombo { background: #0b0f0c; color: #d8e8d0; border: 1px solid #4a6b54;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "re": {
        "label": "Resident Evil",
        "title": "\u2623 WELCOME, STRANGER", "dot": "\u2623",
        "min_w": 420, "max_w": 500, "opacity": 0.98,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "REC \u25b6 SP 0:00:07 \u00b7 TRACKING OK",
        "buttons": ("Buy", "Sell", "Close"),
        "status_ok": "saved to the ribbon \u00b7 ink used",
        "status_err": "you are dead \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(5,5,5,250); border: 1px solid #3a0d0d;
                        border-radius: 2px; }
                #dot { color: #7a0c0c; font-size: 15px; }
                #title { color: #c9bda8; font-size: 13px; letter-spacing: 2px;
                         font-family: "Courier New", monospace; }
                #x { background: transparent; color: #5a5a5a; border: none;
                     font-family: "Courier New", monospace; }
                #tear { color: #7a0c0c; font-size: 10px; font-family: "Courier New", monospace;
                        letter-spacing: 1px; }
                #body { background: #000000; color: #c9c9c9; border: none;
                        border-top: 1px solid #3a0d0d;
                        font-family: "Courier New", monospace; font-size: 12.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #7a0c0c; }
                #status { color: #5a5a5a; font-size: 11px; font-family: "Courier New", monospace; }
                #btn { background: transparent; color: #c9c9c9; border: 1px solid #3a3a3a;
                       font-family: "Courier New", monospace; padding: 6px 12px; }
                #btnPri { background: #7a0c0c; color: #e8d8d8; border: none;
                          font-family: "Courier New", monospace; padding: 6px 14px; }
                #modelCombo { background: #000000; color: #c9c9c9; border: 1px solid #3a3a3a;
                              font-family: "Courier New", monospace; font-size: 11px;
                              max-width: 200px; }
                """,
    },
    "fnaf": {
        "label": "FNaF",
        "title": "\u2605 FREDDY'S \u2014 {model}", "dot": "\u25c9",
        "min_w": 420, "max_w": 500, "opacity": 0.98,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "NIGHT 1 \u00b7 12:00 AM \u00b7 POWER 98%",
        "buttons": ("Check Cams", "Wind Box", "6 AM"),
        "status_ok": "6 AM \u00b7 saved",
        "status_err": "it\u2019s me \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(8,6,12,250); border: 2px solid #5a3d8a;
                        border-radius: 4px; }
                #dot { color: #8a5cc9; font-size: 14px; }
                #title { color: #d8ccf0; font-size: 14px; font-weight: bold; letter-spacing: 2px;
                         font-family: Consolas, monospace; }
                #x { background: transparent; color: #5a4a73; border: 1px solid #5a3d8a;
                     font-size: 12px; }
                #tear { color: #8a5cc9; font-size: 10px; font-family: Consolas, monospace;
                        letter-spacing: 1px; }
                #body { background: #000000; color: #c9c9c9; border: 1px solid #2a2138;
                        font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #8a5cc9; }
                #status { color: #5a4a73; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: #141020; color: #d8ccf0; border: 1px solid #5a3d8a;
                       font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: #5a3d8a; color: #ffffff; border: none;
                          font-family: Consolas, monospace; padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: #000000; color: #d8ccf0; border: 1px solid #2a2138;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "fnf": {
        "label": "Friday Night Funkin'",
        "title": "FUNK FRIDAY \u2014 SICK!!", "dot": "\u26a1",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "eq": True,
        "floaters": [("\u25c0", "tl", 8, 24, 0, "#c24bff"),
                     ("\u25bc", "tr", 8, 24, 0, "#3dff3d"),
                     ("\u25b2", "bl", 8, 44, 0, "#ffff54"),
                     ("\u25b6", "br", 8, 44, 0, "#ff4d4d")],
        "buttons": ("Retry", "Freeplay", "Quit"),
        "status_ok": "SICK!! +350 \u00b7 saved",
        "qss": """
                #card { background: rgba(13,13,18,246); border: 2px solid #ffffff;
                        border-radius: 10px; }
                #dot { color: #ff4d4d; font-size: 15px; }
                #title { color: #ffffff; font-size: 16px; font-weight: 900; letter-spacing: 1px; }
                #x { background: #ff4d4d; color: white; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; border-radius: 8px; }
                #body { background: #0a0a0e; color: #f2f2f2; border: 2px solid #c24bff;
                        border-radius: 6px; font-size: 13px; font-weight: 600; }
                #spin { height: 6px; border: none; background: transparent; }
                #spin::chunk { background: #3dff3d; }
                #status { color: #8b96b0; font-size: 11px; font-weight: bold; }
                #btn { background: #1c1c26; color: #ffffff; border: 2px solid #12c4ff;
                       border-radius: 8px; padding: 7px 14px; font-weight: 900; }
                #btnPri { background: #3dff3d; color: #0d0d12; border: none;
                          border-radius: 8px; padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #0a0a0e; color: #ffffff; border: 1px solid #c24bff;
                              font-size: 11px; max-width: 200px; }
                #eqbar { background: #ff4d4d; border-radius: 2px; }
                #floater { font-size: 20px; }
                """,
    },
    "mario": {
        "label": "Super Mario",
        "title": "\u2605 SUPER SS \u2014 {model}", "dot": "?",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "? ? ?  BONUS ROOM  ? ? ?",
        "buttons": ("1-UP", "Save & Quit", "Game Over"),
        "status_ok": "course clear! \u00b7 saved",
        "qss": """
                #card { background: #5c94fc; border: 3px solid #000000; border-radius: 16px; }
                #dot { background: #f8b800; color: #000000; font-size: 13px; font-weight: 900;
                       border: 2px solid #000000; border-radius: 9px; padding: 0px 5px; }
                #title { color: #ffffff; font-size: 15px; font-weight: 900; letter-spacing: 1px; }
                #x { background: #e52521; color: #ffffff; border: 2px solid #000000;
                     border-radius: 8px; font-size: 12px; font-weight: 900; padding: 0px 8px; }
                #tear { color: #ffffff; font-size: 12px; font-weight: 900; letter-spacing: 2px; }
                #body { background: #ffffff; color: #000000; border: 3px solid #000000;
                        border-radius: 10px; font-size: 13px; font-weight: 600; }
                #spin { height: 8px; border: 2px solid #000000; background: #ffffff; }
                #spin::chunk { background: #43d33d; }
                #status { color: #ffffff; font-size: 11px; font-weight: bold; }
                #btn { background: #f8b800; color: #000000; border: 3px solid #000000;
                       border-radius: 10px; padding: 6px 12px; font-weight: 900; }
                #btnPri { background: #43d33d; color: #000000; border: 3px solid #000000;
                          border-radius: 10px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #ffffff; color: #000000; border: 2px solid #000000;
                              border-radius: 8px; font-size: 11px; max-width: 190px; }
                """,
    },
    "bioshock": {
        "label": "BioShock",
        "title": "\u2693 RAPTURE \u2014 {model}", "dot": "\u25c8",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u00b7 ART DECO \u00b7 1959 \u00b7 NO GODS OR KINGS \u00b7",
        "buttons": ("Kindly Copy", "Gather", "Close"),
        "status_ok": "would you kindly check the log",
        "qss": """
                #card { background: rgba(7,18,15,246); border: 2px solid #c9a227;
                        border-radius: 2px; }
                #dot { color: #c9a227; font-size: 14px; }
                #title { color: #e8d9a8; font-size: 15px; letter-spacing: 5px;
                         font-family: Georgia, serif; }
                #x { background: transparent; color: #7a8a80; border: 1px solid #c9a227;
                     font-size: 12px; padding: 2px 8px; }
                #tear { color: #7a8a80; font-size: 10px; letter-spacing: 3px; }
                #body { background: rgba(0,0,0,150); color: #e8e4d4;
                        border: none; border-top: 1px solid #c9a227;
                        font-family: Georgia, serif; font-size: 13.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #c9a227; }
                #status { color: #7a8a80; font-size: 11px; font-family: Georgia, serif;
                          font-style: italic; }
                #btn { background: transparent; color: #e8d9a8; border: 1px solid #c9a227;
                       font-family: Georgia, serif; letter-spacing: 1px; padding: 7px 14px; }
                #btnPri { background: #c9a227; color: #07120f; border: none;
                          font-family: Georgia, serif; font-weight: bold; padding: 7px 16px; }
                #modelCombo { background: #07120f; color: #e8d9a8; border: 1px solid #5a6a60;
                              font-family: Georgia, serif; font-size: 11px; max-width: 200px; }
                """,
    },
    "borderlands": {
        "label": "Borderlands",
        "title": "\u2620 BORDERLANDS \u2014 {model}", "dot": "\u2620",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("LOOT", "SELL", "QUIT"),
        "status_ok": "badass rank +1 \u00b7 saved",
        "qss": """
                #card { background: #0d0d0d; border: 3px solid #ffd800; border-radius: 0px; }
                #dot { color: #ff6b00; font-size: 15px; }
                #title { color: #ffd800; font-size: 17px; font-weight: 900;
                         font-style: italic; letter-spacing: 1px; }
                #x { background: #ff6b00; color: #0d0d0d; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #body { background: #141414; color: #f2f2f2; border: 2px solid #ffd800;
                        border-radius: 0px; font-size: 13px; font-weight: 600; }
                #spin { height: 7px; border: 2px solid #ffd800; background: #141414; }
                #spin::chunk { background: #ff6b00; }
                #status { color: #ff6b00; font-size: 11px; font-weight: bold; font-style: italic; }
                #btn { background: #1c1c1c; color: #ffd800; border: 3px solid #ffd800;
                       border-radius: 0px; padding: 7px 14px; font-weight: 900; font-style: italic; }
                #btnPri { background: #ff6b00; color: #0d0d0d; border: 3px solid #ffd800;
                          border-radius: 0px; padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #141414; color: #ffd800; border: 2px solid #8a8a8a;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "persona": {
        "label": "Persona 5",
        "title": "\u2605 TAKE YOUR HEART \u2014 {model}", "dot": "\u2605",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u2605", "tr", 4, 2, -14, "#e60012"),
                     ("\u2605", "bl", 6, 46, 10, "#ffffff")],
        "buttons": ("Showtime!", "Calling Card", "Heist Over"),
        "status_ok": "treasure secured \u00b7 saved",
        "qss": """
                #card { background: #0a0a0a; border: 3px solid #e60012; border-radius: 2px; }
                #dot { color: #e60012; font-size: 15px; }
                #title { background: #e60012; color: #ffffff; font-size: 15px;
                         font-weight: 900; font-style: italic; padding: 4px 12px; }
                #x { background: #ffffff; color: #0a0a0a; border: none;
                     font-size: 12px; font-weight: 900; font-style: italic; padding: 2px 10px; }
                #body { background: #111111; color: #ffffff; border: 2px solid #ffffff;
                        font-size: 13px; font-weight: 600; }
                #spin { height: 6px; border: none; background: #111111; }
                #spin::chunk { background: #e60012; }
                #status { color: #888888; font-size: 11px; font-weight: bold; font-style: italic; }
                #btn { background: #ffffff; color: #0a0a0a; border: 3px solid #0a0a0a;
                       outline: 2px solid #ffffff; padding: 7px 14px;
                       font-weight: 900; font-style: italic; }
                #btnPri { background: #e60012; color: #ffffff; border: 3px solid #ffffff;
                          padding: 7px 16px; font-weight: 900; font-style: italic; }
                #modelCombo { background: #111111; color: #ffffff; border: 2px solid #e60012;
                              font-size: 11px; max-width: 200px; }
                #floater { font-size: 26px; }
                """,
    },
    "tekken": {
        "label": "Tekken",
        "title": "TEKKEN \u2014 {model}", "dot": "\u25cf",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "alarm": True, "alarm_text": "FIGHT!",
        "note_top": "ROUND 1 \u00b7 GET READY",
        "buttons": ("Rage Art", "Rematch", "K.O."),
        "status_ok": "K.O.! GREAT \u00b7 saved",
        "qss": """
                #card { background: #0a0a0a; border: 3px solid #e60012; border-radius: 0px; }
                #dot { color: #e60012; font-size: 14px; }
                #title { color: #ffffff; font-size: 17px; font-weight: 900;
                         font-style: italic; letter-spacing: 1px; }
                #x { background: #e60012; color: white; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #tear { color: #e60012; font-size: 11px; font-weight: 900;
                        font-style: italic; letter-spacing: 2px; }
                #alarm { font-size: 18px; font-weight: 900; font-style: italic;
                         letter-spacing: 4px; border-radius: 0px; }
                #body { background: #101010; color: #f2f2f2; border: 2px solid #333333;
                        font-size: 13px; font-weight: 600; }
                #spin { height: 7px; border: none; background: #101010; }
                #spin::chunk { background: #e60012; }
                #status { color: #888888; font-size: 11px; font-weight: bold; font-style: italic; }
                #btn { background: #161616; color: #ffffff; border: 2px solid #ffffff;
                       padding: 8px 14px; font-weight: 900; font-style: italic; }
                #btnPri { background: #e60012; color: #ffffff; border: none;
                          padding: 8px 16px; font-weight: 900; font-style: italic; }
                #modelCombo { background: #101010; color: #ffffff; border: 1px solid #333333;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "destiny": {
        "label": "Destiny 2",
        "title": "\u25b2 GUARDIANS \u2014 {model}", "dot": "\u25b2",
        "min_w": 440, "max_w": 520, "opacity": 0.95,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Loot", "Orbit", "Wipe"),
        "status_ok": "eyes up, guardian \u00b7 saved",
        "qss": """
                #card { background: rgba(20,27,40,244); border: 1px solid #9db8d9;
                        border-radius: 3px; }
                #dot { color: #eef1f6; font-size: 13px; }
                #title { color: #eef1f6; font-size: 13px; font-weight: 300; letter-spacing: 4px; }
                #x { background: transparent; color: #66788f; border: 1px solid #3a4a61;
                     font-size: 12px; padding: 2px 8px; }
                #body { background: rgba(255,255,255,14); color: #eef1f6;
                        border: 1px solid #3a4a61; border-radius: 2px; font-size: 13px; }
                #spin { height: 3px; border: none; background: transparent; }
                #spin::chunk { background: #9db8d9; }
                #status { color: #66788f; font-size: 11px; letter-spacing: 1px; }
                #btn { background: transparent; color: #eef1f6; border: 1px solid #66788f;
                       border-radius: 2px; padding: 7px 16px; letter-spacing: 2px; }
                #btnPri { background: #eef1f6; color: #141b28; border: none;
                          border-radius: 2px; padding: 7px 18px; letter-spacing: 2px; }
                #modelCombo { background: #141b28; color: #eef1f6; border: 1px solid #3a4a61;
                              font-size: 11px; max-width: 210px; }
                """,
    },
    "batman": {
        "label": "Batman",
        "title": "GOTHAM \u2014 {model}", "dot": "\u25cf",
        "min_w": 420, "max_w": 500, "opacity": 0.98,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Detect", "Case Files", "I\u2019m Batman"),
        "status_ok": "justice \u00b7 saved",
        "qss": """
                #card { background: rgba(5,5,5,248); border: 2px solid #ffdd00;
                        border-radius: 10px; }
                #dot { color: #ffdd00; font-size: 14px; }
                #title { background: #ffdd00; color: #050505; font-size: 14px;
                         font-weight: 900; letter-spacing: 2px; padding: 4px 12px;
                         border-radius: 12px; }
                #x { background: transparent; color: #ffdd00; border: 1px solid #ffdd00;
                     font-size: 12px; padding: 2px 8px; border-radius: 8px; }
                #body { background: #0c0c0c; color: #e8e8e8; border: 1px solid #3a3a3a;
                        border-radius: 8px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #ffdd00; }
                #status { color: #7a7a5a; font-size: 11px; }
                #btn { background: transparent; color: #e8e8e8; border: 2px solid #5a5a5a;
                       border-radius: 10px; padding: 7px 14px; font-weight: bold; }
                #btnPri { background: #ffdd00; color: #050505; border: none;
                          border-radius: 10px; padding: 7px 16px; font-weight: 900; }
                #modelCombo { background: #0c0c0c; color: #e8e8e8; border: 1px solid #3a3a3a;
                              border-radius: 8px; font-size: 11px; max-width: 200px; }
                """,
    },
    "falloutnv": {
        "label": "Fallout New Vegas",
        "title": "\u2605 WELCOME TO NEW VEGAS", "dot": "\u2605",
        "min_w": 440, "max_w": 520, "opacity": 1.0,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "WAR. WAR NEVER CHANGES.",
        "buttons": ("[Copy]", "[Pip-Boy]", "Goodbye"),
        "status_ok": "war never changes \u00b7 saved",
        "qss": """
                #card { background: #0a0800; border: 3px double #ffb000; border-radius: 0px; }
                #dot { color: #ffb000; font-size: 14px; }
                #title { color: #ffb000; font-size: 14px; font-weight: bold;
                         font-family: Consolas, monospace; letter-spacing: 2px; }
                #x { background: transparent; color: #7a5f00; border: 1px solid #7a5f00;
                     font-family: Consolas, monospace; font-size: 12px; }
                #tear { color: #7a5f00; font-size: 11px; font-family: Consolas, monospace;
                        letter-spacing: 2px; }
                #body { background: #000000; color: #ffb000; border: none;
                        border-top: 1px solid #7a5f00;
                        font-family: Consolas, monospace; font-size: 13px; }
                #spin { height: 6px; border: 1px solid #7a5f00; background: #000000; }
                #spin::chunk { background: #ffb000; }
                #status { color: #7a5f00; font-size: 11px; font-family: Consolas, monospace; }
                #btn { background: transparent; color: #ffb000; border: 1px solid #7a5f00;
                       border-radius: 0px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btnPri { background: #ffb000; color: #0a0800; border: none;
                          border-radius: 0px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #000000; color: #ffb000; border: 1px solid #7a5f00;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "steampunk": {
        "label": "Steampunk",
        "title": "\u2699 STEAMWORKS \u2014 {model}", "dot": "\u2699",
        "min_w": 420, "max_w": 500, "opacity": 0.98,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u2699", "tr", 6, 6, -12, "#caa25c"),
                     ("\u2699", "bl", 8, 48, 10, "#8a6a3a")],
        "buttons": ("Stoke", "Logbook", "Vent Steam"),
        "status_ok": "pressure nominal \u00b7 saved",
        "qss": """
                #card { background: #241610; border: 3px solid #caa25c; border-radius: 8px; }
                #dot { color: #caa25c; font-size: 15px; }
                #title { color: #e8cf9a; font-size: 14px; letter-spacing: 3px;
                         font-family: Georgia, serif; }
                #x { background: #3a2415; color: #caa25c; border: 1px solid #caa25c;
                     font-size: 12px; padding: 2px 8px; border-radius: 6px; }
                #body { background: #2e1c0f; color: #e8d9b8; border: 1px solid #6b4a26;
                        border-radius: 4px; font-family: Georgia, serif; font-size: 13px; }
                #spin { height: 6px; border: 1px solid #6b4a26; background: #2e1c0f; }
                #spin::chunk { background: #b87333; }
                #status { color: #8a6a3a; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: #3a2415; color: #e8cf9a; border: 2px solid #caa25c;
                       border-radius: 8px; font-family: Georgia, serif; padding: 6px 12px; }
                #btnPri { background: #b87333; color: #1c1008; border: 2px solid #caa25c;
                          border-radius: 8px; font-family: Georgia, serif;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #2e1c0f; color: #e8cf9a; border: 1px solid #6b4a26;
                              font-family: Georgia, serif; font-size: 11px; max-width: 200px; }
                #floater { font-size: 24px; }
                """,
    },
    "cyberpunk": {
        "label": "Cyberpunk 2077",
        "title": "\u26a0 NIGHT CITY \u2014 {model}", "dot": "\u2622",
        "min_w": 440, "max_w": 520, "opacity": 0.96,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "ticker": True,
        "ticker_text": "\u26a0 TRAUMA TEAM PLATINUM AVAILABLE \u26a0 CYBERPSYCHOSIS RISK: ELEVATED \u26a0 NEW GIGS IN WATSON \u26a0 ",
        "buttons": ("Preem", "Fixer Log", "Flatline"),
        "status_ok": "preem work \u00b7 saved",
        "status_err": "flatlined \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(10,10,10,246); border: none;
                        border-left: 6px solid #fcee0a; border-radius: 0px; }
                #dot { color: #ff003c; font-size: 15px; }
                #title { background: #fcee0a; color: #0a0a0a; font-size: 15px;
                         font-weight: 900; font-style: italic; padding: 4px 12px; }
                #x { background: #ff003c; color: white; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #ticker { color: #fcee0a; font-size: 11px; font-weight: bold;
                          font-family: Consolas, monospace; }
                #body { background: #101014; color: #e8ecf4; border: 1px solid #3a3a44;
                        font-family: Consolas, monospace; font-size: 12.5px; }
                #spin { height: 5px; border: none; background: #101014; }
                #spin::chunk { background: #00f0ff; }
                #status { color: #ff003c; font-size: 11px; font-weight: bold;
                          font-family: Consolas, monospace; }
                #btn { background: transparent; color: #fcee0a; border: 2px solid #fcee0a;
                       font-weight: 900; font-style: italic; padding: 7px 14px; }
                #btnPri { background: #ff003c; color: white; border: none;
                          font-weight: 900; font-style: italic; padding: 7px 16px; }
                #modelCombo { background: #101014; color: #00f0ff; border: 1px solid #3a3a44;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "ghostwire": {
        "label": "Ghostwire Tokyo",
        "title": "\u26e9 SHIBUYA \u2014 {model}", "dot": "\u26e9",
        "min_w": 420, "max_w": 500, "opacity": 0.96,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u6255", "tr", 8, 24, -10, "#ff2a2a")],
        "buttons": ("Purge", "Nekomata Log", "Close"),
        "status_ok": "spirits cleansed \u00b7 saved",
        "qss": """
                #card { background: rgba(6,8,12,245); border: 1px solid #ff2a2a;
                        border-radius: 4px; }
                #dot { color: #ff2a2a; font-size: 15px; }
                #title { color: #6ff5ff; font-size: 14px; letter-spacing: 3px; }
                #x { background: transparent; color: #3d6a72; border: 1px solid #ff2a2a;
                     font-size: 12px; padding: 2px 8px; }
                #body { background: rgba(0,0,0,140); color: #d8f4f8;
                        border: 1px solid rgba(111,245,255,70); border-radius: 3px;
                        font-size: 13px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #6ff5ff; }
                #status { color: #3d6a72; font-size: 11px; }
                #btn { background: transparent; color: #6ff5ff; border: 1px solid #2a5a62;
                       padding: 6px 12px; }
                #btnPri { background: #ff2a2a; color: #ffffff; border: none;
                          padding: 6px 14px; font-weight: bold; }
                #modelCombo { background: #06080c; color: #d8f4f8; border: 1px solid #2a3a44;
                              font-size: 11px; max-width: 200px; }
                #floater { font-size: 26px; }
                """,
    },
    "skyrim": {
        "label": "Skyrim",
        "title": "\u2756 SKYRIM \u2014 {model}", "dot": "\u2756",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u25c4 \u25c6 \u25ba",
        "buttons": ("Fus", "Quest Log", "Ro Dah"),
        "status_ok": "quest updated \u00b7 saved",
        "qss": """
                #card { background: rgba(30,32,36,246); border: 1px solid #6b6f76;
                        border-radius: 2px; }
                #dot { color: #d8cfae; font-size: 13px; }
                #title { color: #e8e2cc; font-size: 15px; letter-spacing: 5px;
                         font-family: Georgia, serif; }
                #x { background: transparent; color: #8a8d92; border: 1px solid #4a4d52;
                     font-size: 12px; padding: 2px 8px; }
                #tear { color: #6b6f76; font-size: 10px; letter-spacing: 4px; }
                #body { background: transparent; color: #d8d4c4; border: none;
                        border-top: 1px solid #4a4d52; font-family: Georgia, serif;
                        font-size: 13.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #d8cfae; }
                #status { color: #8a8d92; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: transparent; color: #e8e2cc; border: 1px solid #6b6f76;
                       font-family: Georgia, serif; letter-spacing: 1px; padding: 7px 14px; }
                #btnPri { background: #d8cfae; color: #1e2024; border: none;
                          font-family: Georgia, serif; padding: 7px 16px; }
                #modelCombo { background: #1e2024; color: #d8d4c4; border: 1px solid #4a4d52;
                              font-family: Georgia, serif; font-size: 11px; max-width: 200px; }
                """,
    },
    "baldur": {
        "label": "Baldur's Gate",
        "title": "\u2694 BALDUR\u2019S GATE \u2014 {model}", "dot": "\u25c8",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u2694 ROLL FOR INITIATIVE \u2694",
        "buttons": ("Roll Insight", "Journal", "Long Rest"),
        "status_ok": "critical success \u00b7 saved",
        "status_err": "critical fail \u00b7 attempt logged",
        "qss": """
                #card { background: rgba(20,16,12,246); border: 2px solid #c9a227;
                        border-radius: 6px; }
                #dot { color: #8a1f2d; font-size: 14px; }
                #title { color: #e8cf9a; font-size: 14px; letter-spacing: 2px;
                         font-family: Georgia, serif; }
                #x { background: #8a1f2d; color: #e8cf9a; border: none;
                     font-size: 12px; padding: 2px 10px; border-radius: 4px; }
                #tear { color: #8a6a3a; font-size: 10px; letter-spacing: 2px;
                        font-family: Georgia, serif; }
                #body { background: rgba(0,0,0,150); color: #e0d5b8;
                        border: 1px solid #6b5f2e; border-radius: 4px;
                        font-family: Georgia, serif; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #8a1f2d; }
                #status { color: #8a6a3a; font-size: 11px; font-family: Georgia, serif; }
                #btn { background: transparent; color: #e8cf9a; border: 1px solid #8a6a3a;
                       border-radius: 4px; font-family: Georgia, serif; padding: 6px 12px; }
                #btnPri { background: #8a1f2d; color: #f2e6c9; border: 1px solid #c9a227;
                          border-radius: 4px; font-family: Georgia, serif; padding: 6px 14px; }
                #modelCombo { background: #14100c; color: #e0d5b8; border: 1px solid #6b5f2e;
                              font-family: Georgia, serif; font-size: 11px; max-width: 200px; }
                """,
    },
    "dispatch": {
        "label": "Dispatch (SDN)",
        "title": "\u2139 SDN DISPATCH \u2014 {model}", "dot": "\u2605",
        "min_w": 440, "max_w": 520, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "SDN HANDBOOK p.44: A SAFE, VIOLENCE-FREE WORKPLACE",
        "buttons": ("Deploy", "Roster", "End Shift"),
        "status_ok": "shift complete \u00b7 0 casualties \u00b7 saved",
        "qss": """
                #card { background: #f4f1ea; border: 3px solid #101c2c; border-radius: 6px; }
                #dot { color: #ff6b1a; font-size: 14px; }
                #title { background: #101c2c; color: #ffffff; font-size: 13px;
                         font-weight: 900; letter-spacing: 1px; padding: 5px 12px; }
                #x { background: #ff6b1a; color: #101c2c; border: none;
                     font-size: 12px; font-weight: 900; padding: 2px 10px; }
                #tear { color: #5a6a7a; font-size: 10px; font-weight: bold; letter-spacing: 1px; }
                #body { background: #ffffff; color: #1c2836; border: 2px solid #101c2c;
                        border-radius: 4px; font-size: 13px; }
                #spin { height: 6px; border: 2px solid #101c2c; background: #ffffff; }
                #spin::chunk { background: #1f6feb; }
                #status { color: #5a6a7a; font-size: 11px; font-weight: bold; }
                #btn { background: #ffffff; color: #101c2c; border: 2px solid #101c2c;
                       border-radius: 4px; padding: 6px 12px; font-weight: 900; }
                #btnPri { background: #ff6b1a; color: #101c2c; border: 2px solid #101c2c;
                          border-radius: 4px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #ffffff; color: #1c2836; border: 2px solid #101c2c;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "terraria": {
        "label": "Terraria",
        "title": "\u26cf TERRARIA \u2014 {model}", "dot": "\u26cf",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Dig", "Craft", "Save & Exit"),
        "status_ok": "achievement get! \u00b7 saved",
        "qss": """
                #card { background: #2a2118; border: 3px solid #6b4a2a; border-radius: 6px; }
                #dot { color: #5da43d; font-size: 14px; }
                #title { color: #f2e6c9; font-size: 14px; font-weight: 900; }
                #x { background: #6b4a2a; color: #f2e6c9; border: 2px solid #3a2a16;
                     font-size: 11px; font-weight: bold; padding: 0px 8px; }
                #body { background: #1c150d; color: #f2e6c9; border: 2px solid #3a2a16;
                        border-radius: 4px; font-size: 12.5px; }
                #spin { height: 8px; border: 2px solid #3a2a16; background: #1c150d; }
                #spin::chunk { background: #5da43d; }
                #status { color: #a8936a; font-size: 11px; }
                #btn { background: #4a3a24; color: #f2e6c9; border: 2px solid #6b4a2a;
                       border-radius: 4px; padding: 6px 12px; font-weight: bold; }
                #btn:hover { background: #5da43d; color: #10240a; }
                #btnPri { background: #5da43d; color: #10240a; border: 2px solid #3a2a16;
                          border-radius: 4px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #1c150d; color: #f2e6c9; border: 2px solid #3a2a16;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "zelda": {
        "label": "Legend of Zelda",
        "title": "\u25b2 HYRULE \u2014 {model}", "dot": "\u25b2",
        "min_w": 420, "max_w": 500, "opacity": 0.97,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "buttons": ("Take This", "Save", "It\u2019s Dangerous"),
        "status_ok": "it\u2019s dangerous to go alone \u00b7 saved",
        "qss": """
                #card { background: rgba(11,61,46,246); border: 2px solid #d4af37;
                        border-radius: 8px; }
                #dot { color: #d4af37; font-size: 15px; }
                #title { color: #f3ead0; font-size: 14px; letter-spacing: 3px;
                         font-family: Georgia, serif; }
                #x { background: transparent; color: #8aa88f; border: 1px solid #d4af37;
                     font-size: 12px; padding: 2px 8px; border-radius: 6px; }
                #body { background: rgba(0,0,0,130); color: #f3ead0;
                        border: 1px solid rgba(212,175,55,120); border-radius: 6px;
                        font-family: Georgia, serif; font-size: 13.5px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #d4af37; }
                #status { color: #8aa88f; font-size: 11px; font-family: Georgia, serif;
                          font-style: italic; }
                #btn { background: transparent; color: #f3ead0; border: 2px solid #d4af37;
                       border-radius: 8px; font-family: Georgia, serif; padding: 6px 12px; }
                #btnPri { background: #d4af37; color: #0b3d2e; border: none;
                          border-radius: 8px; font-family: Georgia, serif;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #0b3d2e; color: #f3ead0; border: 1px solid #6b5f2e;
                              font-family: Georgia, serif; font-size: 11px; max-width: 200px; }
                """,
    },
    "runescape": {
        "label": "RuneScape",
        "title": "\u2694 RUNESCAPE \u2014 {model}", "dot": "\u2694",
        "min_w": 420, "max_w": 500, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "XP DROP: +120 ANALYSIS",
        "buttons": ("Bank", "Quest Journal", "Logout"),
        "status_ok": "120 analysis XP \u00b7 saved",
        "qss": """
                #card { background: #4a3220; border: 3px solid #2a1c0e; border-radius: 4px; }
                #dot { color: #ffff00; font-size: 14px; }
                #title { color: #ffff00; font-size: 14px; font-weight: 900; }
                #x { background: #6b4a2a; color: #ffff00; border: 2px solid #2a1c0e;
                     font-size: 11px; font-weight: bold; padding: 0px 8px; }
                #tear { color: #ffff00; font-size: 11px; font-weight: bold; }
                #body { background: #c8a165; color: #2a1c0e; border: 3px solid #2a1c0e;
                        border-radius: 2px; font-size: 13px; font-weight: 600; }
                #spin { height: 8px; border: 2px solid #2a1c0e; background: #c8a165; }
                #spin::chunk { background: #7a0000; }
                #status { color: #ffff00; font-size: 11px; font-weight: bold; }
                #btn { background: #6b4a2a; color: #ffff00; border: 2px solid #2a1c0e;
                       border-radius: 2px; padding: 6px 12px; font-weight: bold; }
                #btn:hover { background: #7a0000; }
                #btnPri { background: #7a0000; color: #ffff00; border: 2px solid #2a1c0e;
                          border-radius: 2px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #c8a165; color: #2a1c0e; border: 2px solid #2a1c0e;
                              font-size: 11px; max-width: 200px; }
                """,
    },
    "ultrakill": {
        "label": "ULTRAKILL",
        "title": "V1 // {model}", "dot": "\u271a",
        "min_w": 420, "max_w": 500, "opacity": 0.98,
        "reveal": "type", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "MANKIND IS DEAD \u00b7 BLOOD IS FUEL \u00b7 HELL IS FULL",
        "buttons": ("RIP", "TEAR", "REPENT"),
        "status_ok": "S+ \u00b7 ULTRAKILL \u00b7 saved",
        "status_err": "WASTED \u00b7 attempt logged",
        "qss": """
                #card { background: #000000; border: 2px solid #c00000; border-radius: 0px; }
                #dot { color: #ff0000; font-size: 14px; font-weight: 900; }
                #title { background: #c00000; color: #ffffff; font-size: 14px;
                         font-weight: 900; font-family: Consolas, monospace;
                         letter-spacing: 1px; padding: 3px 10px; }
                #x { background: transparent; color: #c00000; border: 1px solid #c00000;
                     font-family: Consolas, monospace; font-size: 12px; padding: 2px 8px; }
                #tear { color: #ffd800; font-size: 10px; font-family: Consolas, monospace;
                        letter-spacing: 1px; font-weight: bold; }
                #body { background: #050505; color: #ff2a2a; border: 1px solid #5a0000;
                        font-family: Consolas, monospace; font-size: 13px; font-weight: bold; }
                #spin { height: 6px; border: 1px solid #5a0000; background: #050505; }
                #spin::chunk { background: #ff0000; }
                #status { color: #ffd800; font-size: 11px; font-family: Consolas, monospace;
                          font-weight: bold; }
                #btn { background: transparent; color: #ff2a2a; border: 2px solid #c00000;
                       font-family: Consolas, monospace; padding: 6px 12px; font-weight: bold; }
                #btnPri { background: #c00000; color: #ffffff; border: none;
                          font-family: Consolas, monospace; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #050505; color: #ff2a2a; border: 1px solid #5a0000;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
    "stellar": {
        "label": "Stellar Blade",
        "title": "\u2726 7TH AIRBORNE \u2014 {model}", "dot": "\u2726",
        "min_w": 420, "max_w": 500, "opacity": 0.96,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "RECLAIM EARTH FOR HUMANKIND",
        "buttons": ("Scan", "Legacy", "Rest at Camp"),
        "status_ok": "camp secured \u00b7 saved \u00b7 for humankind",
        "qss": """
                #card { background: rgba(238,241,244,248); border: 1px solid #9aa8bd;
                        border-radius: 10px; }
                #dot { color: #ff7a1a; font-size: 14px; }
                #title { color: #0b1220; font-size: 13px; font-weight: 300; letter-spacing: 4px; }
                #x { background: transparent; color: #7a8aa0; border: 1px solid #c3ccd8;
                     font-size: 12px; padding: 2px 8px; border-radius: 6px; }
                #tear { color: #7a8aa0; font-size: 10px; letter-spacing: 3px; }
                #body { background: #ffffff; color: #16202e; border: 1px solid #c3ccd8;
                        border-radius: 8px; font-size: 13px; }
                #spin { height: 4px; border: none; background: transparent; }
                #spin::chunk { background: #ff7a1a; }
                #status { color: #7a8aa0; font-size: 11px; }
                #btn { background: transparent; color: #0b1220; border: 1px solid #9aa8bd;
                       border-radius: 8px; padding: 6px 12px; }
                #btnPri { background: #ff7a1a; color: #ffffff; border: none;
                          border-radius: 8px; padding: 6px 14px; font-weight: 700; }
                #modelCombo { background: #ffffff; color: #16202e; border: 1px solid #c3ccd8;
                              border-radius: 6px; font-size: 11px; max-width: 200px; }
                """,
    },
    "coquette": {
        "label": "Coquette",
        "title": "\U0001f380 coquette corner \u2014 {model}", "dot": "\U0001f380",
        "min_w": 400, "max_w": 470, "opacity": 0.98,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\U0001f380", "tr", 8, 6, -12, "#c78ca0"),
                     ("\u2767", "bl", 10, 44, 8, "#ecbad0")],
        "buttons": ("adore", "keep", "farewell"),
        "status_ok": "sealed with a bow \u00b7 saved",
        "qss": """
                #card { background: #fff3fa; border: 1px solid #ecbad0; border-radius: 16px; }
                #dot { color: #c78ca0; font-size: 15px; }
                #title { color: #1c1b18; font-size: 15px; font-style: italic;
                         font-family: Georgia, serif; }
                #x { background: #ffe1ed; color: #1c1b18; border: 1px solid #ecbad0;
                     border-radius: 10px; font-size: 12px; padding: 2px 10px;
                     font-family: Georgia, serif; font-style: italic; }
                #body { background: #ffffff; color: #1c1b18; border: 1px solid #fcd7d7;
                        border-radius: 12px; font-family: Georgia, serif; font-size: 13.5px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #ecbad0; border-radius: 3px; }
                #status { color: #a8889a; font-size: 11px; font-family: Georgia, serif;
                          font-style: italic; }
                #btn { background: #ffffff; color: #1c1b18; border: 1.5px solid #ecbad0;
                       border-radius: 12px; font-family: Georgia, serif;
                       font-style: italic; padding: 6px 14px; }
                #btnPri { background: #c78ca0; color: #ffffff; border: none;
                          border-radius: 12px; font-family: Georgia, serif;
                          font-style: italic; padding: 6px 16px; }
                #modelCombo { background: #ffffff; color: #1c1b18; border: 1px solid #fcd7d7;
                              border-radius: 10px; font-family: Georgia, serif;
                              font-size: 11px; max-width: 200px; }
                #floater { font-size: 20px; }
                """,
    },
    "strawberry": {
        "label": "Strawberry Milk",
        "title": "\U0001f353 strawberry milk \u2014 {model}", "dot": "\u25cf",
        "min_w": 400, "max_w": 470, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "SHAKE WELL \u00b7 SERVE CHILLED \u00b7 500ml",
        "buttons": ("Sip", "Refill", "All Gone"),
        "status_ok": "extra strawberry \u00b7 saved",
        "qss": """
                #card { background: #fff6f0; border: 3px solid #ff9eb5; border-radius: 14px; }
                #dot { color: #e0455a; font-size: 14px; }
                #title { color: #a3243b; font-size: 15px; font-weight: 900; }
                #x { background: #ffd1dc; color: #a3243b; border: 2px solid #e0455a;
                     border-radius: 10px; font-size: 12px; font-weight: bold; padding: 0px 8px; }
                #tear { color: #c98a94; font-size: 10px; font-weight: bold; letter-spacing: 2px; }
                #body { background: #ffffff; color: #5c2a33; border: 2px solid #ffb3c1;
                        border-radius: 10px; font-size: 13px; }
                #spin { height: 8px; border: 2px solid #e0455a; background: #ffffff;
                        border-radius: 4px; }
                #spin::chunk { background: #e0455a; }
                #status { color: #c98a94; font-size: 11px; font-weight: bold; }
                #btn { background: #ffffff; color: #a3243b; border: 3px solid #ff9eb5;
                       border-radius: 12px; padding: 6px 12px; font-weight: 900; }
                #btnPri { background: #e0455a; color: #ffffff; border: none;
                          border-radius: 12px; padding: 6px 14px; font-weight: 900; }
                #modelCombo { background: #ffffff; color: #5c2a33; border: 2px solid #ffb3c1;
                              border-radius: 10px; font-size: 11px; max-width: 200px; }
                """,
    },
    "lavender": {
        "label": "Lavender Haze",
        "title": "\u263e lavender haze", "dot": "\u263e",
        "min_w": 400, "max_w": 470, "opacity": 0.96,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "floaters": [("\u263e", "tr", 10, 8, -10, "#8a6fb8"),
                     ("\u2727", "bl", 12, 40, 8, "#b57edc"),
                     ("\u2727", "tl", 40, 60, -8, "#d3c2ec")],
        "buttons": ("Dream", "Stargaze", "Wake Up"),
        "status_ok": "drifting \u00b7 saved",
        "qss": """
                #card { background: rgba(30,24,48,244); border: 1px solid #b57edc;
                        border-radius: 16px; }
                #dot { color: #e6e6fa; font-size: 15px; }
                #title { color: #e6e6fa; font-size: 14px; font-weight: 300; letter-spacing: 3px; }
                #x { background: transparent; color: #8a7ba8; border: 1px solid #5a4a7a;
                     border-radius: 8px; font-size: 12px; padding: 2px 8px; }
                #body { background: rgba(230,230,250,16); color: #f0ebff;
                        border: 1px solid #5a4a7a; border-radius: 12px; font-size: 13px; }
                #spin { height: 5px; border: none; background: transparent; }
                #spin::chunk { background: #b57edc; border-radius: 3px; }
                #status { color: #8a7ba8; font-size: 11px; font-style: italic; }
                #btn { background: transparent; color: #e6e6fa; border: 1.5px solid #8a6fb8;
                       border-radius: 12px; padding: 6px 14px; }
                #btnPri { background: #b57edc; color: #1e1830; border: none;
                          border-radius: 12px; padding: 6px 16px; font-weight: 700; }
                #modelCombo { background: #1e1830; color: #e6e6fa; border: 1px solid #5a4a7a;
                              border-radius: 10px; font-size: 11px; max-width: 200px; }
                #modelCombo QAbstractItemView { background: #1e1830; color: #e6e6fa; }
                #floater { font-size: 20px; }
                """,
    },
    "discord": {
        "label": "Discord",
        "title": "# ss-analysis", "dot": "\u25cf",
        "min_w": 460, "max_w": 540, "opacity": 0.98,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "\u2014 Today \u2014",
        "buttons": ("Send Copy", "Open Log", "Delete"),
        "status_ok": "SS Analyzer BOT \u00b7 today at {time} \u00b7 saved",
        "qss": """
                #card { background: #2b2d31; border: none; border-radius: 8px; }
                #dot { background: #57f287; color: #57f287; font-size: 10px;
                       border-radius: 7px; padding: 0px 4px; }
                #title { color: #f2f3f5; font-size: 15px; font-weight: 700; }
                #x { background: transparent; color: #b5bac1; border: none;
                     font-size: 13px; padding: 2px 8px; border-radius: 4px; }
                #x:hover { background: #ed4245; color: #ffffff; }
                #tear { color: #949ba4; font-size: 11px; font-weight: bold; }
                #body { background: #313338; color: #dbdee1; border: none;
                        border-top: 1px solid #3f4147; border-radius: 0px; font-size: 14px; }
                #spin { height: 4px; border: none; background: #383a40; border-radius: 2px; }
                #spin::chunk { background: #5865f2; border-radius: 2px; }
                #status { color: #b5bac1; font-size: 11px; }
                #btn { background: #4e5058; color: #ffffff; border: none;
                       border-radius: 4px; padding: 8px 16px; font-weight: 600; }
                #btn:hover { background: #6d6f78; }
                #btnPri { background: #5865f2; color: #ffffff; border: none;
                          border-radius: 4px; padding: 8px 18px; font-weight: 600; }
                #btnPri:hover { background: #4752c4; }
                #modelCombo { background: #1e1f22; color: #dbdee1; border: none;
                              border-radius: 4px; font-size: 12px; max-width: 220px; }
                #modelCombo QAbstractItemView { background: #111214; color: #dbdee1;
                              selection-background-color: #5865f2; }
                """,
    },
    "aseprite": {
        "label": "Aseprite",
        "title": "*sprite.aseprite", "dot": "\u25a0",
        "min_w": 400, "max_w": 480, "opacity": 1.0,
        "reveal": "instant", "footer": "always", "autohide": 0, "tear": False,
        "note_top": "Layer 1 \u00b7 Cel 1 \u00b7 100% \u00b7 RGB",
        "buttons": ("Paint", "Fill", "Close"),
        "status_ok": "1 cel changed \u00b7 saved",
        "qss": """
                #card { background: #232323; border: 2px solid #000000; border-radius: 0px; }
                #dot { background: #ff5555; color: #ffffff; font-size: 11px;
                       padding: 0px 5px; }
                #title { background: #7c909f; color: #ffffff; font-size: 12px;
                         font-family: Consolas, monospace; padding: 3px 8px; }
                #x { background: #323232; color: #c6c6c6; border: 2px solid #000000;
                     border-radius: 0px; font-family: Consolas, monospace;
                     font-size: 11px; padding: 0px 8px; }
                #x:hover { background: #ff5555; color: #ffffff; }
                #tear { color: #ffebb6; background: #323232; font-size: 10px;
                        font-family: Consolas, monospace; padding: 2px 6px; }
                #body { background: #101010; color: #e8e8e8;
                        border: 2px solid #000000; border-radius: 0px;
                        font-family: Consolas, monospace; font-size: 12px; }
                #spin { height: 10px; border: 2px solid #000000; background: #101010; }
                #spin::chunk { background: #ff5555; }
                #status { color: #ffff7d; background: #323232; font-size: 11px;
                          font-family: Consolas, monospace; padding: 2px 6px; }
                #btn { background: #3c3c3c; color: #e8e8e8; border: 2px solid #000000;
                       border-radius: 0px; font-family: Consolas, monospace; padding: 6px 12px; }
                #btn:hover { background: #ffebb6; color: #000000; }
                #btnPri { background: #ff5555; color: #ffffff; border: 2px solid #000000;
                          border-radius: 0px; font-family: Consolas, monospace;
                          font-weight: bold; padding: 6px 14px; }
                #modelCombo { background: #101010; color: #e8e8e8; border: 2px solid #000000;
                              font-family: Consolas, monospace; font-size: 11px; max-width: 200px; }
                """,
    },
}

THEME_ORDER = ["obsidian", "clawd", "yorha", "stdout", "receipt", "brutalist",
               "miku", "girly", "overstim", "doge", "amogus",
               "e404", "comic", "bug", "crt", "blueprint",
               "noir", "arcade", "zen", "solar", "ada",
               "win95", "holo", "field", "elden", "hollow",
               "sekiro", "minecraft", "pokefrlg", "gtavc", "gtasa",
               "gta5", "jojo", "cuphead", "manga", "marvel",
               "dc", "halo", "re", "fnaf", "fnf",
               "mario", "bioshock", "borderlands", "persona", "tekken",
               "destiny", "batman", "falloutnv", "steampunk", "cyberpunk",
               "ghostwire", "skyrim", "baldur", "dispatch", "terraria",
               "zelda", "runescape", "ultrakill", "stellar",
               "coquette", "strawberry", "lavender", "discord", "aseprite"]


def get_theme(theme_id):
    return THEMES.get(theme_id) or THEMES["obsidian"]


# ---------------------------------------------------------------- GUI (imported lazily so --selftest stays light)

def run_gui(cli_model=None, cli_key=None, cli_log=None, cli_theme=None, _app=None):
    import random
    from PIL import ImageGrab
    from PySide6 import QtGui, QtWidgets
    from PySide6.QtCore import (QAbstractNativeEventFilter, QObject,
                                Signal, QTimer, Qt, QRect, QPoint)
    from PySide6.QtGui import QCursor, QGuiApplication, QPixmap, QPainter, QColor, QPen, QActionGroup
    from PySide6.QtWidgets import (QApplication, QMainWindow, QDialog, QWidget,
                                   QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
                                   QPushButton, QProgressBar, QSystemTrayIcon,
                                   QMenu, QFrame, QComboBox)

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)  # per-monitor V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    cfg = load_config()
    if cli_model:
        cfg["model"] = cli_model
    if cli_log:
        cfg["log_file"] = cli_log
    GEMINI_KEY = [resolve_api_key(cfg, cli_key)]  # mutable cells for thread access
    GO_KEY = [(cfg.get("opencode_go_api_key") or "").strip()]
    SESSION_ID = "ss-analyzer-" + uuid.uuid4().hex[:12]  # stable per run, for Go routing/cache
    GEMINI_MODEL = cfg.get("gemini_model") or DEFAULT_MODEL
    SYSTEM_PROMPT = cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    USER_PROMPT = cfg.get("user_prompt", DEFAULT_USER_PROMPT)
    ensure_log(LOG_PATH := cfg["log_file"])
    os.makedirs(SNIPS_DIR, exist_ok=True)

    # vision model registry: curated list intersected with the live catalog
    # (offline -> baked list). First entry doubles as Gemini direct option.
    try:
        _live = fetch_go_catalog(timeout=12)
    except Exception as e:
        print(f"[go] live catalog unreachable ({e}); using baked vision list")
        _live = None
    GO_ITEMS = resolve_go_vision_models(cfg, live_ids=_live)
    SELECTIONS = [("gemini", GEMINI_MODEL, f"Gemini {GEMINI_MODEL} (direct)")]
    SELECTIONS += [("go", mid, f"{lbl} (Go)") for mid, lbl in GO_ITEMS]
    _sel_ids = {(p, m) for p, m, _ in SELECTIONS}
    LABELS = {(p, m): lbl for p, m, lbl in SELECTIONS}
    PROVIDER = [cfg.get("provider", "gemini")]
    MODEL = [cfg.get("model") or (cfg.get("go_model") if PROVIDER[0] == "go" else GEMINI_MODEL)]
    if (PROVIDER[0], MODEL[0]) not in _sel_ids:  # stale config -> first valid
        PROVIDER[0], MODEL[0], _ = SELECTIONS[0]
    SETTINGS = load_settings()
    THEME = [cli_theme or SETTINGS.get("theme") or "obsidian"]
    if THEME[0] not in THEMES:
        THEME[0] = "obsidian"
    SAVE = [SETTINGS.get("save_snips", True)]
    LOG = [SETTINGS.get("log_analyses", True)]

    def persist_ui():
        SETTINGS["save_snips"] = SAVE[0]
        SETTINGS["log_analyses"] = LOG[0]
        save_settings(SETTINGS)
    OPACITY = float(cfg.get("overlay_opacity", 0.93))
    # User factor around the 0.93 default: default leaves theme design
    # untouched, a custom overlay_opacity scales every theme proportionally.
    OPACITY_FACTOR = (OPACITY / 0.93) if OPACITY > 0 else 1.0

    # ---------------------------------------------------------- hotkey filter
    class HotkeySignaler(QObject):
        pressed = Signal()

    signaler = HotkeySignaler()

    class HotkeyFilter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, eventType, message):
            try:
                et = bytes(eventType)
            except Exception:
                et = b""
            if b"windows_" not in et or b"_MSG" not in et:
                return False, 0
            try:
                addr = message.__int__() if hasattr(message, "__int__") else int(message)
                msg = wintypes.MSG.from_address(addr)
            except Exception:
                return False, 0
            if msg.message != WM_HOTKEY or msg.wParam != HOTKEY_ID:
                return False, 0
            try:  # enforce LEFT alt specifically
                if not (ctypes.windll.user32.GetAsyncKeyState(VK_LMENU) & 0x8000):
                    return False, 0
            except Exception:
                pass
            QTimer.singleShot(0, signaler.pressed.emit)
            return False, 0

    # -------------------------------------------------- theme widgets
    class RotLabel(QLabel):
        """Static rotated caption (doge captions, rubber stamps)."""

        def __init__(self, text, angle=0, parent=None):
            super().__init__(text, parent)
            self._angle = angle
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(self.palette().color(self.foregroundRole()))
            p.setFont(self.font())
            p.translate(self.width() / 2, self.height() / 2)
            p.rotate(self._angle)
            r = self.fontMetrics().boundingRect(self.text())
            p.drawText(-r.width() / 2, r.height() / 4, self.text())

    class ScanWidget(QWidget):
        """Translucent CRT scanline overlay (mouse-transparent)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WA_TranslucentBackground, True)

        def paintEvent(self, e):
            p = QPainter(self)
            p.setPen(QColor(0, 0, 0, 70))
            y = 0
            while y < self.height():
                p.drawLine(0, y, self.width(), y)
                y += 4

    # ---------------------------------------------------------- snip overlay
    HANDLE = 10

    class SnipOverlay(QMainWindow):
        confirmed = Signal(int, int, int, int)  # global x,y,w,h
        cancelled = Signal()

        def __init__(self, virtual_geo):
            super().__init__(None)
            self._origin = virtual_geo.topLeft()
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setGeometry(virtual_geo)
            self.setCursor(Qt.CrossCursor)
            self.sel = None
            self._drag_from = None
            self._mode = "idle"  # drawing | selected | moving | resizing
            self._handle = -1
            self._move_off = QPoint()
            # floating toolbar
            self.bar = QFrame(self)
            self.bar.setObjectName("snipBar")
            lay = QHBoxLayout(self.bar)
            lay.setContentsMargins(10, 6, 10, 6)
            hint = QLabel("drag: select  •  drag inside: move  •  drag corners: resize  •  Enter: analyze  •  Esc: cancel")
            hint.setObjectName("snipHint")
            self.btn_go = QPushButton("Analyze \u23ce")
            self.btn_go.setObjectName("snipGo")
            self.btn_no = QPushButton("Cancel")
            self.btn_no.setObjectName("snipNo")
            lay.addWidget(hint)
            lay.addWidget(self.btn_go)
            lay.addWidget(self.btn_no)
            self.btn_go.clicked.connect(self.accept_rect)
            self.btn_no.clicked.connect(self.reject)
            self.bar.hide()
            self.setStyleSheet("""
                #snipBar { background: rgba(16,20,28,235); border: 1px solid #7c9cff;
                           border-radius: 10px; }
                #snipHint { color: #c6cede; font-size: 12px; }
                #snipGo { background: #4f7cff; color: white; border: none;
                          border-radius: 7px; padding: 6px 14px; font-weight: 600; }
                #snipGo:hover { background: #638bff; }
                #snipNo { background: rgba(255,255,255,18); color: #e8ecf4;
                          border: 1px solid #3a4358; border-radius: 7px; padding: 6px 12px; }
                #snipNo:hover { background: rgba(255,255,255,40); }
            """)

        # -- geometry helpers (widget-local <-> global)
        def _to_local(self, gp):
            return gp - self._origin

        def _handles(self):
            r = self.sel
            cx, cy = r.center().x(), r.center().y()
            pts = [r.topLeft(), QPoint(cx, r.top()), r.topRight(),
                   QPoint(r.left(), cy), QPoint(r.right(), cy),
                   r.bottomLeft(), QPoint(cx, r.bottom()), r.bottomRight()]
            return [QRect(p.x() - HANDLE // 2, p.y() - HANDLE // 2, HANDLE, HANDLE) for p in pts]

        def _hit_handle(self, p):
            for i, h in enumerate(self._handles()):
                if h.contains(p):
                    return i
            return -1

        # -- mouse
        def mousePressEvent(self, e):
            p = e.position().toPoint() if hasattr(e, "position") else e.pos()
            if e.button() == Qt.RightButton:
                self.reject()
                return
            if self.sel is not None:
                h = self._hit_handle(p)
                if h >= 0:
                    self._mode, self._handle = "resizing", h
                    return
                if self.sel.contains(p):
                    self._mode = "moving"
                    self._move_off = p - self.sel.topLeft()
                    return
            self._drag_from = p
            self.sel = QRect(p, p)
            self._mode = "drawing"
            self.bar.hide()
            self.update()

        def mouseMoveEvent(self, e):
            p = e.position().toPoint() if hasattr(e, "position") else e.pos()
            if self._mode == "drawing" and self._drag_from is not None:
                self.sel = QRect(self._drag_from, p).normalized()
                self.update()
            elif self._mode == "moving":
                self.sel.moveTopLeft(p - self._move_off)
                self.update()
            elif self._mode == "resizing":
                self._resize_to(self._handle, p)
                self.update()

        def mouseReleaseEvent(self, e):
            if self._mode == "drawing":
                if self.sel is None or self.sel.width() < 8 or self.sel.height() < 8:
                    self.sel = None
                    self._mode = "idle"
                    self.update()
                    return
                self._mode = "selected"
                self._place_bar()
                self.update()
            else:
                self._mode = "selected"
                self._place_bar()
                self.update()

        def mouseDoubleClickEvent(self, e):
            p = e.position().toPoint() if hasattr(e, "position") else e.pos()
            if self.sel is not None and self.sel.contains(p):
                self.accept_rect()

        def keyPressEvent(self, e):
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.accept_rect()
            elif e.key() == Qt.Key_Escape:
                self.reject()

        def _resize_to(self, h, p):
            r = QRect(self.sel)
            if h in (0, 3, 5):   # left column
                r.setLeft(min(p.x(), r.right() - 8))
            if h in (2, 4, 7):   # right column
                r.setRight(max(p.x(), r.left() + 8))
            if h in (0, 1, 2):   # top row
                r.setTop(min(p.y(), r.bottom() - 8))
            if h in (5, 6, 7):   # bottom row
                r.setBottom(max(p.y(), r.top() + 8))
            self.sel = r.normalized()

        def _place_bar(self):
            if self.sel is None:
                return
            bw = min(560, max(200, self.width() - 16))
            bh = 40
            x = min(max(self.sel.left(), 8), max(8, self.width() - bw - 8))
            y = self.sel.bottom() + 10
            if y + bh > self.height() - 8:
                y = max(8, self.sel.top() - bh - 10)
            self.bar.setGeometry(x, y, bw, bh)
            self.bar.show()
            self.bar.raise_()

        # -- confirm / cancel
        def accept_rect(self):
            if self.sel is None or self.sel.width() < 8 or self.sel.height() < 8:
                return
            g = self.sel.translated(self._origin)
            x, y, w, h = g.x(), g.y(), g.width(), g.height()
            # Hide BEFORE emitting: the confirmed handler captures the screen
            # synchronously, and our own border/handles must not be in the grab.
            self.hide()
            QApplication.processEvents()
            QTimer.singleShot(150, lambda: self.confirmed.emit(x, y, w, h))
            self.close()

        def reject(self):
            self.cancelled.emit()
            self.close()

        # -- paint
        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            if self.sel is None:
                p.fillRect(self.contentsRect(), QColor(0, 0, 0, 110))
            else:
                r = self.sel
                dim = QColor(0, 0, 0, 110)
                p.fillRect(0, 0, self.width(), r.top(), dim)
                p.fillRect(0, r.bottom() + 1, self.width(), self.height() - r.bottom() - 1, dim)
                p.fillRect(0, r.top(), r.left(), r.height(), dim)
                p.fillRect(r.right() + 1, r.top(), self.width() - r.right() - 1, r.height(), dim)
                # selection frame (off-black; never blue — see accept_rect)
                p.setPen(QPen(QColor(43, 43, 48), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
                # handles (dark fill, light hairline so they read on any bg)
                p.setBrush(QColor(43, 43, 48))
                p.setPen(QPen(QColor(180, 180, 180), 1))
                for h in self._handles():
                    p.drawRoundedRect(h, 2, 2)
                # size label
                g = r.translated(self._origin)
                lbl = f"{g.width()} x {g.height()}"
                p.setPen(QColor(230, 235, 245))
                p.drawText(r.left(), max(0, r.top() - 8), lbl)

    # ---------------------------------------------------------- result overlay
    class MarqueeLabel(QLabel):
        """QLabel that auto-scrolls (character marquee with end pauses) only
        when its text does not fit; otherwise a plain static label. Native
        painting is kept, so every theme's QSS colors apply untouched."""

        def __init__(self, text="", parent=None, interval_ms=130, hold_ticks=12):
            super().__init__(text, parent)
            self._full = text or ""
            self._off = 0
            self._phase = 0  # 0 hold-start, 1 scroll, 2 hold-end
            self._hold = 0
            self._holds = hold_ticks
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._marquee_step)
            self._timer.setInterval(interval_ms)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        def fullText(self):
            return self._full

        def setFullText(self, text):
            self._full = text or ""
            self._off = 0
            self._phase = 0
            self._hold = 0
            super().setText(self._full)
            self._evaluate()

        def setText(self, text):
            self.setFullText(text)

        def _needs_scroll(self):
            try:
                if not self._full or self.width() <= 0:
                    return False
                return self.fontMetrics().horizontalAdvance(self._full) > max(0, self.width() - 4)
            except Exception:
                return False

        def _evaluate(self):
            try:
                if self._needs_scroll() and self.isVisible():
                    if not self._timer.isActive():
                        self._timer.start()
                else:
                    self._timer.stop()
                    self._off = 0
                    self._phase = 0
                    if super().text() != self._full:
                        super().setText(self._full)
            except Exception:
                pass

        def showEvent(self, e):
            super().showEvent(e)
            self._evaluate()

        def hideEvent(self, e):
            try:
                self._timer.stop()
            except Exception:
                pass
            super().hideEvent(e)

        def resizeEvent(self, e):
            super().resizeEvent(e)
            self._evaluate()

        def _marquee_step(self):
            try:
                if not self._needs_scroll():
                    self._evaluate()
                    return
                if self._phase in (0, 2):  # hold at an end
                    self._hold += 1
                    if self._hold < self._holds:
                        return
                    self._hold = 0
                    if self._phase == 2:  # wrap to start
                        self._off = 0
                        self._phase = 0
                        super().setText(self._full)
                        return
                    self._phase = 1
                    return
                track = self._full + "   \u2022   "
                self._off += 1
                if self._off >= len(track):
                    self._phase = 2
                    return
                try:
                    avg = max(1, self.fontMetrics().averageCharWidth())
                    vis = max(1, int(self.width() / avg))
                except Exception:
                    vis = 40
                doubled = track + self._full
                super().setText(doubled[self._off:self._off + vis])
            except Exception:
                pass

    class ResultOverlay(QDialog):
        model_chosen = Signal(str, str)  # provider, model

        def __init__(self, selections, provider, model):
            super().__init__(None)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setWindowOpacity(OPACITY)
            self.setMinimumWidth(380)
            self.setMaximumWidth(520)
            self._drag = None
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            self.card = QFrame()
            self.card.setObjectName("card")
            lay = QVBoxLayout(self.card)
            lay.setContentsMargins(16, 12, 16, 12)
            lay.setSpacing(8)
            # header (drag handle)
            hl = QHBoxLayout()
            self.dot = QLabel("\u25cf")
            self.dot.setObjectName("dot")
            self.title = MarqueeLabel("SS Analyzer")
            self.title.setObjectName("title")
            self.combo = QComboBox()
            self.combo.setObjectName("modelCombo")
            self.combo.setToolTip("Analyzer model — applies to the next analysis")
            for p, m, label in selections:
                self.combo.addItem(label, (p, m))
            self.sync_combo(provider, model)
            self.combo.currentIndexChanged.connect(self._on_combo)
            self.x = QPushButton("\u2715")
            self.x.setObjectName("x")
            self.x.clicked.connect(self.hide)
            hl.addWidget(self.dot)
            hl.addWidget(self.title)
            hl.addStretch(1)
            hl.addWidget(self.combo)
            hl.addWidget(self.x)
            self.header = QWidget()
            self.header.setLayout(hl)
            # body
            self.body = QTextBrowser()
            self.body.setObjectName("body")
            self.body.setOpenExternalLinks(False)
            self.body.setMinimumHeight(140)
            self.body.setMaximumHeight(380)
            self.spin = QProgressBar()
            self.spin.setObjectName("spin")
            self.spin.setRange(0, 0)
            self.spin.hide()
            # footer
            fl = QHBoxLayout()
            self.status = QLabel("")
            self.status.setObjectName("status")
            self.btn_copy = QPushButton("Copy")
            self.btn_copy.setObjectName("btn")
            self.btn_log = QPushButton("Open log")
            self.btn_log.setObjectName("btn")
            self.btn_close = QPushButton("Close")
            self.btn_close.setObjectName("btnPri")
            fl.addWidget(self.status)
            fl.addStretch(1)
            fl.addWidget(self.btn_copy)
            fl.addWidget(self.btn_log)
            fl.addWidget(self.btn_close)
            self.btn_copy.clicked.connect(self._copy)
            self.btn_close.clicked.connect(self.hide)
            self.btn_log.clicked.connect(self._open_log)
            lay.addWidget(self.header)
            lay.addWidget(self.spin)
            lay.addWidget(self.body)
            self.footerW = QWidget()
            self.footerW.setLayout(fl)
            lay.addWidget(self.footerW)
            self.tear_top = QLabel(("\u25b2 " * 40).strip())
            self.tear_top.setObjectName("tear")
            self.tear_top.setAlignment(Qt.AlignCenter)
            self.tear_bot = QLabel(("\u25bc " * 40).strip())
            self.tear_bot.setObjectName("tear")
            self.tear_bot.setAlignment(Qt.AlignCenter)
            root.addWidget(self.tear_top)
            root.addWidget(self.card)
            root.addWidget(self.tear_bot)
            self.tear_top.hide()
            self.tear_bot.hide()
            self._text = ""
            self._full = ""
            self._shown = 0
            self._lines = []
            self._shown_lines = 0
            self._reveal_timer = QTimer(self)
            self._reveal_timer.timeout.connect(self._reveal_step)
            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self.hide)
            # theme extra rows (hidden unless the active theme enables them)
            self.eq_row = QWidget()
            eq_lay = QHBoxLayout(self.eq_row)
            eq_lay.setContentsMargins(0, 2, 0, 2)
            eq_lay.setSpacing(4)
            eq_lay.addStretch(1)
            self._eq_bars = []
            for _ in range(7):
                bar = QLabel()
                bar.setObjectName("eqbar")
                bar.setFixedWidth(10)
                bar.setMinimumHeight(6)
                eq_lay.addWidget(bar)
                self._eq_bars.append(bar)
            eq_lay.addStretch(1)
            self._eq_timer = QTimer(self)
            self._eq_timer.timeout.connect(self._eq_step)
            self.alarm_lbl = QLabel()
            self.alarm_lbl.setObjectName("alarm")
            self.alarm_lbl.setAlignment(Qt.AlignCenter)
            self._alarm_timer = QTimer(self)
            self._alarm_timer.timeout.connect(self._alarm_step)
            self._alarm_on = False
            self.ticker_lbl = QLabel()
            self.ticker_lbl.setObjectName("ticker")
            self._tick_timer = QTimer(self)
            self._tick_timer.timeout.connect(self._tick_step)
            self._tick_text = ""
            self._tick_pos = 0
            lay.insertWidget(2, self.eq_row)
            lay.insertWidget(3, self.alarm_lbl)
            lay.insertWidget(4, self.ticker_lbl)
            self.eq_row.hide()
            self.alarm_lbl.hide()
            self.ticker_lbl.hide()
            self.scan = ScanWidget(self.card)
            self.scan.hide()
            self._floaters = []  # RotLabels, rebuilt per theme
            self._theme = get_theme("obsidian")
            self._theme_id = "obsidian"
            self.apply_theme("obsidian", "")

        def sync_combo(self, provider, model):
            for i in range(self.combo.count()):
                if tuple(self.combo.itemData(i)) == (provider, model):
                    self.combo.blockSignals(True)
                    self.combo.setCurrentIndex(i)
                    self.combo.blockSignals(False)
                    return

        def _on_combo(self, i):
            data = self.combo.itemData(i)
            if data:
                self.model_chosen.emit(data[0], data[1])

        # draggable via header
        def _global_pos(self, e):
            try:
                return e.globalPosition().toPoint()
            except Exception:
                return e.globalPos()

        def mousePressEvent(self, e):
            if self.header.geometry().contains(e.pos()):
                self._drag = self._global_pos(e) - self.frameGeometry().topLeft()
            super().mousePressEvent(e)

        def mouseMoveEvent(self, e):
            if self._drag is not None:
                self.move(self._global_pos(e) - self._drag)
            super().mouseMoveEvent(e)

        def mouseReleaseEvent(self, e):
            self._drag = None
            super().mouseReleaseEvent(e)

        def place_near(self, pos):
            self.adjustSize()
            w, h = self.width() or 420, self.height() or 300
            sc = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            avail = sc.availableGeometry() if sc else QRect(pos.x(), pos.y(), 1600, 900)
            x = min(pos.x() + 18, avail.right() - w - 8)
            y = min(pos.y() + 18, avail.bottom() - h - 8)
            self.move(max(avail.left() + 8, x), max(avail.top() + 8, y))

        def show_loading(self, pos, bbox):
            self._text = ""
            self._reveal_stop()
            self._hide_timer.stop()
            self._extras_stop()
            self.body.setPlainText("")
            self.spin.show()
            if self._theme.get("eq"):
                self.eq_row.show()
                self._eq_timer.start(140)
            if self._theme.get("alarm"):
                self.alarm_lbl.setText(self._theme.get("alarm_text", "⚠"))
                self.alarm_lbl.show()
                self._alarm_on = True
                self._alarm_step()
                self._alarm_timer.start(500)
            self.status.setText(f"Analyzing {bbox[2]}x{bbox[3]} …")
            self.place_near(pos)
            self.show()
            self.raise_()
            self.activateWindow()

        def show_result(self, text, logged=True):
            self._text = text
            self._reveal_stop()
            self._extras_stop()
            self.spin.hide()
            mode = self._theme.get("reveal", "instant")
            if mode == "instant":
                self.body.setPlainText(text)
            elif mode == "type":
                self._full = text
                self._shown = 0
                self.body.setPlainText("")
                self._reveal_timer.start(18)
            else:  # print
                self._lines = text.splitlines(keepends=True) or [text]
                self._shown_lines = 0
                self.body.setPlainText("")
                self._reveal_timer.start(40)
            self.status.setText(self._status_text(
                logged, "saved to analyses.md", "logging off (tray menu)"))
            self.show()
            self.raise_()
            self._arm_autohide()

        def _status_text(self, logged, saved_bit, off_bit):
            base = self._theme.get("status_ok")
            if base is None:
                stamp = datetime.now().strftime("%H:%M:%S") + "  •  "
                base = stamp + (saved_bit if logged else "result ready  •  " + off_bit)
            elif not logged:
                base += "  •  " + off_bit
            return base.replace("{time}", datetime.now().strftime("%H:%M:%S"))

        def show_error(self, text, logged=True):
            self._text = text
            self._reveal_stop()
            self._extras_stop()
            self.spin.hide()
            self.body.setPlainText("ANALYSIS FAILED\n\n" + text)
            err = self._theme.get("status_err")
            if err is None:
                err = ("error  •  attempt saved to analyses.md" if logged
                       else "error  •  not logged (tray menu)")
            elif not logged:
                err += "  •  logging off"
            self.status.setText(err)
            self.show()
            self.raise_()
            self._arm_autohide()

        def _copy(self):
            if self._text:
                QApplication.clipboard().setText(self._text)
                self.status.setText("copied to clipboard")

        def _open_log(self):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_PATH))

        # ---- theming
        def apply_theme(self, theme_id, model_label=""):
            t = get_theme(theme_id)
            self._extras_stop()
            self._theme = t
            self._theme_id = theme_id
            self.setWindowOpacity(min(1.0, t["opacity"] * OPACITY_FACTOR))
            self.setMinimumWidth(t["min_w"])
            self.setMaximumWidth(t["max_w"])
            self.setStyleSheet(t["qss"])
            self.refresh_theme_texts(model_label)
            top = t.get("note_top", "") or (("▲ " * 40).strip() if t.get("tear") else "")
            bot = t.get("note_bot", "") or (("▼ " * 40).strip() if t.get("tear") else "")
            self.tear_top.setText(top)
            self.tear_bot.setText(bot)
            self.tear_top.setVisible(bool(top))
            self.tear_bot.setVisible(bool(bot))
            for fl, _, _, _ in self._floaters:
                try:
                    fl.deleteLater()
                except Exception:
                    pass
            self._floaters = []
            for text, corner, dx, dy, angle, color in t.get("floaters", []):
                fl = RotLabel(text, angle, self.card)
                fl.setObjectName("floater")
                fl.setStyleSheet(f"color: {color}; background: transparent;")
                f = fl.font()
                f.setBold(True)
                fl.setFont(f)
                fl.show()
                self._floaters.append((fl, corner, dx, dy))
            self._place_floaters()
            self.alarm_lbl.setStyleSheet("")
            self.scan.setVisible(bool(t.get("scan")))
            if t.get("ticker"):
                self._tick_text = t.get("ticker_text", "")
                self._tick_pos = 0
                self.ticker_lbl.show()
                self._tick_timer.start(120)
            else:
                self.ticker_lbl.hide()
            if t["footer"] == "hover":
                self.footerW.hide()
            else:
                self.footerW.show()
            self._hide_timer.stop()

        def refresh_theme_texts(self, model_label=""):
            t = self._theme
            title = t["title"]
            if "{model}" in title:
                title = title.format(model=model_label or "?")
            self.title.setText(title)
            self.dot.setText(t["dot"])
            c, l, x = t["buttons"]
            self.btn_copy.setText(c)
            self.btn_log.setText(l)
            self.btn_close.setText(x)

        # ---- progressive reveal (type / print), instant otherwise
        def _reveal_stop(self):
            try:
                self._reveal_timer.stop()
            except Exception:
                pass

        def _reveal_step(self):
            if self._theme.get("reveal") == "print":
                self._shown_lines = min(len(self._lines), self._shown_lines + 3)
                self.body.setPlainText("".join(self._lines[:self._shown_lines]))
                if self._shown_lines >= len(self._lines):
                    self._reveal_timer.stop()
            else:  # type
                self._shown = min(len(self._full), self._shown + 24)
                self.body.setPlainText(self._full[:self._shown])
                if self._shown >= len(self._full):
                    self._reveal_timer.stop()

        # ---- hover footer + auto-hide (stdout-style themes)
        def _arm_autohide(self):
            self._hide_timer.stop()
            if self._theme.get("autohide", 0) and not self.underMouse():
                self._hide_timer.start(self._theme["autohide"] * 1000)

        def enterEvent(self, e):
            self._hide_timer.stop()
            if self._theme.get("footer") == "hover":
                self.footerW.show()
            super().enterEvent(e)

        def leaveEvent(self, e):
            if self._theme.get("footer") == "hover":
                self.footerW.hide()
            self._arm_autohide()
            super().leaveEvent(e)

        def resizeEvent(self, e):
            super().resizeEvent(e)
            try:
                self.scan.setGeometry(QRect(QPoint(0, 0), self.card.size()))
            except Exception:
                pass
            self._place_floaters()

        # ---- theme extras
        def _place_floaters(self):
            try:
                W, H = self.card.width(), self.card.height()
            except Exception:
                return
            for fl, corner, dx, dy in self._floaters:
                try:
                    fl.adjustSize()
                    fw, fh = fl.width(), fl.height()
                    x = dx if corner[1] == "l" else W - fw - dx
                    y = dy if corner[0] == "t" else H - fh - dy
                    fl.move(x, y)
                except Exception:
                    pass

        def _eq_step(self):
            for bar in self._eq_bars:
                try:
                    bar.setFixedHeight(random.randint(6, 34))
                except Exception:
                    pass

        def _alarm_step(self):
            self._alarm_on = not self._alarm_on
            self.alarm_lbl.setStyleSheet(
                "background: #c51111; color: white; font-weight: bold; padding: 4px;" if self._alarm_on
                else "background: #3a0d0d; color: #ff8a8a; font-weight: bold; padding: 4px;")

        def _tick_step(self):
            if not self._tick_text:
                return
            self._tick_pos = (self._tick_pos + 1) % len(self._tick_text)
            window = (self._tick_text + "   " + self._tick_text)
            self.ticker_lbl.setText(window[self._tick_pos:self._tick_pos + 64])

        def _extras_stop(self):
            for timer in (self._eq_timer, self._alarm_timer, self._tick_timer):
                try:
                    timer.stop()
                except Exception:
                    pass
            self.eq_row.hide()
            self.alarm_lbl.hide()

    # ---------------------------------------------------------- analyzer worker
    # Daemon python thread + queued bridge signals (NOT QThread): quitting or
    # re-snipping mid-run can never abort the process, and stale results from
    # a superseded snip are dropped by generation counter.
    import threading

    class _Bridge(QObject):
        done = Signal(object)    # (generation, text)
        failed = Signal(object)  # (generation, error)

    bridge = _Bridge()

    def spawn_analysis(provider, model, png, session, gen):
        def work():
            try:
                text = analyze_dispatch(provider, png,
                                        GEMINI_KEY[0], GO_KEY[0], model,
                                        SYSTEM_PROMPT, USER_PROMPT,
                                        session_id=session)
            except Exception as e:
                try:
                    bridge.failed.emit((gen, str(e)))
                except Exception:
                    pass
                return
            try:
                bridge.done.emit((gen, text))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------- app controller
    app = _app or QApplication(sys.argv[1:])
    app.setQuitOnLastWindowClosed(False)

    overlay = ResultOverlay(SELECTIONS, PROVIDER[0], MODEL[0])
    overlay.apply_theme(THEME[0], LABELS.get((PROVIDER[0], MODEL[0]), MODEL[0]))
    state = {"snip": None, "gen": 0, "bbox": None, "cursor": None,
             "png": b"", "png_path": ""}

    # ---- model selection: single source of truth, both switchers sync here
    tray_actions = {}  # (provider, model) -> QAction

    def persist_selection():
        cfg["provider"] = PROVIDER[0]
        cfg["model"] = MODEL[0]
        if PROVIDER[0] == "go":
            cfg["go_model"] = MODEL[0]
        else:
            cfg["gemini_model"] = MODEL[0]
        save_config(cfg)

    def set_selection(provider, model):
        PROVIDER[0], MODEL[0] = provider, model
        persist_selection()
        overlay.sync_combo(provider, model)
        overlay.refresh_theme_texts(LABELS.get((provider, model), model))
        for key, act in tray_actions.items():
            act.blockSignals(True)
            act.setChecked(key == (provider, model))
            act.blockSignals(False)
        tray.setToolTip(f"SS Analyzer - {LABELS.get((provider, model), model)} "
                        "| Ctrl+LeftAlt+J to snip (right-click: quit)")

    def set_theme(tid):
        THEME[0] = tid
        SETTINGS["theme"] = tid
        save_settings(SETTINGS)
        overlay.apply_theme(tid, LABELS.get((PROVIDER[0], MODEL[0]), MODEL[0]))
        for k, act in theme_actions.items():
            act.blockSignals(True)
            act.setChecked(k == tid)
            act.blockSignals(False)

    def open_keys():
        res = run_setup_wizard(app, GEMINI_KEY[0], GO_KEY[0], first_run=False)
        if res is None:
            return
        save_setup_keys(*res)
        GEMINI_KEY[0] = res[0]
        GO_KEY[0] = res[1]

    def run_analysis(cursor_pos):
        overlay.show_loading(cursor_pos, state["bbox"])
        state["gen"] = state.get("gen", 0) + 1
        spawn_analysis(PROVIDER[0], MODEL[0], state["png"], SESSION_ID, state["gen"])

    # tray (visual proof the app is running; quit lives here)
    tray = QSystemTrayIcon()
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    pt = QPainter(pm)
    pt.setRenderHint(QPainter.Antialiasing)
    pt.setBrush(QColor(79, 124, 255))
    pt.setPen(Qt.NoPen)
    pt.drawRoundedRect(4, 4, 56, 56, 14, 14)
    pt.setPen(QColor(255, 255, 255))
    f = pt.font()
    f.setPixelSize(24)
    f.setBold(True)
    pt.setFont(f)
    pt.drawText(pm.rect(), Qt.AlignCenter, "SS")
    pt.end()
    tray.setIcon(QtGui.QIcon(pm))
    tray.setToolTip(f"SS Analyzer v{VERSION} - {LABELS.get((PROVIDER[0], MODEL[0]), MODEL[0])} "
                    " (right-click: model / quit)")
    menu = QMenu()
    act_snip = menu.addAction("Snip now")
    model_menu = menu.addMenu("Model")
    model_group = QActionGroup(menu)
    model_group.setExclusive(True)
    _last_family = None
    for p, m, label in SELECTIONS:
        family = "Gemini direct" if p == "gemini" else label.split(" ", 1)[0]
        if _last_family is not None and family != _last_family:
            model_menu.addSeparator()
        _last_family = family
        act = model_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked((p, m) == (PROVIDER[0], MODEL[0]))
        act.triggered.connect(lambda _c=False, _p=p, _m=m: set_selection(_p, _m))
        model_group.addAction(act)
        tray_actions[(p, m)] = act
    theme_menu = menu.addMenu("Theme")
    theme_group = QActionGroup(menu)
    theme_group.setExclusive(True)
    theme_actions = {}
    for tid in THEME_ORDER:
        t = THEMES[tid]
        tact = theme_menu.addAction(t["label"])
        tact.setCheckable(True)
        tact.setChecked(tid == THEME[0])
        tact.triggered.connect(lambda _c=False, _t=tid: set_theme(_t))
        theme_group.addAction(tact)
        theme_actions[tid] = tact
    menu.addSeparator()
    act_save = menu.addAction("Save snip PNGs")
    act_save.setCheckable(True)
    act_save.setChecked(bool(SAVE[0]))
    act_save.triggered.connect(lambda c=False: (SAVE.__setitem__(0, bool(c)), persist_ui()))
    act_logtoggle = menu.addAction("Log to analyses.md")
    act_logtoggle.setCheckable(True)
    act_logtoggle.setChecked(bool(LOG[0]))
    act_logtoggle.triggered.connect(lambda c=False: (LOG.__setitem__(0, bool(c)), persist_ui()))
    act_keys = menu.addAction("Set API keys…")
    act_keys.triggered.connect(open_keys)
    act_log = menu.addAction("Open analyses log")
    act_quit = menu.addAction("Quit")
    tray.setContextMenu(menu)
    tray.show()

    def virtual_geometry():
        geos = [s.geometry() for s in QGuiApplication.screens()]
        if not geos:
            return QRect(0, 0, 1920, 1080)
        x1 = min(g.left() for g in geos)
        y1 = min(g.top() for g in geos)
        x2 = max(g.right() for g in geos)
        y2 = max(g.bottom() for g in geos)
        return QRect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)

    def start_snip():
        existing = state["snip"]
        if existing is not None:
            try:
                if existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
            except Exception:
                pass
            # Hidden (150ms confirm window): drop the stray press; the pending
            # capture owns this cycle. Press again after it lands.
            state["snip"] = None
            return
        w = SnipOverlay(virtual_geometry())
        state["snip"] = w
        w.confirmed.connect(on_snip_confirmed)
        w.cancelled.connect(lambda: state.update(snip=None))
        w.show()
        w.raise_()
        w.activateWindow()

    def on_snip_confirmed(x, y, w, h):
        state["snip"] = None
        state["bbox"] = (x, y, w, h)
        try:
            state["cursor"] = QCursor.pos()
        except Exception:
            state["cursor"] = QPoint(x, y)
        # capture (Pillow handles multi-monitor global coords). Any failure
        # here (locked screen, save error, teardown race) becomes an overlay
        # error — never an unhandled slot exception.
        try:
            try:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
            except TypeError:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if SAVE[0]:
                os.makedirs(SNIPS_DIR, exist_ok=True)
                png_path = os.path.join(SNIPS_DIR, f"snip_{ts}.png")
                img.save(png_path, "PNG")
                state["png_path"] = png_path
            else:
                state["png_path"] = "(snip saving off — image kept in memory only)"
            buf = io.BytesIO()
            img.save(buf, "PNG")
            state["png"] = buf.getvalue()
        except Exception as e:
            try:
                overlay.show_error(f"capture failed: {type(e).__name__}: {e}",
                                   logged=False)
            except Exception:
                pass
            return
        run_analysis(state["cursor"])

    def on_done(payload):
        gen, text = payload
        if gen != state.get("gen"):
            return  # superseded by a newer snip
        if LOG[0]:
            append_log(LOG_PATH, MODEL[0], state["bbox"], state.get("png_path", ""),
                       USER_PROMPT, text, provider=PROVIDER[0])
        overlay.show_result(text, logged=LOG[0])

    def on_failed(payload):
        gen, err = payload
        if gen != state.get("gen"):
            return  # superseded by a newer snip
        if LOG[0]:
            append_log(LOG_PATH, MODEL[0], state["bbox"], state.get("png_path", ""),
                       USER_PROMPT, "", error=err, provider=PROVIDER[0])
        overlay.show_error(err, logged=LOG[0])

    bridge.done.connect(on_done)
    bridge.failed.connect(on_failed)

    overlay.model_chosen.connect(lambda p, m: set_selection(p, m))
    signaler.pressed.connect(start_snip)
    act_snip.triggered.connect(start_snip)
    act_log.triggered.connect(overlay._open_log)
    act_quit.triggered.connect(app.quit)

    # register global hotkey on the Qt thread
    u32 = ctypes.windll.user32
    if not u32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_J):
        code = ctypes.GetLastError()
        QtWidgets.QMessageBox.critical(
            None, "SS Analyzer",
            f"Could not register Ctrl+LeftAlt+J (WinError {code}). "
            "Another instance may be running.")
    filt = HotkeyFilter()
    app.installNativeEventFilter(filt)
    app.aboutToQuit.connect(lambda: u32.UnregisterHotKey(None, HOTKEY_ID))

    tray.showMessage(f"SS Analyzer v{VERSION}", "Running. Press Ctrl+LeftAlt+J to snip.",
                     QSystemTrayIcon.Information, 3000)
    print(f"[theme] {THEME[0]} applied ({len(THEME_ORDER)} available)")
    sys.exit(app.exec())


# ---------------------------------------------------------------- entry

def main(argv):
    args = argv[1:]
    cli_model = cli_key = cli_log = cli_theme = None
    setup_only = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--selftest":
            return run_selftest(cli_model, cli_key, cli_log)
        elif a == "--model" and i + 1 < len(args):
            cli_model = args[i + 1]; i += 1
        elif a == "--key" and i + 1 < len(args):
            cli_key = args[i + 1]; i += 1
        elif a == "--log" and i + 1 < len(args):
            cli_log = args[i + 1]; i += 1
        elif a == "--theme" and i + 1 < len(args):
            cli_theme = args[i + 1]; i += 1
        elif a == "--setup":
            setup_only = True
        elif a in ("-h", "--help"):
            print("usage: app.py [--selftest] [--model ID] [--key KEY] [--log PATH] [--theme ID] [--setup]")
            print("  hotkey: Ctrl+LeftAlt+J | keys: GEMINI_API_KEY / OPENCODE_GO_API_KEY env or config.json")
            print(f"  themes: {', '.join(THEME_ORDER)}")
            print("  --setup: (re)run the first-run key wizard and exit")
            return 0
        i += 1
    first_run = not os.path.exists(CONFIG_PATH)
    app = None
    if setup_only or first_run:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            print("PySide6 is missing: run pip install -r requirements.txt first.")
            return 2
        app = QApplication([])
        cfg0 = load_config()
        res = run_setup_wizard(app, cfg0.get("gemini_api_key", "") or "",
                               cfg0.get("opencode_go_api_key", "") or "",
                               first_run=first_run and not setup_only)
        if res is None:
            return 0  # cancelled — leave everything untouched
        save_setup_keys(*res)
        if setup_only:
            print("keys saved to config.json")
            return 0
    return run_gui(cli_model, cli_key, cli_log, cli_theme, _app=app)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except Exception:
        # pythonw has no console: persist the traceback so a
        # flash-and-die launch is diagnosable via crash.log.
        try:
            with open(os.path.join(APP_DIR, "crash.log"), "a", encoding="utf-8") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
                        + traceback.format_exc() + "\n---\n")
        except Exception:
            pass
        raise
