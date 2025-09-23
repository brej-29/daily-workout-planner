# services/openai_ops.py
import os
import json
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from openai import OpenAI

# =============== Client ===============
def make_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=key)

# =============== Schemas (strict) ===============
def _core_schema() -> Dict[str, Any]:
    # Allow up to 3 exercises per block (we’ll steer distribution via the prompt)
    return {
        "name": "core_workout_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "meta": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "goal": {"type": "string"},
                        "environment": {"type": "string"},
                        "level": {"type": "string"},
                        "duration_min": {"type": "integer"},
                        "calorie_target": {"type": ["integer", "null"]},
                        "equipment": {"type": "array", "items": {"type": "string"}},
                        "constraints": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": [
                        "goal","environment","level","duration_min",
                        "calorie_target","equipment","constraints"
                    ]
                },
                "summary": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "est_total_minutes": {"type": "integer"},
                        "est_total_kcal": {"type": "integer"}
                    },
                    "required": ["title","est_total_minutes","est_total_kcal"]
                },
                "blocks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "est_minutes": {"type": "integer"},
                            "est_kcal": {"type": "integer"},
                            "exercises": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "title": {"type": "string"},
                                        "prescription": {"type": "string"},
                                        "rest": {"type": "string"},
                                        "intensity": {"type": "string"},
                                        "tempo": {"type": "string"},     # must be present; "" allowed
                                        "notes": {"type": "string"},
                                        "est_kcal": {"type": "integer"},
                                        "est_minutes": {"type": "integer"},
                                        "equipment": {"type": "array", "items": {"type": "string"}},
                                        "tags": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": [
                                        "title","prescription","rest","intensity","tempo",
                                        "notes","est_kcal","est_minutes","equipment","tags"
                                    ]
                                },
                                "maxItems": 3
                            }
                        },
                        "required": ["name","est_minutes","est_kcal","exercises"]
                    },
                    "minItems": 3,
                    "maxItems": 3
                },
                "titles_for_images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 6
                }
            },
            "required": ["meta","summary","blocks","titles_for_images"]
        }
    }

def _view_schema() -> Dict[str, Any]:
    return {
        "name": "view_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "plan_html_fragment": {"type": "string"},
                "talk_track": {"type": "string"}
            },
            "required": ["plan_html_fragment","talk_track"]
        }
    }

# =============== Helpers ===============
def _build_chat_kwargs(
    *,
    model: str,
    messages: List[Dict[str, str]],
    json_schema: Dict[str, Any],
    max_completion_tokens: int
) -> Dict[str, Any]:
    # Chat Completions + JSON Schema
    return {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_schema", "json_schema": json_schema},
        "max_completion_tokens": max_completion_tokens
    }

