# services/openai_ops.py
import os
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, List

from openai import OpenAI


# ---------- Client ----------
def make_client(api_key: Optional[str] = None) -> OpenAI:
    """
    Return an OpenAI client. Prefer an explicit key; fallback to env var.
    Keeping this small lets Streamlit pass st.secrets cleanly.
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


# ---------- Helpers (local) ----------
def _safe_json_extract(text: str) -> Dict[str, Any]:
    """
    Be lenient with model output: try a direct json.loads; if that fails,
    isolate the first {...} block and parse again. Raise on final failure.
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a top-level JSON object in the text
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # As a last resort, show a readable error
    raise ValueError("Could not parse JSON from model output.")


def _html_fragment_ok(s: str) -> bool:
    """
    We expect a fragment (no <html>/<head>/<body>). Allow tags like section/div/h1…
    """
    if re.search(r"<html\b|<head\b|<body\b|<!DOCTYPE", s, re.I):
        return False
    return bool(re.search(r"<(section|div|article|h[1-6]|p|ul|ol|table)\b", s, re.I))


# ---------- Generation ----------
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
    temperature: float = 0.7,
    max_output_tokens: int = 1800,
) -> Dict[str, Any]:
    """
    Call the LLM to produce a single JSON object with:
      meta, summary, blocks, plan_html_fragment, titles_for_images, talk_track
    and return the parsed dict. We enforce strict “JSON only” in the prompt.
    """
    # Compact schema example (kept brief to reduce tokens; LLM still gets the idea)
    schema_example = {
        "meta": {
            "goal": goal,
            "environment": environment,
            "level": level,
            "duration_min": duration_min,
            "calorie_target": calorie_target,
            "equipment": equipment,
            "constraints": constraints
        },
        "summary": {
            "title": "Example Title",
            "est_total_minutes": duration_min,
            "est_total_kcal": 350
        },
        "blocks": [
            {
                "name": "Warm-up",
                "est_minutes": 6,
                "est_kcal": 30,
                "exercises": [
                    {
                        "title": "March in Place",
                        "prescription": "2 min easy",
                        "rest": "—",
                        "intensity": "RPE 3",
                        "tempo": "",
                        "notes": "Nose breathing, tall posture",
                        "est_kcal": 12,
                        "est_minutes": 2,
                        "equipment": [],
                        "tags": ["cardio", "warmup", "low-impact"]
                    }
                ]
            }
        ],
        "plan_html_fragment": "<section id=\"workout-plan\">...</section>",
        "titles_for_images": ["DB Goblet Squat", "Low-Impact Circuit"],
        "talk_track": f"Hi {name}, this is your motivation text..."
    }

    system_msg = (
        "You are a certified strength & conditioning coach and a professional fitness writer. "
        "You create safe, balanced, goal-driven single-day workouts with precise prescriptions "
        "and concise coaching cues. Follow instructions exactly and return valid JSON."
    )

    user_msg = f"""
Inputs:
- name: {name}
- goal: {goal}
- environment: {environment}
- level: {level}
- duration_min: {duration_min}
- calorie_target: {calorie_target}
- equipment: {equipment}
- constraints: {constraints}

Rules:
1) Fit within duration_min; include Warm-up, 1–3 Main blocks, Cool-down.
2) Respect equipment and constraints; prefer low-impact/regressions if needed.
3) Each exercise includes: title, prescription (sets×reps or time), rest, intensity (RPE/%), optional tempo, brief notes, est_kcal, est_minutes, tags, equipment.
4) Keep estimates realistic and labeled as estimates; if calorie_target exists, aim ±15%.
5) STRICT OUTPUT: Return ONLY a single JSON object with keys:
   meta, summary, blocks, plan_html_fragment, titles_for_images, talk_track.
6) plan_html_fragment MUST BE AN HTML FRAGMENT (no doctype/html/head/body), with minimal inline CSS and neat cards/headers.
7) titles_for_images: 2–5 short titles (blocks or key exercises) for neutral bright images.
8) talk_track: 80–160 words, plain text (no HTML), direct address to {name}; motivating, grounded, safe; no medical claims.

JSON shape example (values are illustrative only):
{json.dumps(schema_example, ensure_ascii=False)}
"""

    # Call Chat Completions with your cheaper model (as requested)
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_output_tokens,  # <- correct for GPT-5 family
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    )

    text = resp.choices[0].message.content
    data = _safe_json_extract(text)

    # Minimal sanity checks
    missing = [k for k in ["meta", "summary", "blocks", "plan_html_fragment", "titles_for_images", "talk_track"] if k not in data]
    if missing:
        raise ValueError(f"Model JSON missing keys: {missing}")

    if not _html_fragment_ok(data["plan_html_fragment"]):
        # We keep going but you may want to warn in UI
        pass

    return data


# ---------- Image generation (stub signature) ----------
def generate_image_dalle2(
    client: OpenAI,
    exercise_title: str,
    assets_dir: Path,
    size: str = "1024x1024"
) -> Path:
    """
    Step 3 will implement:
    - Compose a neutral, bright 'studio' prompt for DALL·E 2.
    - Save one PNG per exercise to assets/images/<safe_title>.png.
    - Return the path; if it already exists, just return it (no API call).
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    # Placeholder path; actual generation will come in Step 3.
    return assets_dir / "placeholder.png"


# ---------- Motivation + TTS (stub signature) ----------
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
    Step 4 will implement:
    - Use gpt-5-nano to create a 120–180 word speech (plain text).
    - Append text to assets/motivation_log.txt (no display).
    - Convert to MP3 via tts-1 and save to assets/audio/<timestamp>.mp3.
    - Return paths and a small status dict (no speech content).
    """
    assets_audio_dir.mkdir(parents=True, exist_ok=True)
    assets_text_log.parent.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "note": "Motivation + TTS will be implemented in Step 4."}
