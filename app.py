import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. TASARIM VE GÜVENLİK ---
st.set_page_config(page_title="AI Exam Mentor", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .explanation-box { background-color: #fff9db; padding: 20px; border-radius: 15px; border-left: 5px solid #fcc419; margin-top: 20px; font-style: italic; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. OTURUM DURUMLARI (SÜREKLİLİK İÇİN) ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. VERİ YAZMA ---
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

# --- 5. NAVİGASYON (SIDEBAR) ---
with st.sidebar:
    st.title("🏆 AI Mentor Panel")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint"): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate"): 
            st.session_state.is_sprint_active = False
            st.session_state.view = 'Analytics'
            st.rerun()
    else:
        if st.button("🚀 Start 10-Min AI Sprint"):
            questions = conn.read(worksheet="Questions", ttl=0)
            st.session_state.smart_list = questions.sample(frac=1).reset_index(drop=True)
            st.session_state.q_idx = 0
            st.session_state.view = 'Study'
            st.session_state.start_time = datetime.now()
            st.session_state.is_sprint_active = True
            st.rerun()
    
    st.write("---")
    if st.button("📊 AI Analytics"): st.session_state.view = 'Analytics'

# --- 6. ÇALIŞMA MODU VE AI AÇIKLAMASI ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # Zamanlayıcı
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    df = st.session_state.smart_list
    curr = df.iloc[st.session_state.q_idx]
    
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"A) {curr['option_a']}", use_container_width=True): st.session_state.feedback = ('A' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"C) {curr['option_c']}", use_container_width=True): st.session_state.feedback = ('C' == curr['correct_option']); st.session_state.last_q_id = curr['id']
    with col2:
        if st.button(f"B) {curr['option_b']}", use_container_width=True): st.session_state.feedback = ('B' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"D) {curr['option_d']}", use_container_width=True): st.session_state.feedback = ('D' == curr['correct_option']); st.session_state.last_q_id = curr['id']

    # Geri Bildirim ve AI Açıklaması [cite: 58, 199, 213]
    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Correct!")
            # Açıklama Göster (Opsiyonel: Doğruyken de öğrenmek için)
            st.markdown(f'<div class="explanation-box"><b>AI Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Guessed"): save_stat(st.session_state.last_q_id, True, "Guessed", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Wrong! Correct Answer: {curr['correct_option']}")
            # Yanlışta Açıklamayı Hemen Göster [cite: 57, 209]
            st.markdown(f'<div class="explanation-box"><b>AI Mentor Explanation:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Knowledge Gap"): save_stat(st.session_state.last_q_id, False, None, "Knowledge Gap"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Attention"): save_stat(st.session_state.last_q_id, False, None, "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Logic"): save_stat(st.session_state.last_q_id, False, None, "Interpretation"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

    st.write("---")
    if st.button("⬅️ View Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# --- 7. ANALİZ ---
elif st.session_state.view == 'Analytics':
    st.header("📊 AI Performance Mentoring")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    if not stats.empty:
        stats['is_correct'] = stats['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})
        st.plotly_chart(px.pie(stats, names='is_correct', title="Success Rate", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}))
    else:
        st.info("Start a sprint to see your AI mentor's feedback.")
