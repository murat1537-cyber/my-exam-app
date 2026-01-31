import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. GÜVENLİK VE TASARIM ---
st.set_page_config(page_title="Pro Exam AI", layout="wide")

st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; }
    .timer-box { font-size: 24px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    .watermark { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-45deg); font-size: 50px; color: rgba(0, 0, 0, 0.03); z-index: 1000; pointer-events: none; }
    </style>
    <div class="watermark">CONFIDENTIAL - SECURE EXAM</div>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Connection Error! Check Secrets.")
    st.stop()

# --- 3. OTURUM DURUMLARI ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Study'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'session_results' not in st.session_state: st.session_state.session_results = []

# --- 4. FONKSİYONLAR ---
def save_stat(q_id, correct, confidence, reason):
    new_entry = pd.DataFrame([{
        "user_id": "User_01",
        "question_id": q_id,
        "is_correct": correct,
        "confidence_level": confidence,
        "error_reason": reason,
        "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    conn.create(worksheet="User_Stats", data=new_entry)
    st.session_state.session_results.append({"correct": correct, "reason": reason})

def create_pdf(results_df):
    """PDF Raporu Oluşturur """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Exam Performance Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    total = len(results_df)
    correct = results_df['correct'].sum()
    pdf.cell(200, 10, f"Total Questions Solved: {total}", ln=True)
    pdf.cell(200, 10, f"Correct Answers: {correct}", ln=True)
    pdf.cell(200, 10, f"Accuracy: %{(correct/total)*100:.2f}", ln=True)
    pdf.ln(10)
    pdf.cell(200, 10, "Keep studying to reach your goals!", ln=True, align='C')
    return pdf.output()

# --- 5. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Control Center")
    if st.button("📝 Start 10-Min Sprint"):
        st.session_state.smart_list = conn.read(worksheet="Questions").sample(frac=1)
        st.session_state.q_idx = 0
        st.session_state.view = 'Study'
        st.session_state.start_time = datetime.now()
        st.session_state.session_results = []
    if st.button("📊 Performance Analytics"):
        st.session_state.view = 'Analytics'

# --- 6. ÇALIŞMA MODU VE SAYAÇ ---
if st.session_state.view == 'Study':
    if st.session_state.start_time:
        # Geri Sayım Sayacı (10 Dakika) 
        elapsed = datetime.now() - st.session_state.start_time
        remaining = timedelta(minutes=10) - elapsed
        if remaining.total_seconds() > 0:
            st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ Time is up! Review your results.")
            st.session_state.view = 'Analytics'
            st.rerun()

    df = st.session_state.smart_list
    if df is not None and not df.empty and st.session_state.q_idx < len(df):
        curr = df.iloc[st.session_state.q_idx]
        st.markdown(f'<div class="q-card"><h2>{curr["content_text"]}</h2></div>', unsafe_allow_html=True)
        
        cols = st.columns(2)
        for i, opt in enumerate(['A', 'B', 'C', 'D']):
            with cols[i % 2]:
                if st.button(f"{opt}) {curr[f'option_{opt.lower()}']}", use_container_width=True):
                    st.session_state.feedback = (opt == curr['correct_option'])
                    st.session_state.last_q_id = curr['id']

        if st.session_state.feedback is not None:
            if st.session_state.feedback:
                st.success("✅ Correct!")
                c1, c2 = st.columns(2)
                if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if c2.button("🎲 Guessed"): save_stat(st.session_state.last_q_id, True, "Guessed", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Wrong! Correct: {curr['correct_option']}")
                r1, r2, r3 = st.columns(3)
                if r1.button("Knowledge Gap"): save_stat(st.session_state.last_q_id, False, None, "Knowledge Gap"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r2.button("Attention"): save_stat(st.session_state.last_q_id, False, None, "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r3.button("Logic"): save_stat(st.session_state.last_q_id, False, None, "Interpretation"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# --- 7. ANALİZ VE PDF RAPORU ---
else:
    st.header("📊 Performance Dashboard")
    stats = conn.read(worksheet="User_Stats")
    
    if not stats.empty:
        col_chart, col_report = st.columns([2, 1])
        with col_chart:
            fig = px.bar(stats['error_reason'].value_counts(), title="Why do you miss?")
            st.plotly_chart(fig, use_container_width=True)
        
        with col_report:
            st.subheader("📄 Export Results")
            # PDF Oluşturma Butonu
            if st.button("Generate PDF Report"):
                pdf_data = create_pdf(stats)
                st.download_button(label="📥 Download Report", data=pdf_data, file_name="exam_report.pdf", mime="application/pdf")
    else:
        st.info("No data. Solve some questions first!")
