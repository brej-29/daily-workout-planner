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
    # Every object declares additionalProperties: false
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
                                        "tempo": {"type": "string"},     # present even if ""
                                        "notes": {"type": "string"},
                                        "est_kcal": {"type": "integer"},
                                        "est_minutes": {"type": "integer"},
                                        "equipment": {
                                            "type": "array", "items": {"type": "string"}
                                        },
                                        "tags": {
                                            "type": "array", "items": {"type": "string"}
                                        }
                                    },
                                    # Strict mode: require EVERY key
                                    "required": [
                                        "title","prescription","rest","intensity","tempo",
                                        "notes","est_kcal","est_minutes","equipment","tags"
                                    ]
                                },
                                "maxItems": 2
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
                    "minItems": 2,
                    "maxItems": 4
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
    """
    Chat Completions + Structured Outputs (JSON Schema) kwargs for GPT-5 family:
    - DO NOT send temperature/top_p/penalties (can 400).
    - Use max_completion_tokens (not max_tokens).
    """
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
    """
    Builds a short debug string (finish_reason + usage) to attach in exceptions.
    """
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
    Deterministic minimal HTML fragment built locally from the core JSON.
    Used when the model returns an empty/too-small plan_html_fragment.
    """
    title = core.get("summary", {}).get("title", "Your Workout")
    meta = core.get("meta", {})
    blocks = core.get("blocks", [])

    # Minimal, clean inline styles (fragment only)
    css = """
    <style>
      .wp-wrap {font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial, sans-serif; line-height:1.5;}
      .wp-title {font-size: 1.6rem; font-weight: 700; margin: 0 0 0.5rem 0;}
      .wp-meta {display:flex; gap:0.75rem; flex-wrap:wrap; color:#444; font-size:0.95rem; margin-bottom:1rem;}
      .wp-card {border:1px solid #eee; border-radius:14px; padding:16px; margin:12px 0; box-shadow:0 1px 8px rgba(0,0,0,0.04);}
      .wp-card h3 {margin:0 0 0.5rem 0; font-size:1.15rem;}
      .wp-ex {margin:0.35rem 0; padding-left:1rem;}
      .wp-tag {display:inline-block; font-size:0.75rem; background:#f5f5f5; padding:2px 8px; border-radius:999px; margin-right:6px;}
    </style>
    """

    meta_bits = []
    if meta.get("goal"): meta_bits.append(f"Goal: <b>{meta['goal']}</b>")
    if meta.get("environment"): meta_bits.append(f"Env: <b>{meta['environment']}</b>")
    if meta.get("level"): meta_bits.append(f"Level: <b>{meta['level']}</b>")
    if meta.get("duration_min") is not None: meta_bits.append(f"Duration: <b>{meta['duration_min']} min</b>")

    html = [f'<section id="workout-plan" class="wp-wrap">', css]
    html.append(f'<h2 class="wp-title">{title}</h2>')
    if meta_bits:
        html.append(f'<div class="wp-meta">{" • ".join(meta_bits)}</div>')

    for blk in blocks:
        bname = blk.get("name", "Block")
        mins = blk.get("est_minutes")
        kcal = blk.get("est_kcal")
        meta_line = []
        if mins is not None: meta_line.append(f"{mins} min")
        if kcal is not None: meta_line.append(f"~{kcal} kcal")
        html.append('<div class="wp-card">')
        html.append(f"<h3>{bname}" + (f" ({', '.join(meta_line)})" if meta_line else "") + "</h3>")

        for ex in blk.get("exercises", []):
            title = ex.get("title", "Exercise")
            presc = ex.get("prescription", "")
            rest = ex.get("rest", "")
            intensity = ex.get("intensity", "")
            notes = ex.get("notes", "")
            line = f"<li><b>{title}</b>"
            details = []
            if presc: details.append(presc)
            if rest: details.append(f"Rest: {rest}")
            if intensity: details.append(intensity)
            if notes: details.append(notes)
            if details:
                line += f" — " + "; ".join(details)
            line += "</li>"
            html.append(f'<ul class="wp-ex">{line}</ul>')
        html.append("</div>")

    html.append("</section>")
    return "".join(html)

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
    model: str = "gpt-5-nano",
    max_output_tokens: int = 3200,
) -> Dict[str, Any]:
    """
    Two-pass generation with JSON Schema on Chat Completions.
    - Pass 1: core JSON (small)
    - Pass 2: view JSON (HTML fragment + talk_track)
    If GPT-5-nano returns empty/length, AUTO-FALLBACK to gpt-4o-mini.
    Also: if plan_html_fragment is empty/too short, we build a clean local fragment.
    """
    primary_model = model or "gpt-5-nano"
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
        "Design a single-day workout that safely fits within duration_min. "
        "Include exactly 3 blocks: Warm-up, Main, Cool-down. "
        "Limits: ONE Main block; ≤2 exercises/block; notes ≤8 words; realistic numbers. "
        "Tempo may be an empty string if not relevant, but the 'tempo' field must be present. "
        "Return ONLY valid JSON per the schema; keep values compact."
    )

    def call_core(m: str, compact_retry: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
        schema = _core_schema()
        msg = user1 if not compact_retry else (
            f"Inputs: name={name}; goal={goal}; env={environment}; level={level}; "
            f"duration_min={duration_min}; calorie_target={calorie_target}; "
            f"equipment={equipment}; constraints={constraints}\n\n"
            "Return ONLY valid JSON (per schema) with: meta, summary, 3 blocks (Warm-up/Main/Cool-down), "
            "max 1 exercise per block (notes ≤6 words), tempo='' if not relevant, titles_for_images (2–3 strings)."
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

    use_model_for_view = primary_model if "meta" in core else fallback_model
    view, vdbg = call_view(use_model_for_view, compact_retry=False)
    if not view:
        view, vdbg2 = call_view(use_model_for_view, compact_retry=True)
        if not view:
            view, vdbg3 = call_view(fallback_model, compact_retry=True)
            if not view:
                raise ValueError(f"Empty response from model (pass 2). Debug: main {vdbg}; retry {vdbg2}; fallback {vdbg3}")

    # ========= Ensure we always return a good HTML fragment =========
    frag = (view.get("plan_html_fragment") or "").strip()
    if (not frag) or ("<" not in frag) or ("workout-plan" not in frag and "<div" not in frag and "<section" not in frag):
        # Build a clean local fragment from the core JSON
        frag = _html_fragment_from_core(core)

    talk_track = (view.get("talk_track") or "").strip()
    if not talk_track:
        # Minimal talk_track if the model omitted it
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

# =============== Stubs for next steps ===============
def generate_image_dalle2(
    client: OpenAI,
    exercise_title: str,
    assets_dir: Path,
    size: str = "1024x1024"
) -> Path:
    """
    Step 3 will implement DALL·E 2 generation with on-disk caching.
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir / "placeholder.png"

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
    """
    Step 4 will implement: motivation text append + TTS MP3 save.
    """
    assets_audio_dir.mkdir(parents=True, exist_ok=True)
    assets_text_log.parent.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "note": "Will be implemented in Step 4."}
