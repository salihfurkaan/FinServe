"""
FinServe AI Email Triage Engine — Gradio GUI
=============================================
Interactive web interface for the email processing engine.
Run with: python app.py
"""

import gradio as gr
from finserve import FinServeAIEngine, DEMO_SCENARIOS, KNOWLEDGE_BASE, VALID_CATEGORIES
from dotenv import load_dotenv
import os
import json

load_dotenv()

# ── Initialise engine ──────────────────────────
# We instantiate the engine with whatever is in the .env initially,
# but it will dynamically fall back to the user's input if the env is empty.
API_KEY = os.getenv("GROQ_API_KEY", "")
engine = FinServeAIEngine(api_key=API_KEY)


# ── Processing function ────────────────────────
def process_email(subject: str, body: str, user_api_key: str):
    """Process an email and return formatted results."""
    if not subject.strip() or not body.strip():
        return (
            "⚠️ Please enter both a subject and body.",
            "", "", "", "", "", ""
        )

    try:
        # Pass the user's API key if they provided one, otherwise it falls back to the .env inside the engine
        result = engine.process_email(subject, body, passed_api_key=user_api_key.strip() if user_api_key else None)
    except Exception as e:
        # Catch missing API key errors or authentication failures gracefully
        return (
            "❌ ERROR",
            f"Authentication/API Error: {str(e)}",
            "—", "—", "—", "—", ""
        )

    status = result["status"]

    if status == "ESCALATED":
        return (
            "🚨 ESCALATED",
            result["reason"],
            "—", "—", "—", "—",
            ""
        )

    meta = result["metadata"]
    category_output = meta.get("category", "—")
    details_output = f"Urgency: {meta.get('urgency', '—')}"

    return (
        f"✅ {status}",
        "",
        meta.get("client_name") or "Not detected",
        meta.get("loan_id") or "Not detected",
        category_output,
        details_output,
        result["response_draft"],
    )


# ── Load demo scenario ─────────────────────────
def load_demo(scenario_name: str):
    """Fill in subject and body from a demo scenario."""
    if not scenario_name or scenario_name == "— Select a demo scenario —":
        return "", ""
    for s in DEMO_SCENARIOS:
        if s["name"] == scenario_name:
            return s["subject"], s["body"]
    return "", ""


# ── Custom CSS ──────────────────────────────────
CUSTOM_CSS = """
/* Global Theme & Typography */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body, .gradio-container {
    background-color: #0b0f19 !important;
    background-image: 
        radial-gradient(circle at 15% 50%, rgba(103, 76, 159, 0.08), transparent 25%),
        radial-gradient(circle at 85% 30%, rgba(45, 122, 184, 0.08), transparent 25%) !important;
    font-family: 'Inter', sans-serif !important;
    color: #e2e8f0 !important;
}

/* Base Panel Glassmorphism */
.glass-panel {
    background: rgba(17, 24, 39, 0.6) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
    padding: 24px !important;
}

/* Header Section */
.header-section {
    text-align: center;
    padding: 32px 16px 24px;
    margin-bottom: 12px;
}
.header-section h1 {
    font-size: 2.75rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    background: linear-gradient(135deg, #a5b4fc 0%, #c084fc 50%, #f472b6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
    text-shadow: 0 0 40px rgba(192, 132, 252, 0.3);
}
.header-section p {
    color: #94a3b8;
    font-size: 1.1rem;
    font-weight: 400;
}

/* Pipeline Status Bar */
.pipeline-info {
    background: linear-gradient(90deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.8) 100%);
    border-top: 1px solid rgba(165, 180, 252, 0.2);
    border-bottom: 1px solid rgba(165, 180, 252, 0.2);
    padding: 12px 24px;
    margin-bottom: 32px;
    font-size: 0.9rem;
    color: #cbd5e1;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    font-weight: 500;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
}
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 8px;
}
.pipeline-arrow {
    color: #475569;
}

/* Buttons */
.process-btn {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1.1rem !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    padding: 14px 32px !important;
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-top: 16px !important;
}
.process-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.6), inset 0 1px 0 rgba(255,255,255,0.3) !important;
}

/* Stat Cards (Replacing Textboxes for Metrics) */
.metric-row {
    display: grid !important;
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 16px !important;
    margin-bottom: 16px !important;
}
.stat-card {
    background: rgba(30, 41, 59, 0.5) !important;
    border: 1px solid rgba(148, 163, 184, 0.1) !important;
    border-radius: 12px !important;
    padding: 16px !important;
    display: flex !important;
    flex-direction: column !important;
}
.stat-card label {
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #94a3b8 !important;
    margin-bottom: 4px !important;
}
.stat-card textarea {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #f8fafc !important;
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    padding: 0 !important;
    resize: none !important;
}

/* Primary Status Indicator */
.status-indicator {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 12px !important;
    padding: 20px !important;
    margin-bottom: 24px !important;
    text-align: center !important;
}
.status-indicator textarea {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    text-align: center !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #f8fafc !important;
}

/* Text Areas & Inputs */
textarea, input[type="text"] {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-size: 0.95rem !important;
    transition: all 0.2s !important;
}
textarea:focus, input[type="text"]:focus {
    border-color: #818cf8 !important;
    box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.2) !important;
}

/* Draft Response Box */
.draft-box {
    margin-top: 24px !important;
}
.draft-box textarea {
    min-height: 250px !important;
    font-family: 'Inter', monospace !important;
    line-height: 1.6 !important;
    font-size: 0.95rem !important;
    padding: 20px !important;
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(129, 140, 248, 0.3) !important;
    border-left: 4px solid #818cf8 !important;
}

/* Accordion Styling */
.wrap.svelte-1g7478h {
    background: rgba(17, 24, 39, 0.4) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
}
"""


