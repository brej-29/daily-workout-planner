<div align="center">
  <h1>🏋️ Daily Workout Planner</h1>
  <p><i>Generate professional, web-styled daily workout plans with on-demand images, motivation speech, and PDF/HTML export — built with Streamlit & OpenAI</i></p>
</div>

<br>

<div align="center">
  <a href="https://github.com/brej-29/daily-workout-planner">
    <img alt="Last Commit" src="https://img.shields.io/github/last-commit/brej-29/daily-workout-planner">
  </a>
  <img alt="Language" src="https://img.shields.io/badge/Language-Python-blue">
  <img alt="Framework" src="https://img.shields.io/badge/Framework-Streamlit-ff4b4b">
  <img alt="API" src="https://img.shields.io/badge/API-OpenAI-orange">
  <img alt="Libraries" src="https://img.shields.io/badge/Libraries-Playwright%20%7C%20Requests%20%7C%20Pillow%20%7C%20Streamlit%20Components-brightgreen">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-black">
</div>

<div align="center">
  <br>
  <b>Built with the tools and technologies:</b>
  <br><br>
  <code>Python</code> | <code>Streamlit</code> | <code>OpenAI</code> | <code>DALL·E-2</code> | <code>Playwright (Chromium)</code> | <code>Requests</code> | <code>Pillow</code>
</div>

---

## **Screenshot**

<!-- Replace with your own screenshots or remove this section -->
<img width="1919" height="928" alt="image" src="https://github.com/user-attachments/assets/ee6a2c14-c3f0-41ea-a490-09b6613cf554" />


<img width="1919" height="922" alt="image" src="https://github.com/user-attachments/assets/f4c9e170-6c8d-4827-ba16-5627c1569ddd" />


<img width="1918" height="924" alt="image" src="https://github.com/user-attachments/assets/d85780b6-99b6-47b5-9e33-79111517f404" />


<img width="1918" height="918" alt="image" src="https://github.com/user-attachments/assets/b2458554-2e98-4bec-99a4-89140fdc9cae" />


<img width="1919" height="920" alt="image" src="https://github.com/user-attachments/assets/adca8750-f96f-4f5a-83da-f5f0408b7cc4" />



---

## **Table of Contents**
* [Overview](#overview)
* [Features](#features)
* [Getting Started](#getting-started)
    * [Project Structure](#project-structure)
    * [Prerequisites](#prerequisites)
    * [Installation](#installation)
    * [Configuration](#configuration)
    * [Usage](#usage)
* [License](#license)
* [Contact](#contact)

---

## **Overview**

Daily Workout Planner is an interactive Streamlit application that builds a **single-day workout** tailored to your goal, environment (Gym/Home), level, duration, and optional calorie target. The app renders a clean, website-style HTML fragment, lists real exercise names, lets you **generate per-exercise images on demand** (cached locally), and produces a **personalized motivation speech** as MP3. You can also **export** the full plan with embedded thumbnails as **self-contained HTML** or **PDF** (via Playwright/Chromium).

<br>

### **Project Highlights**

- **Structured AI Plans:** Uses OpenAI Chat Completions with **JSON Schema** for robust, predictable workout data.
- **Website-Style Rendering:** Local HTML fragment renderer for consistent, polished visuals.
- **On-Demand Images:** Generate one image per exercise with **DALL·E-2**; files are cached under `assets/images/`.
- **Motivation Speech:** Short, powerful speech generated (text via GPT-5-nano with fallback; TTS via `tts-1`) and saved to MP3.
- **Export Ready:** One-click **HTML** (self-contained) and **PDF** (Chromium print-to-PDF) exports.
- **Audio History:** “Last MP3” download plus a recent files panel.
- **Zero Secret Leaks:** API key read from Streamlit **Secrets**.

---

## **Features**

- Configure **Goal, Environment, Level, Duration**, and optional **Calorie Target**.
- Generate a structured **Warm-up / Main / Cool-down** plan with realistic sets, reps, rest, intensity, and notes.
- **Per-exercise images**: generate only when needed; cached images are reused automatically.
- **Motivation speech**: generates text (not displayed), appends to a local **log**, and plays **MP3** inline.
- **Export / Share**: Download **HTML** with embedded thumbnails or **PDF** using Playwright (Chromium).
- Clean, modern UI with tabs (**Plan / Images / Export / Audio**) and subtle design polish.

---

## **Getting Started**

Follow these steps to set up and run the project locally.

### **Project Structure**

    daily-workout-planner/
    ├─ app.py
    ├─ services/
    │  └─ openai_ops.py            # OpenAI calls: plan JSON, images (DALL·E-2), motivation+TTS
    ├─ utils/
    │  ├─ exporters.py             # Export: HTML compose + Playwright PDF
    │  ├─ parse.py                 # Filename sanitization helpers
    │  └─ ui.py                    # Safe HTML fragment rendering
    ├─ assets/
    │  ├─ images/                  # Cached exercise images (PNG)
    │  ├─ audio/                   # Generated MP3s
    │  └─ text/                    # motivation_log.txt
    ├─ .streamlit/
    │  └─ secrets.toml             # contains your OPENAI_API_KEY (not committed)
    ├─ requirements.txt
    ├─ LICENSE                     # MIT License
    └─ README.md

### **Prerequisites**
- Python **3.9+** recommended
- **OpenAI API key** with access to:
  - Text models (e.g., `gpt-4o-mini`, `gpt-5-nano`)
  - Images (`dall-e-2`)
  - TTS (`tts-1`)
- For PDF export:
  - `playwright` and a local Chromium: `python -m playwright install chromium`

### **Installation**
1) Create and activate a virtual environment (optional but recommended).

        python -m venv .venv
        # Windows:
        .venv\Scripts\activate
        # macOS/Linux:
        source .venv/bin/activate

2) Install dependencies.

        pip install -r requirements.txt
        # For PDF export (Chromium print-to-PDF):
        python -m playwright install chromium

### **Configuration**
1) Create `.streamlit/secrets.toml` (the folder/file may not exist by default).

        OPENAI_API_KEY = "sk-...your-key..."

2) Confirm `app.py` reads from `st.secrets["OPENAI_API_KEY"]` (already wired).

3) (Optional) Corporate networks/AV: ensure Playwright can launch Chromium.

### **Usage**
1) Run the Streamlit app.

        streamlit run app.py

2) In the **sidebar**, set your plan parameters (Goal, Environment, Level, Duration, optional Calorie Target). Enter **Your Name** and choose **TTS Voice**.

3) Click **“⚡ Generate Workout Plan”**.

4) **Plan Tab:** Review the formatted workout with block cards (Warm-up / Main / Cool-down).

5) **Images Tab:**  
   - See a **Cached Gallery** at the top (if any images exist).  
   - For each exercise, click **Generate image** to create a DALL·E-2 image; it’s saved under `assets/images/` and instantly reused next time.

6) **Export Tab:**  
   - **Download HTML:** self-contained page with embedded thumbnails.  
   - **Download PDF:** Chromium print-to-PDF via Playwright.

7) **Audio Tab:**  
   - Click **“🎧 Generate Motivation”** to create a personalized speech (text appended to `assets/text/motivation_log.txt`) and play the MP3.  
   - **Download last MP3** and browse recent audio files.

---

## **License**
This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## **Contact**
For questions or feedback, connect with me on [LinkedIn](https://www.linkedin.com/in/brejesh-balakrishnan-7855051b9/)
