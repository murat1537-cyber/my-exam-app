import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. GÜVENLİK VE SAYFA AYARLARI (OWASP A03 & A05) ---
st.set_page_config(page_title="Secure Exam Prep", layout="wide")

# İçerik koruması ve Tasarım (theorieexamen.nl stili) [cite: 17, 18, 164, 165]
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; } /* Kopyalama engeli [cite: 17] */
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.1; font-size: 10px; }
    </style>
    """, unsafe_allow_html=True) # Hata burada düzeltildi

# --- 2. VERİ BAĞLANTISI (Secure Secrets) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Google Sheets bağlantı hatası! Lütfen Secrets (Sırlar) kısmını kontrol et.")
    st.stop()

# --- 3. OTURUM YÖNETİMİ ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Study'
if 'feedback' not in st.session_state: st.session_state.feedback = None

# --- 4. FONKSİYONLAR (Güvenli Veri İşleme) ---
def save_result(q_id, correct, confidence, reason):
    # Veri girişini otomatik temizler (Input Validation) [cite: 255]
    new_data = pd.DataFrame([{
        "user_id": "User_1", # İleride Login ile değişecek [cite: 83]
        "question_id": q_id,
        "is_correct": correct,
        "confidence_level": confidence,
        "error_reason": reason,
        "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    conn.create(worksheet="User_Stats", data=new_data) # [cite: 133, 144]

# --- 5. ARAYÜZ BÖLÜMLERİ ---
# Yan Menü (Navigation) [cite: 168-171]
with st.sidebar:
    st.title("Exam Menu")
    if st.button("📝 Study Mode"): st.session_state.view = 'Study'
    if st.button("📊 Analytics"): st.session_state.view = 'Analytics'

# --- A. ÇALIŞMA MODU ---
if st.session_state.view == 'Study':
    df = conn.read(worksheet="Questions") # [cite: 114]
    if not df.empty:
        curr = df.iloc[st.session_state.q_idx]
        
        # Soru Kartı [cite: 188-190]
        st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
        
        # Şıklar [cite: 190]
        for opt in ['A', 'B', 'C', 'D']:
            if st.button(f"{opt}) {curr[f'option_{opt.lower()}']}", key=f"btn_{opt}"):
                st.session_state.feedback = (opt == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

        # Metacognition (Bilişsel Farkındalık) [cite: 50-57, 198-213]
        if st.session_state.feedback is not None:
            if st.session_state.feedback:
                st.success("✅ Correct!")
                st.write("Are you sure?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, I was sure"): 
                    save_result(st.session_state.last_q_id, True, "Sure", None)
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Wrong! Correct was {curr['correct_option']}")
                st.write("Why did you get it wrong?")
                r1, r2, r3 = st.columns(3)
                if r1.button("Knowledge Gap"): 
                    save_result(st.session_state.last_q_id, False, None, "Knowledge Gap")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
    
# --- B. ANALİZ MODU (Analytics) [cite: 58-63, 214-224] ---
else:
    st.header("Your Progress Dashboard")
    stats = conn.read(worksheet="User_Stats")
    if not stats.empty:
        # Başarı Grafiği [cite: 60]
        fig = px.pie(stats, names='is_correct', title="Overall Accuracy", color='is_correct',
                     color_discrete_map={True:'green', False:'red'})
        st.plotly_chart(fig)
        
        # Hata Analizi [cite: 61, 219, 220]
        st.subheader("Why do you make mistakes?")
        st.bar_chart(stats['error_reason'].value_counts())
    else:
        st.info("No stats yet! Start studying.")

st.markdown('<div class="watermark">Secure SaaS Prototype</div>', unsafe_allow_html=True)