def _parse_json_or_raise(text: str, ctx: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError(f"Empty response from model ({ctx}).")
    try:
        return json.loads(text)
    except Exception as e:
        snippet = text[:600].replace("\n", "\\n")
        raise ValueError(
            f"Could not parse JSON from model output ({ctx}). Snippet: {snippet}"
        ) from e

def _first_choice_debug_payload(resp) -> str:
    try:
        ch = resp.choices[0]
        fr = getattr(ch, "finish_reason", None)
        usage = getattr(resp, "usage", None)
        if usage:
            return f"(finish_reason={fr}, completion_tokens={usage.completion_tokens}, prompt_tokens={usage.prompt_tokens})"
        return f"(finish_reason={fr})"
    except Exception:
        return "(no debug)"

def _html_fragment_from_core(core: Dict[str, Any]) -> str:
    """
    Build a clean, website-style HTML fragment from the core JSON with:
      • Inline meta row: "Goal: ... • Env: ... • Level: ... • Duration: ... min"
      • Block headings: "Warm-up (10 min, ~30 kcal)"
      • Exercises: "Title — prescription; Rest: ...; Intensity: ...; Notes: ...; (~N min)"
    """
    title = core.get("summary", {}).get("title", "Single-Day Workout Plan")
    meta = core.get("meta", {})
    blocks = core.get("blocks", [])

    css = """
    <style>
      .wp-wrap{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Arial,sans-serif;line-height:1.55}
      .wp-title{font-size:1.6rem;font-weight:700;margin:0 0 .5rem 0}
      .wp-meta{color:#bbb;font-size:.95rem;margin:.25rem 0 1rem 0}
      .wp-card{border:1px solid #eee;border-radius:14px;padding:16px;margin:12px 0;box-shadow:0 1px 8px rgba(0,0,0,.05);background:#e0e0e0}
      .wp-card h3{margin:0 0 .5rem 0;font-size:1.1rem}
      .wp-ex{margin:.35rem 0;padding-left:1rem}
      .wp-ex li{margin:.25rem 0}
      .muted{color:#ddd}
    </style>
    """

    # Meta line: Goal • Env • Level • Duration
    meta_items = []
    if meta.get("goal"): meta_items.append(f"Goal: <b>{meta['goal']}</b>")
    if meta.get("environment"): meta_items.append(f"Env: <b>{meta['environment']}</b>")
    if meta.get("level"): meta_items.append(f"Level: <b>{meta['level']}</b>")
    if meta.get("duration_min") is not None: meta_items.append(f"Duration: <b>{meta['duration_min']} min</b>")
    meta_line = " • ".join(meta_items)

    out = [f'<section id="workout-plan" class="wp-wrap">', css]
    out.append(f'<h2 class="wp-title">{title}</h2>')
    if meta_line:
        out.append(f'<div class="wp-meta">{meta_line}</div>')

    # Blocks
    for blk in blocks:
        bname = blk.get("name", "Block")
        mins = blk.get("est_minutes")
        kcal = blk.get("est_kcal")
        head_bits = []
        if mins is not None: head_bits.append(f"{mins} min")
        if kcal is not None: head_bits.append(f"~{kcal} kcal")
        head_sfx = f" ({', '.join(head_bits)})" if head_bits else ""
        out.append('<div class="wp-card">')
        out.append(f"<h3>{bname}{head_sfx}</h3>")

        out.append('<ul class="wp-ex">')
        for ex in blk.get("exercises", []):
            t = ex.get("title", "Exercise")
            presc = ex.get("prescription", "").strip()
            rest = ex.get("rest", "").strip()
            intensity = ex.get("intensity", "").strip()
            notes = ex.get("notes", "").strip()
            est_m = ex.get("est_minutes")
            details = []
            if presc: details.append(presc)
            if rest: details.append(f"Rest: {rest}")
            if intensity: details.append(f"Intensity: {intensity}")
            if notes: details.append(f"Notes: {notes}")
            if est_m is not None: details.append(f"(~{est_m} min)")
            details_str = " — " + "; ".join(details) if details else ""
            out.append(f"<li><b>{t}</b>{details_str}</li>")
        out.append("</ul>")
        out.append("</div>")

    out.append("</section>")
    return "".join(out)

# =============== Public API ===============
def generate_workout_plan(
    client: OpenAI,
    *,
    name: str,
    goal: str,
    environment: str,
    level: str,
    duration_min: int,
    calorie_target: Optional[int],
    equipment: List[str],
    constraints: List[str],
    model: str = "gpt-4o-mini",           # <-- default to 4o-mini for reliability + low cost
    max_output_tokens: int = 3200,
) -> Dict[str, Any]:
    """
    Two-pass generation with JSON Schema on Chat Completions.
    - Pass 1: core JSON (small)
    - Pass 2: view JSON (HTML fragment + talk_track)
    Use 4o-mini by default (cheapest reliable); optional fallback stays 4o-mini.
    """
    primary_model = model or "gpt-4o-mini"
    fallback_model = "gpt-4o-mini"

    # ---------- PASS 1 (Core) ----------
    sys1 = (
        "You are a certified strength & conditioning coach. "
        "Return data that strictly matches the provided JSON Schema."
    )
    user1 = (
        f"Inputs: name={name}; goal={goal}; env={environment}; level={level}; "
        f"duration_min={duration_min}; calorie_target={calorie_target}; "
        f"equipment={equipment}; constraints={constraints}\n\n"
        "Design a SINGLE-DAY workout that fits within duration_min.\n"
        "Blocks: exactly 3 → Warm-up, Main, Cool-down.\n"
        "Exercise counts: Warm-up ≤2; Main ≤3; Cool-down ≤2.\n"
        "Keep notes ≤10 words; numbers realistic. 'tempo' must be present ('' if not relevant).\n"
        "Return ONLY valid JSON per the schema; keep values compact."
    )

    def call_core(m: str, compact_retry: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
        schema = _core_schema()
        msg = user1 if not compact_retry else (
            f"Inputs: name={name}; goal={goal}; env={environment}; level={level}; "
            f"duration_min={duration_min}; calorie_target={calorie_target}; "
            f"equipment={equipment}; constraints={constraints}\n\n"
            "Return ONLY JSON (per schema) with meta, summary, 3 blocks (Warm-up/Main/Cool-down). "
            "Warm-up≤2, Main≤3, Cool-down≤2 exercises. notes≤8w, tempo='' allowed. titles_for_images 3–5."
        )
        kwargs = _build_chat_kwargs(
            model=m,
            messages=[{"role": "system", "content": sys1}, {"role": "user", "content": msg}],
            json_schema=schema,
            max_completion_tokens=min(max_output_tokens, 2500 if not compact_retry else 1800),
        )
        resp = client.chat.completions.create(**kwargs)
        debug = _first_choice_debug_payload(resp)
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return {}, debug
        return _parse_json_or_raise(text, f"pass 1 ({m})"), debug

    core, dbg = call_core(primary_model, compact_retry=False)
    if not core:
        core, dbg2 = call_core(primary_model, compact_retry=True)
        if not core:
            core, dbg3 = call_core(fallback_model, compact_retry=True)
            if not core:
                raise ValueError(f"Empty response from model (pass 1). Debug: primary {dbg}; retry {dbg2}; fallback {dbg3}")

    for k in ["meta", "summary", "blocks", "titles_for_images"]:
        if k not in core:
            raise ValueError(f"Core JSON missing key: {k}")

    # ---------- PASS 2 (View) ----------
    sys2 = (
        "You are a professional fitness writer & frontend editor. "
        "Return data strictly matching the provided JSON Schema."
    )
    core_compact = json.dumps(core, separators=(",", ":"), ensure_ascii=False)
    user2 = (
        f"Build display + motivation for this workout JSON: {core_compact}\n\n"
        f"Constraints: plan_html_fragment MUST be an HTML FRAGMENT (no doctype/html/head/body), "
        f"minimal inline CSS, compact cards/headers. talk_track: 90–110 words, plain text, address {name}, "
        "motivating and safe; no medical claims. Return ONLY valid JSON per the schema."
    )

    def call_view(m: str, compact_retry: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
        schema = _view_schema()
        msg = user2 if not compact_retry else (
            f"Display for: {core_compact}\n"
            f"Return ONLY JSON with: plan_html_fragment (tiny HTML fragment) and "
            f"talk_track (≤90 words, plain text to {name})."
        )
        kwargs = _build_chat_kwargs(
            model=m,
            messages=[{"role": "system", "content": sys2}, {"role": "user", "content": msg}],
            json_schema=schema,
            max_completion_tokens=min(max_output_tokens, 900 if not compact_retry else 700),
        )
        resp = client.chat.completions.create(**kwargs)
        debug = _first_choice_debug_payload(resp)
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return {}, debug
        return _parse_json_or_raise(text, f"pass 2 ({m})"), debug

    view, vdbg = call_view(primary_model, compact_retry=False)
    if not view:
        view, vdbg2 = call_view(primary_model, compact_retry=True)
        if not view:
            view, vdbg3 = call_view(fallback_model, compact_retry=True)
            if not view:
                raise ValueError(f"Empty response from model (pass 2). Debug: main {vdbg}; retry {vdbg2}; fallback {vdbg3}")

    # Ensure a good HTML fragment, even if the model skimps
    frag = _html_fragment_from_core(core)

    talk_track = (view.get("talk_track") or "").strip()
    if not talk_track:
        tt_name = name or "athlete"
        talk_track = (
            f"{tt_name}, this session is your next step. Stay smooth in the warm-up, put focused energy into the main block, "
            "and use the cool-down to lock in good form. Keep breaths steady and posture tall. You’re here, you’re capable, "
            "and every rep builds momentum. Let’s get the work done—one set at a time."
        )

    return {
        "meta": core["meta"],
        "summary": core["summary"],
        "blocks": core["blocks"],
        "titles_for_images": core["titles_for_images"],
        "plan_html_fragment": frag,
        "talk_track": talk_track,
    }

# =============== Image Generation ===============
def generate_image_dalle2(
    client: OpenAI,
    exercise_title: str,
    assets_dir: Path,
    *,
    meta: Dict[str, Any] | None = None,
    size: str = "1024x1024",
    force_regen: bool = False,
) -> Path:
    """
    Generate (or load from cache) a DALL·E-2 image for a single exercise.
    Saves to assets_dir/<safe-exercise-name>.png and returns the Path.

    - If force_regen=False and file already exists -> no API call (instant).
    - Uses a structured, safe prompt with neutral background.
    """
    import re
    import requests
    from utils.parse import safe_filename

    assets_dir.mkdir(parents=True, exist_ok=True)

    # Normalize/sanitize title -> filename
    title_clean = re.sub(r"\s+", " ", exercise_title or "").strip(" '\"\t\r\n")
    filename = safe_filename(title_clean, suffix=".png")
    out_path = assets_dir / filename

    if out_path.exists() and not force_regen:
        return out_path

    # Build a concise, consistent prompt
    meta = meta or {}
    goal = meta.get("goal", "General fitness")
    environment = meta.get("environment", "Gym")
    level = meta.get("level", "Beginner")

    # DALL·E-2 works best with a short, concrete description.
    # Keep it object-centric; avoid depicting real persons (policy-safe, reusable).
    prompt = f"""
High-quality instructional image for a single fitness exercise.
Exercise: "{title_clean}"
Context: {goal} program, {environment} setting, level: {level}.
Composition rules:
- Single subject (no face), neutral/white background.
- Clear view of body position and main implement (if any).
- Clean lines, balanced contrast, no text, no logos, no watermarks.
- Style: crisp studio illustration (not cartoon), photoreal-inspired, minimal shadows.
Output: one centered shot that clearly demonstrates the exercise setup or peak position.
""".strip()

    # Call Images API (DALL·E-2 returns a URL)
    resp = client.images.generate(
        model="dall-e-2",
        prompt=prompt,
        size=size,
        n=1,
    )
    try:
        image_url = resp.data[0].url
    except Exception as e:
        raise RuntimeError(f"Image API returned no URL for '{exercise_title}': {e}")

    # Download and save
    r = requests.get(image_url, stream=True, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch image URL for '{exercise_title}': HTTP {r.status_code}")
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return out_path


# =============== Speech naration ===============

def generate_motivation_and_tts(
    client: OpenAI,
    *,
    name: str,
    meta: Dict[str, Any],
    summary: Dict[str, Any],
    assets_text_log: Path,
    assets_audio_dir: Path,
    tts_voice: str = "alloy"
) -> Dict[str, Any]:
    assets_audio_dir.mkdir(parents=True, exist_ok=True)
    assets_text_log.parent.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "note": "Will be implemented in Step 4."}