# ── Build the app ───────────────────────────────
demo_names = ["— Select a demo scenario —"] + [s["name"] for s in DEMO_SCENARIOS]

with gr.Blocks(title="FinServe AI Dashboard", theme=gr.themes.Monochrome(), css=CUSTOM_CSS) as app:

    # Header
    gr.HTML("""
        <div class="header-section">
            <h1>FinServe Operations AI</h1>
            <p>Enterprise Email Engine • Automated Triage & Draft Verification</p>
        </div>
    """)

    # Pipeline overview
    gr.HTML("""
        <div class="pipeline-info">
            <span style="color:#a5b4fc; text-transform:uppercase; font-size:0.75rem; letter-spacing:1px; margin-right:16px;">Active Engine Sequence:</span>
            <span class="pipeline-step">🛡️ Risk Filter</span> <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">🧠 Neural Extractor</span> <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">📚 Knowledge Graph</span> <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">⚡ Synthesizer</span> <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">✅ Validator</span>
        </div>
    """)

    with gr.Row():
        # ── Left: Input Dashboard ─────────────────────────
        with gr.Column(scale=4, elem_classes=["glass-panel"]):
            gr.Markdown("### 📥 Ingestion Port")
            gr.Markdown("<br>")

            demo_dropdown = gr.Dropdown(
                choices=demo_names,
                value=demo_names[0],
                label="Simulation Payload (Demo Scenarios)",
                interactive=True,
            )

            gr.Markdown("<br>")
            
            api_key_input = gr.Textbox(
                label="Groq API Key (Optional if hosted locally)",
                placeholder="gsk_...",
                type="password",
                lines=1,
            )
            
            gr.Markdown("<br>")
            
            subject_input = gr.Textbox(
                label="Subject Line",
                placeholder="e.g. Missing documents for LN-99821",
                lines=1,
            )
            body_input = gr.Textbox(
                label="Raw Email Corpus",
                placeholder="Paste or type the client's raw communication here...",
                lines=8,
            )
            
            gr.Markdown("<br>")
            process_btn = gr.Button(
                "⚡ ENGAGE ENGINE", elem_classes=["process-btn"], size="lg"
            )

            gr.Markdown(
                "<div style='margin-top:16px; padding:12px; background:rgba(0,0,0,0.2); border-radius:8px; border-left:3px solid #f59e0b; font-size:0.85rem; color:#94a3b8;'>"
                "<strong>System Note:</strong> Content containing hostile sentiment or explicit legal threats (e.g. lawsuit, ombudsman) "
                "triggers an immediate Level 1 Escalation, bypassing synthesis."
                "</div>"
            )

        # ── Right: Analysis & Output Dashboard ───────────────────────
        with gr.Column(scale=7, elem_classes=["glass-panel"]):
            gr.Markdown("### 🔍 Telemetry & Synthesis")
            
            # Primary Status
            status_output = gr.Textbox(
                show_label=False, 
                interactive=False, 
                elem_classes=["status-indicator"]
            )
            
            escalation_output = gr.Textbox(
                label="⚠️ Escalation Details", 
                interactive=False, 
                visible=True
            )

            gr.Markdown("<br>")
            gr.Markdown("#### Extracted Entity Matrix")
            
            # Stat Cards using custom CSS overriding textareas
            with gr.Row(elem_classes=["metric-row"]):
                client_output = gr.Textbox(label="Identified Client", interactive=False, elem_classes=["stat-card"])
                loan_output = gr.Textbox(label="Reference / Loan ID", interactive=False, elem_classes=["stat-card"])
                
            with gr.Row(elem_classes=["metric-row"]):
                category_output = gr.Textbox(label="Determined Intent", interactive=False, elem_classes=["stat-card"])
                details_output = gr.Textbox(label="Assessed Urgency", interactive=False, elem_classes=["stat-card"])

            gr.Markdown("<br>")
            draft_output = gr.Textbox(
                label="Generated Response (Draft Mode)",
                interactive=False,
                lines=10,
                elem_classes=["draft-box"],
            )

    gr.Markdown("<br><br>")

    # ── Knowledge base accordion ────────────────
    with gr.Accordion("📚 Reference Data (Policy Source Code)", open=False):
        gr.Markdown("*The LLM strictly references the following verified corporate policies when synthesizing drafts.*")
        for cat, policy in KNOWLEDGE_BASE.items():
            gr.Textbox(value=policy, label=cat, interactive=False, lines=2)

    # ── Wire events ─────────────────────────────
    demo_dropdown.change(
        fn=load_demo,
        inputs=[demo_dropdown],
        outputs=[subject_input, body_input],
    )

    process_btn.click(
        fn=process_email,
        inputs=[subject_input, body_input, api_key_input],
        outputs=[
            status_output,
            escalation_output,
            client_output,
            loan_output,
            category_output,
            details_output,
            draft_output,
        ],
    )

# ── Launch ──────────────────────────────────────
if __name__ == "__main__":
    app.launch(inbrowser=True, css=CUSTOM_CSS)
