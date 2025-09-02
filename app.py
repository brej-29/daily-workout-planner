import logging
import os
from typing import List
import streamlit as st
# app.py (add near top, below existing imports)
from pathlib import Path
from services.openai_ops import make_client, generate_workout_plan
from utils.ui import render_html_fragment

# ---------- Page & Logging ----------
st.set_page_config(page_title="Daily Workout Planner", page_icon="🏋️", layout="wide")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("workout_planner")

# Prepare assets dirs (used later steps too)
ASSETS_DIR = Path("assets")
ASSETS_IMAGES = ASSETS_DIR / "images"
ASSETS_AUDIO = ASSETS_DIR / "audio"
ASSETS_DIR.mkdir(exist_ok=True)
ASSETS_IMAGES.mkdir(parents=True, exist_ok=True)
ASSETS_AUDIO.mkdir(parents=True, exist_ok=True)

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
        "duration_min": 45,                  # default session length
        "use_calorie_target": False,         # off by default (optional)
        "calorie_target": 400,               # shown only if enabled
        "equipment": [],                     # optional; empty means none
        "constraints": []                    # optional constraints
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# Create OpenAI client from secrets/env
API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not API_KEY:
    st.sidebar.error("Missing OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()
client = make_client(API_KEY)

# ---------- Sidebar: Input Form ----------
with st.sidebar:
    st.title("🧭 Plan Setup")
    
    st.markdown("---")
    name = st.text_input("Your name (for motivation later)", value=st.session_state.get("name", ""))
    
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

        submitted = st.form_submit_button("Save plan settings")

# ---------- Handle Submit ----------
if submitted:
    if use_calorie_target and calorie_target is None:
        st.sidebar.error("Please enter a calorie-burn target or untick the option.")
    else:
        st.session_state.goal = goal
        st.session_state.environment = environment
        st.session_state.level = level
        st.session_state.duration_min = int(duration_min)
        st.session_state.use_calorie_target = bool(use_calorie_target)
        st.session_state.name = name.strip()
        if use_calorie_target:
            st.session_state.calorie_target = int(calorie_target)
        st.session_state.equipment = list(equipment)
        st.session_state.constraints = list(constraints)

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
st.title("🏋️ Daily Workout Planner (MVP — Step 1)")
st.caption("This step focuses on a clean input experience. Generation comes next.")

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("Your plan settings")
    st.markdown(f"**Goal:** {st.session_state.goal}")
    st.markdown(f"**Environment:** {st.session_state.environment}")
    st.markdown(f"**Level:** {st.session_state.level}")
    st.markdown(f"**Duration:** {st.session_state.duration_min} minutes")

    if st.session_state.use_calorie_target:
        st.markdown(f"**Calorie target:** {st.session_state.calorie_target} kcal (optional)")

    if st.session_state.equipment:
        st.markdown("**Equipment:** " + ", ".join(st.session_state.equipment))
    else:
        st.markdown("**Equipment:** _not specified_")

    if st.session_state.constraints:
        st.markdown("**Constraints:** " + ", ".join(st.session_state.constraints))
    else:
        st.markdown("**Constraints:** _none_")

with col_right:
    st.subheader("Next up")
    st.write("• Add an exercise library and logic to assemble sessions.")
    st.write("• Show per-exercise sets/reps/time, rest, and estimated calories.")
    st.write("• Keep totals within the timebox and (optionally) a calorie target.")

st.markdown("---")
st.subheader("Generate AI Workout Plan")

generate_clicked = st.button("⚡ Generate Workout Plan")

if generate_clicked:
    if not st.session_state.get("name"):
        st.warning("Please enter your name in the sidebar (for motivation later).")
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
                model="gpt-5-nano",
                temperature=0.7,
                max_output_tokens=1800
            )
            st.session_state.plan = plan
            st.success("Plan generated.")
    except Exception as e:
        st.error(f"Failed to generate plan: {e}")

# Render the plan if available
if "plan" in st.session_state:
    plan = st.session_state.plan
    st.subheader(plan.get("summary", {}).get("title", "Your Workout Plan"))

    # Render HTML fragment
    html_fragment = plan.get("plan_html_fragment", "")
    if html_fragment:
        render_html_fragment(html_fragment, height=1200)
    else:
        st.warning("No HTML fragment returned; check model output.")

    # Show exercise/image titles list (no generation yet — Step 3)
    titles = plan.get("titles_for_images", [])
    if titles:
        st.markdown("#### Exercises / Blocks available for images")
        st.write(", ".join(titles))