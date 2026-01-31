import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. TASARIM VE GÜVENLİK ---
st.set_page_config(page_title="AI Exam Mentor Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .explanation-box { background-color: #fff9db; padding: 20px; border-radius: 15px; border-left: 5px solid #fcc419; margin-top: 20px; font-style: italic; color: #856404; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.8em; font-weight: 600; font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. OTURUM DURUMLARI ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. VERİ YAZMA (TRUE/FALSE FORMATI) ---
def save_stat(q_id, correct, confidence, reason):
    try:
        existing_df = conn.read(worksheet="User_Stats", ttl=0)
        new_row = pd.DataFrame([{
            "user_id": "User_01",
            "question_id": str(q_id),
            "is_correct": "TRUE" if correct else "FALSE",
            "confidence_level": str(confidence),
            "error_reason": str(reason) if reason else "None",
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).dropna(how='all')
        conn.update(worksheet="User_Stats", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

# --- 5. PDF RAPORU (I SÜTUNUNDAKİ AÇIKLAMA DAHİL) ---
def create_error_report(stats_df, questions_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Personal Error Analysis Report", ln=True, align='C')
    pdf.ln(10)
    
    stats_df['is_correct'] = stats_df['is_correct'].astype(str).str.upper().replace({'0': 'FALSE', '1': 'TRUE'})
    wrong_stats = stats_df[(stats_df['is_correct'] == "FALSE") | (stats_df['confidence_level'] == "Guessed")]
    
    if wrong_stats.empty:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No errors to report.", ln=True)
    else:
        for _, row in wrong_stats.iterrows():
            q_info = questions_df[questions_df['id'].astype(str) == str(row['question_id'])]
            if not q_info.empty:
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(185, 7, f"Q: {str(q_info['content_text'].values[0])}")
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(185, 6, f"Correct: {str(q_info['correct_option'].values[0])} | Error: {row['error_reason']}")
                if 'explanation' in q_info.columns:
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.multi_cell(185, 5, f"AI Explanation: {str(q_info['explanation'].values[0])}")
                pdf.ln(3)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
                if pdf.get_y() > 260: pdf.add_page()
    return bytes(pdf.output())

# --- 6. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Learning Hub")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint", use_container_width=True): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate Sprint", use_container_width=True): 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    else:
        if st.button("🚀 New 10-Min Sprint", use_container_width=True):
            questions = conn.read(worksheet="Questions", ttl=0)
            st.session_state.smart_list = questions.sample(frac=1).reset_index(drop=True)
            st.session_state.q_idx = 0; st.session_state.view = 'Study'; st.session_state.start_time = datetime.now(); st.session_state.is_sprint_active = True; st.rerun()
    
    st.write("---")
    if st.button("📊 AI Analytics", use_container_width=True): st.session_state.view = 'Analytics'

# --- 7. ÇALIŞMA EKRANI ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # Zamanlayıcı [cite: 41, 195]
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Remaining Time: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    df = st.session_state.smart_list
    curr = df.iloc[st.session_state.q_idx]
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    # 2x2 Şık Düzeni [cite: 190]
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"A) {curr['option_a']}", use_container_width=True): st.session_state.feedback = ('A' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"C) {curr['option_c']}", use_container_width=True): st.session_state.feedback = ('C' == curr['correct_option']); st.session_state.last_q_id = curr['id']
    with col2:
        if st.button(f"B) {curr['option_b']}", use_container_width=True): st.session_state.feedback = ('B' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"D) {curr['option_d']}", use_container_width=True): st.session_state.feedback = ('D' == curr['correct_option']); st.session_state.last_q_id = curr['id']

    # Geri Bildirim ve AI Mentor [cite: 51, 53, 203, 209]
    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Correct!")
            if 'explanation' in curr:
                st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Guessed"): save_stat(st.session_state.last_q_id, True, "Guessed", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Wrong! Correct: {curr['correct_option']}")
            if 'explanation' in curr:
                st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Knowledge Gap"): save_stat(st.session_state.last_q_id, False, None, "Knowledge Gap"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Attention"): save_stat(st.session_state.last_q_id, False, None, "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Logic"): save_stat(st.session_state.last_q_id, False, None, "Interpretation"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

    st.write("---")
    if st.button("⬅️ Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# --- 8. ANALİZ EKRANI ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Insights")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty:
        stats['is_correct'] = stats['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})
        col_p, col_r = st.columns([2, 1])
        with col_p:
            st.plotly_chart(px.pie(stats, names='is_correct', title="Success Rate", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}))
        with col_r:
            st.subheader("📋 Report")
            if st.button("Generate Detailed PDF"):
                report = create_error_report(stats, questions)
                st.download_button(label="📥 Download", data=report, file_name="ai_analysis.pdf", mime="application/pdf")
    else:
        st.info("No stats recorded yet.")
