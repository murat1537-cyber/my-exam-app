import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. GÜVENLİK VE TASARIM ---
st.set_page_config(page_title="AI Exam Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
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

# --- 4. VERİ YAZMA FONKSİYONU (SATIR EKLEME DÜZELTİLDİ) ---
def save_stat(q_id, correct, confidence, reason):
    try:
        # 1. Mevcut verileri çek
        existing_df = conn.read(worksheet="User_Stats")
        
        # 2. Yeni veriyi hazırla [cite: 136-144]
        new_row = pd.DataFrame([{
            "user_id": "User_01",
            "question_id": q_id,
            "is_correct": 1 if correct else 0,
            "confidence_level": confidence if confidence else "None",
            "error_reason": reason if reason else "None",
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        
        # 3. Eski ve yeniyi birleştir (Alt alta ekleme)
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        # 4. Sayfayı tamamen güncelle (Hata almamak için update kullanıyoruz)
        conn.update(worksheet="User_Stats", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# --- 5. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Control Center")
    if st.button("📝 Start 10-Min Sprint"):
        questions = conn.read(worksheet="Questions")
        st.session_state.smart_list = questions.sample(frac=1).reset_index(drop=True)
        st.session_state.q_idx = 0
        st.session_state.view = 'Study'
        st.session_state.start_time = datetime.now()
        st.rerun()
    
    if st.button("📊 Performance Analytics"):
        st.session_state.view = 'Analytics'
    
    if st.session_state.view == 'Study':
        st.write("---")
        if st.button("🛑 Finish Session Early"):
            st.session_state.view = 'Analytics'
            st.session_state.start_time = None
            st.rerun()

# --- 6. ÇALIŞMA MODU ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # Sayaç [cite: 41, 195-197]
    if st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        remaining = timedelta(minutes=10) - elapsed
        if remaining.total_seconds() <= 0:
            st.session_state.view = 'Analytics'
            st.rerun()
        st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    df = st.session_state.smart_list
    curr = df.iloc[st.session_state.q_idx]
    
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    # Şıklar (2x2)
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"A) {curr['option_a']}", use_container_width=True): st.session_state.feedback = ('A' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"C) {curr['option_c']}", use_container_width=True): st.session_state.feedback = ('C' == curr['correct_option']); st.session_state.last_q_id = curr['id']
    with col2:
        if st.button(f"B) {curr['option_b']}", use_container_width=True): st.session_state.feedback = ('B' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"D) {curr['option_d']}", use_container_width=True): st.session_state.feedback = ('D' == curr['correct_option']); st.session_state.last_q_id = curr['id']

    # Geri Bildirim ve Alt Navigasyon
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

    # ÖNCEKİ SORU BUTONU 
    st.write("---")
    if st.button("⬅️ View Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1
        st.session_state.feedback = None
        st.rerun()

# --- 7. ANALİZ ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Session Summary")
    stats = conn.read(worksheet="User_Stats")
    if not stats.empty:
        st.plotly_chart(px.pie(stats, names='is_correct', title="Overall Success Rate", hole=0.3))
    else:
        st.info("No data recorded yet.")
