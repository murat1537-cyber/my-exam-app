import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 1. GÜVENLİK VE TASARIM AYARLARI ---
st.set_page_config(page_title="AI Exam Master", layout="wide")

# theorieexamen.nl tarzı modern CSS ve Güvenlik Kalkanı
st.markdown("""
    <style>
    /* İçerik Koruması: Metin seçimi ve sağ tık engeli [cite: 17, 187] */
    * { -webkit-user-select: none; user-select: none; }
    
    .main { background-color: #f8f9fa; }
    
    /* Soru Kartı Tasarımı [cite: 7, 188] */
    .q-card {
        background: white; 
        padding: 2.5rem; 
        border-radius: 20px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        border-top: 5px solid #007bff;
    }
    
    /* Dinamik Filigran [cite: 19, 20, 187] */
    .watermark {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-45deg);
        font-size: 50px;
        color: rgba(0, 0, 0, 0.03);
        z-index: 1000;
        pointer-events: none;
        white-space: nowrap;
    }
    
    .stButton>button {
        border-radius: 12px;
        height: 4em;
        font-weight: 600;
        font-size: 17px;
        transition: all 0.3s;
    }
    </style>
    <div class="watermark">SECURE SESSION - PREVENT SCREENSHOT</div>
    """, unsafe_allow_html=True)

# --- 2. VERİ TABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Connection Error! Please check your Streamlit Secrets.")
    st.stop()

# --- 3. OTURUM DURUMLARI (SESSION STATE) ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Study'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None

# --- 4. YARDIMCI FONKSİYONLAR ---
def save_stat(q_id, correct, confidence, reason):
    """Kullanıcı cevaplarını Google Sheets'e kaydeder [cite: 133-144]"""
    new_entry = pd.DataFrame([{
        "user_id": "User_01",
        "question_id": q_id,
        "is_correct": correct,
        "confidence_level": confidence,
        "error_reason": reason,
        "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    conn.create(worksheet="User_Stats", data=new_entry)

def load_smart_questions():
    """Akıllı tekrar listesi oluşturur: Yanlışlar ve Emin Olunmayanlar [cite: 42-49]"""
    all_q = conn.read(worksheet="Questions")
    stats = conn.read(worksheet="User_Stats")
    
    if stats.empty:
        return all_q
        
    # Daha önce yanlış yapılan veya 'Guessed' denilen soruların ID'leri [cite: 142, 143]
    trouble_ids = stats[(stats['is_correct'] == False) | (stats['confidence_level'] == 'Guessed')]['question_id'].unique()
    
    # Bu soruları listenin başına al (Prioritize trouble questions) [cite: 43]
    trouble_q = all_q[all_q['id'].isin(trouble_ids)]
    other_q = all_q[~all_q['id'].isin(trouble_ids)]
    
    return pd.concat([trouble_q.sample(frac=1), other_q.sample(frac=1)])

# --- 5. ANA MENÜ (SIDEBAR) [cite: 168-171] ---
with st.sidebar:
    st.title("🚀 Exam Panel")
    if st.button("📝 Start Smart Study"):
        st.session_state.smart_list = load_smart_questions()
        st.session_state.q_idx = 0
        st.session_state.view = 'Study'
    if st.button("📊 Performance Analytics"):
        st.session_state.view = 'Analytics'

# --- 6. ARAYÜZ BÖLÜMLERİ ---

# A. ÇALIŞMA MODU (Study Mode) [cite: 36, 184]
if st.session_state.view == 'Study':
    if st.session_state.smart_list is None:
        st.session_state.smart_list = load_smart_questions()
    
    df = st.session_state.smart_list
    
    if not df.empty and st.session_state.q_idx < len(df):
        curr = df.iloc[st.session_state.q_idx]
        
        # İlerleme Çubuğu [cite: 179]
        st.progress((st.session_state.q_idx + 1) / len(df))
        
        # Soru Kartı [cite: 188-190]
        st.markdown(f'''
            <div class="q-card">
                <small style="color:gray;">Topic ID: {curr['topic_id']}</small>
                <h2 style="margin-top:0;">{curr['content_text']}</h2>
            </div>
        ''', unsafe_allow_html=True)
        
        # Şıklar (2x2 Grid)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(f"A) {curr['option_a']}", use_container_width=True):
                st.session_state.feedback = ('A' == curr['correct_option'])
                st.session_state.last_q_id = curr['id']
            if st.button(f"C) {curr['option_c']}", use_container_width=True):
                st.session_state.feedback = ('C' == curr['correct_option'])
                st.session_state.last_q_id = curr['id']
        with col_b:
            if st.button(f"B) {curr['option_b']}", use_container_width=True):
                st.session_state.feedback = ('B' == curr['correct_option'])
                st.session_state.last_q_id = curr['id']
            if st.button(f"D) {curr['option_d']}", use_container_width=True):
                st.session_state.feedback = ('D' == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

        # Geri Bildirim ve Metacognition (Bilişsel Farkındalık) [cite: 50-57, 198-213]
        if st.session_state.feedback is not None:
            if st.session_state.feedback:
                st.success("✅ Correct! Excellent Work.")
                st.write("**Confidence Check:**")
                c1, c2 = st.columns(2)
                if c1.button("🎯 Sure of it"):
                    save_stat(st.session_state.last_q_id, True, "Sure", None)
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if c2.button("🎲 Lucky Guess"):
                    save_stat(st.session_state.last_q_id, True, "Guessed", None)
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Incorrect. The right answer was {curr['correct_option']}")
                st.write("**Reason for the error?**")
                r1, r2, r3 = st.columns(3)
                if r1.button("Knowledge Gap"):
                    save_stat(st.session_state.last_q_id, False, None, "Knowledge Gap")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r2.button("Attention"):
                    save_stat(st.session_state.last_q_id, False, None, "Attention")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r3.button("Interpretation"):
                    save_stat(st.session_state.last_q_id, False, None, "Interpretation")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# B. ANALİZ SAYFASI (Analytics) [cite: 58-63, 214-224]
else:
    st.header("📊 Personal Analytics & AI Insights")
    stats = conn.read(worksheet="User_Stats")
    
    if not stats.empty:
        col_graph, col_advice = st.columns([2, 1])
        
        with col_graph:
            # Başarı Pastası [cite: 219]
            fig = px.pie(stats, names='is_correct', title="Total Accuracy", hole=0.5,
                         color='is_correct', color_discrete_map={True:'#2ecc71', False:'#e74c3c'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col_advice:
            st.subheader("💡 AI Advice")
            # Hata nedenine göre tavsiye üretme [cite: 63, 221, 222]
            if "error_reason" in stats.columns:
                top_reason = stats['error_reason'].value_counts().idxmax() if not stats['error_reason'].isna().all() else None
                
                st.info(f"Main struggle: **{top_reason}**")
                if top_reason == "Knowledge Gap":
                    st.write("You are missing fundamental concepts. Re-read the theory[cite: 222].")
                elif top_reason == "Attention":
                    st.write("Focus more! You know the material but you are rushing[cite: 221].")
                elif top_reason == "Interpretation":
                    st.write("Read the questions carefully. The wording is tricking you.")
    else:
        st.info("Start your first session to see analytics!")
