# app.py
import os
import logging
from typing import List
from pathlib import Path

import streamlit as st

from services.openai_ops import make_client, generate_workout_plan, generate_image_dalle2, generate_motivation_and_tts
from utils.exporters import compose_export_html, to_pdf_with_playwright
from utils.ui import render_html_fragment

# ---------- Page & Logging ----------
st.set_page_config(page_title="Daily Workout Planner", page_icon="🏋️", layout="wide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("workout_planner")

# ---------- Constants ----------
GOALS: List[str] = ["Fat loss", "General fitness", "Strength", "Hypertrophy", "Endurance", "Mobility/Recovery"]
ENVIRONMENTS: List[str] = ["Gym", "Home"]
LEVELS: List[str] = ["Beginner", "Intermediate", "Advanced"]

EQUIPMENT_POOL: List[str] = [
    "Bodyweight", "Mat", "Bands", "Dumbbells", "Kettlebell", "Barbell",
    "Bench", "Pull-up Bar", "Cable/Machines", "Jump Rope",
    "Treadmill", "Bike", "Rower", "Elliptical"
]

CONSTRAINTS: List[str] = [
    "Low-impact only",
    "Protect knees",
    "Protect shoulders",
    "Protect back",
    "No jumping",
    "Small space / no running"
]

# ---------- Session State Defaults ----------
def _init_state() -> None:
    defaults = {
        "goal": GOALS[1],                    # "General fitness"
        "environment": ENVIRONMENTS[0],      # "Gym"
        "level": LEVELS[0],                  # "Beginner"
        "duration_min": 45,
        "use_calorie_target": False,
        "calorie_target": 400,
        "equipment": [],
        "constraints": [],
        "tts_voice": "alloy",
        "name": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# --- UI polish: typography + cards + subtle hover ---
st.markdown("""
<style>
/* Base type & spacing */
html, body, [data-testid="stAppViewContainer"] { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Arial, sans-serif; }
h1, h2, h3 { letter-spacing: .2px; }
.block-container { padding-top: 1.2rem; padding-bottom: 2.0rem; }

/* Card look for containers */
.app-card { border: 1px solid #eee; border-radius: 16px; padding: 14px 16px; background: #fff; box-shadow: 0 1px 10px rgba(0,0,0,.05); }
.app-card:hover { box-shadow: 0 2px 16px rgba(0,0,0,.07); }

/* Buttons */
div.stButton > button { border-radius: 10px; padding: .55rem .9rem; font-weight: 600; }

/* Download buttons */
button[kind="secondary"] { border-radius: 10px; }

/* Small pill chips */
.pill { display:inline-block; padding:2px 10px; border-radius:999px; background:#f4f4f4; font-size:.85rem; color:#444; margin-right:6px; }

/* Make images look neat */
.app-thumb { border-radius: 12px; border: 1px solid #eee; }

/* Dark mode friendly tweaks */
@media (prefers-color-scheme: dark) {
  .app-card { border-color: #2a2a2a; background:#111; box-shadow: none; }
  .pill { background:#1d1d1d; color:#ddd; }
}
</style>
""", unsafe_allow_html=True)

# ---------- Assets ----------
ASSETS_DIR = Path("assets")
ASSETS_IMAGES = ASSETS_DIR / "images"
ASSETS_AUDIO = ASSETS_DIR / "audio"
ASSETS_TEXT = ASSETS_DIR / "text"
ASSETS_TEXT.mkdir(parents=True, exist_ok=True)
MOTIVATION_LOG = ASSETS_TEXT / "motivation_log.txt"
ASSETS_DIR.mkdir(exist_ok=True)
ASSETS_IMAGES.mkdir(parents=True, exist_ok=True)
ASSETS_AUDIO.mkdir(parents=True, exist_ok=True)

# ---------- OpenAI client ----------
API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not API_KEY:
    st.sidebar.error("Missing OPENAI_API_KEY in .streamlit/secrets.toml or env")
    st.stop()
client = make_client(API_KEY)

# ---------- Sidebar: Input Form ----------
with st.sidebar:
    st.title("🧭 Plan Setup")
    with st.form("setup_form", clear_on_submit=False):
        goal = st.selectbox("Goal", GOALS, index=GOALS.index(st.session_state.goal))
        environment = st.radio("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(st.session_state.environment), horizontal=True)
        level = st.selectbox("Experience level", LEVELS, index=LEVELS.index(st.session_state.level))
        duration_min = st.slider("Session duration (minutes)", min_value=20, max_value=120, value=st.session_state.duration_min, step=5)

        st.markdown("---")
        use_calorie_target = st.checkbox("Set calorie-burn target (optional)", value=st.session_state.use_calorie_target)
        calorie_target = None
        if use_calorie_target:
            calorie_target = st.number_input("Calories to burn (kcal)", min_value=100, max_value=1200, value=st.session_state.calorie_target, step=25)

        st.markdown("---")
        equipment = st.multiselect("Available equipment (optional)", options=EQUIPMENT_POOL, default=st.session_state.equipment)
        constraints = st.multiselect("Constraints (optional)", options=CONSTRAINTS, default=st.session_state.constraints)

        st.markdown("---")
        name = st.text_input("Your name (for motivation later)", value=st.session_state.get("name", ""))

        tts_voice = st.selectbox(
            "TTS voice",
            options=["alloy", "verse", "coral", "sage", "ash"],
            index=0,
            help="Voice used for the motivation speech"
        )
        submitted = st.form_submit_button("Save plan settings")

if submitted:
    st.session_state.goal = goal
    st.session_state.environment = environment
    st.session_state.level = level
    st.session_state.duration_min = int(duration_min)
    st.session_state.use_calorie_target = bool(use_calorie_target)
    if use_calorie_target:
        st.session_state.calorie_target = int(calorie_target)
    st.session_state.equipment = list(equipment)
    st.session_state.constraints = list(constraints)
    st.session_state.name = name.strip()
    st.session_state.tts_voice = tts_voice
    logger.info("Saved plan settings: %s", {
        "goal": st.session_state.goal,
        "environment": st.session_state.environment,
        "level": st.session_state.level,
        "duration_min": st.session_state.duration_min,
        "use_calorie_target": st.session_state.use_calorie_target,
        "calorie_target": st.session_state.calorie_target if st.session_state.use_calorie_target else None,
        "equipment": st.session_state.equipment,
        "constraints": st.session_state.constraints
    })
    st.sidebar.success("Saved! Settings updated.")

# ---------- Main Preview ----------
st.title("🏋️ Daily Workout Planner (Step 2)")
st.caption("AI plan generation wired with structured JSON (Chat Completions + JSON Schema).")

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("Your plan settings")
    st.markdown(f"**Goal:** {st.session_state.goal}")
    st.markdown(f"**Environment:** {st.session_state.environment}")
    st.markdown(f"**Level:** {st.session_state.level}")
    st.markdown(f"**Duration:** {st.session_state.duration_min} minutes")
    if st.session_state.use_calorie_target:
        st.markdown(f"**Calorie target:** {st.session_state.calorie_target} kcal (optional)")
    st.markdown("**Equipment:** " + (", ".join(st.session_state.equipment) if st.session_state.equipment else "_not specified_"))
    st.markdown("**Constraints:** " + (", ".join(st.session_state.constraints) if st.session_state.constraints else "_none_"))

with col_right:
    st.subheader("Next up")
    st.write("• Per-exercise DALL·E 2 images with on-disk caching.")
    st.write("• Motivation audio: generate/append text and save MP3.")

st.markdown("---")
st.subheader("Generate AI Workout Plan")
generate_clicked = st.button("⚡ Generate Workout Plan")

if generate_clicked:
    if not st.session_state.get("name"):
        st.warning("Please enter your name in the sidebar (for motivation later).")
    else:
        try:
            with st.spinner("Contacting coach..."):
                plan = generate_workout_plan(
                    client,
                    name=st.session_state.get("name", "Athlete"),
                    goal=st.session_state.goal,
                    environment=st.session_state.environment,
                    level=st.session_state.level,
                    duration_min=int(st.session_state.duration_min),
                    calorie_target=int(st.session_state.calorie_target) if st.session_state.use_calorie_target else None,
                    equipment=list(st.session_state.equipment),
                    constraints=list(st.session_state.constraints),
                    model="gpt-4o-mini",
                    max_output_tokens=3200
                )
                st.session_state.plan = plan
                st.success("Plan generated.")
        except Exception as e:
            st.error(f"Failed to generate plan: {e}")

# --- Summary metrics row (duration + kcal) ---
if "plan" in st.session_state:
    _sum = st.session_state.plan.get("summary", {}) or {}
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        st.metric("Duration", f"{_sum.get('est_total_minutes','--')} min")
    with c2:
        st.metric("Est. Burn", f"{_sum.get('est_total_kcal','--')} kcal")
    with c3:
        meta = st.session_state.plan.get("meta", {}) or {}
        line = f"<span class='pill'>Goal: {meta.get('goal','-')}</span> " \
               f"<span class='pill'>Env: {meta.get('environment','-')}</span> " \
               f"<span class='pill'>Level: {meta.get('level','-')}</span>"
        st.markdown(line, unsafe_allow_html=True)

# Render plan if present (TABS)
if "plan" in st.session_state:
    tab_plan, tab_images, tab_export, tab_audio = st.tabs(["📋 Plan", "🖼️ Images", "📤 Export", "🎧 Audio"])

    plan = st.session_state.plan
    html_fragment = (plan.get("plan_html_fragment") or "").strip()
    title_text = plan.get("summary", {}).get("title", "Your Workout Plan")

    # ---- PLAN TAB ----
    with tab_plan:
        # Avoid duplicate title: if fragment already has an H1/H2, skip the outer subheader
        frag_has_title = ("<h1" in html_fragment.lower()) or ("<h2" in html_fragment.lower())
        if not frag_has_title:
            st.subheader(title_text)

        if html_fragment:
            st.markdown("<div class='app-card'>", unsafe_allow_html=True)
            render_html_fragment(html_fragment, height=1100)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("No HTML fragment returned; using fallback renderer failed. Please try again.")

    # ---- IMAGES TAB ----
    with tab_images:
        st.markdown("#### Cached Gallery")
        cached_pngs = sorted(ASSETS_IMAGES.glob("*.png"))
        if cached_pngs:
            cols = st.columns(4)
            for idx, p in enumerate(cached_pngs[:12]):
                with cols[idx % 4]:
                    st.image(str(p), width="stretch", caption=p.stem, output_format="PNG")
        else:
            st.caption("No cached images yet. Generate images below.")

        st.markdown("---")
        st.markdown("#### Exercise Images")
        st.caption("Generate images one-by-one. Cached images won’t re-generate.")

        # Build a unique, ordered list of exercise titles from blocks
        exercise_titles = []
        blocks = (plan.get("blocks") or [])
        for blk in blocks:
            for ex in blk.get("exercises", []):
                t = (ex.get("title") or "").strip()
                if t and t not in exercise_titles:
                    exercise_titles.append(t)

        exercise_titles = exercise_titles[:10]  # keep UI manageable

        if not exercise_titles:
            st.info("No exercises found in the plan.")
        else:
            from utils.parse import safe_filename
            meta = (plan.get("meta") or {})

            for i, t in enumerate(exercise_titles, start=1):
                c1, c2, c3 = st.columns([3, 1.1, 1])

                with c1:
                    # Show the exercise title and block name
                    block_name = None
                    for blk in blocks:
                        if any((ex.get("title") or "").strip() == t for ex in blk.get("exercises", [])):
                            block_name = blk.get("name")
                            break
                    if block_name:
                        st.write(f"**{i}. {t}**  \n<span class='st-emotion-cache-kwuqc'>_Block: {block_name}_</span>", unsafe_allow_html=True)
                    else:
                        st.write(f"**{i}. {t}**")

                    # Optional: details expander (no logic change)
                    ex_details = None
                    for blk in blocks:
                        for ex in blk.get("exercises", []):
                            if (ex.get("title") or "").strip() == t:
                                ex_details = ex
                                break
                        if ex_details: break
                    if ex_details:
                        with st.expander("View details", expanded=False):
                            st.markdown(f"**Prescription:** {ex_details.get('prescription','-')}")
                            st.markdown(f"**Rest:** {ex_details.get('rest','-')}")
                            st.markdown(f"**Intensity:** {ex_details.get('intensity','-')}")
                            notes = ex_details.get('notes','')
                            if notes:
                                st.caption(f"Notes: {notes}")

                # cached preview slot
                cached = (ASSETS_IMAGES / safe_filename(t, suffix=".png"))
                with c2:
                    if cached.exists():
                        st.image(str(cached), width="stretch", caption="Cached")
                    else:
                        st.empty()

                with c3:
                    gen_key = f"gen_btn_{i}"
                    regen_key = f"regen_btn_{i}"

                    # Remove deprecated/invalid use_container_width on buttons
                    if st.button("Generate image", key=gen_key):
                        try:
                            with st.spinner("Generating…"):
                                img_path = generate_image_dalle2(
                                    client,
                                    exercise_title=t,
                                    assets_dir=ASSETS_IMAGES,
                                    meta=meta,
                                    size="1024x1024",
                                    force_regen=False,  # only if not cached
                                )
                            st.toast(f"Image ready: {img_path.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Image failed: {e}")

                    if st.button("Regenerate", key=regen_key):
                        try:
                            with st.spinner("Re-generating…"):
                                img_path = generate_image_dalle2(
                                    client,
                                    exercise_title=t,
                                    assets_dir=ASSETS_IMAGES,
                                    meta=meta,
                                    size="1024x1024",
                                    force_regen=True,
                                )
                            st.toast(f"Re-generated: {img_path.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Image failed: {e}")

    # ---- EXPORT TAB ----
    with tab_export:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("#### Export / Share")

        # Build a self-contained HTML document (base64 images + plan fragment)
        try:
            full_html = compose_export_html(plan, ASSETS_IMAGES)
        except Exception as e:
            st.error(f"Failed to build HTML: {e}")
            full_html = None

        colA, colB = st.columns(2)

        with colA:
            if full_html:
                st.download_button(
                    label="⬇️ Download HTML",
                    data=full_html.encode("utf-8"),
                    file_name=f"{plan.get('summary',{}).get('title','workout').replace(' ','_')}.html",
                    mime="text/html"
                )
            else:
                st.warning("HTML not ready.")

        with colB:
            if full_html:
                try:
                    with st.spinner("Rendering PDF…"):
                        pdf_bytes = to_pdf_with_playwright(full_html)
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"{plan.get('summary',{}).get('title','workout').replace(' ','_')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error("PDF export failed. Make sure Playwright is installed and Chromium is downloaded.")
                    st.caption("Run: pip install playwright  and  python -m playwright install chromium")
            else:
                st.warning("PDF not ready.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("HTML is self-contained (images inlined). PDF uses headless Chromium for reliable print layout.")

    # ---- AUDIO TAB ----
    with tab_audio:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("#### Motivation (Speech)")
        st.caption("We won’t show the text. We’ll generate and play audio, and append the text to a local log.")

        if st.button("🎧 Generate Motivation"):
            try:
                with st.spinner("Preparing motivation…"):
                    plan = st.session_state.get("plan")
                    if not plan:
                        st.warning("Please generate a workout plan first.")
                    else:
                        meta = plan.get("meta") or {}
                        summary = plan.get("summary") or {}
                        # Use the name collected earlier in the sidebar
                        name = st.session_state.get("name", "").strip() or "Athlete"

                        result = generate_motivation_and_tts(
                            client,
                            name=name,
                            meta=meta,
                            summary=summary,
                            assets_text_log=MOTIVATION_LOG,
                            assets_audio_dir=ASSETS_AUDIO,
                            tts_voice=st.session_state.get("tts_voice","alloy"),
                            text_model="gpt-5-nano",
                            max_speech_tokens=400
                        )

                        if result.get("ok"):
                            st.success("Motivation ready!")
                            st.audio(str(result["audio_path"]), format="audio/mp3")
                            st.caption(f"Appended to: {result['text_log_path'].as_posix()}")
                        else:
                            st.error("Failed to create motivation.")
            except Exception as e:
                st.error(f"Motivation failed: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("#### Audio: Last & History")

        # Find most recent MP3
        mp3_files = sorted(ASSETS_AUDIO.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)

        col1, col2 = st.columns([1, 2])

        with col1:
            if mp3_files:
                latest = mp3_files[0]
                st.write(f"**Latest:** {latest.name}")
                st.audio(str(latest), format="audio/mp3")
                with open(latest, "rb") as f:
                    st.download_button(
                        label="⬇️ Download last MP3",
                        data=f.read(),
                        file_name=latest.name,
                        mime="audio/mpeg",
                        key="dl_last_mp3"
                    )
            else:
                st.info("No MP3 files yet. Generate motivation first.")

        with col2:
            st.write("**Recent MP3 files**")
            if mp3_files:
                # Show up to 8 most-recent files (excluding the one already shown)
                for p in mp3_files[1:9]:
                    cL, cR = st.columns([3, 1])
                    with cL:
                        st.write(p.name)
                    with cR:
                        with open(p, "rb") as f:
                            st.download_button("Download", data=f.read(), file_name=p.name, mime="audio/mpeg", key=f"dl_{p.name}")
            else:
                st.caption("History will appear here after you generate audio.")
        st.markdown("</div>", unsafe_allow_html=True)
