import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import random

# --- 1. GÜVENLİK VE TASARIM ---
st.set_page_config(page_title="AI Smart Prep", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f4f7f9; }
    .stButton>button { border-radius: 12px; height: 3.5em; transition: 0.3s; }
    .stButton>button:hover { background-color: #007bff; color: white; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    .advice-box { background-color: #e1f5fe; padding: 15px; border-radius: 10px; border-left: 5px solid #01579b; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. OTURUM YÖNETİMİ ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Study'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = []

# --- 4. AKILLI ALGORİTMA (Smart Selection) ---
def get_smart_questions():
    all_q = conn.read(worksheet="Questions")
    stats = conn.read(worksheet="User_Stats")
    
    if stats.empty:
        return all_q
    
    # Yanlış yapılan veya emin olunmayan soruların ID'lerini bul
    trouble_ids = stats[(stats['is_correct'] == False) | (stats['confidence_level'] == 'Guessed')]['question_id'].unique()
    
    # Bu sorulara öncelik ver (Trouble questions first)
    trouble_q = all_q[all_q['id'].isin(trouble_ids)]
    other_q = all_q[~all_q['id'].isin(trouble_ids)]
    
    # Karıştır ve birleştir
    combined = pd.concat([trouble_q.sample(frac=1), other_q.sample(frac=1)])
    return combined

def save_result(q_id, correct, confidence, reason):
    new_data = pd.DataFrame([{
        "user_id": "User_1",
        "question_id": q_id,
        "is_correct": correct,
        "confidence_level": confidence,
        "error_reason": reason,
        "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    conn.create(worksheet="User_Stats", data=new_data)

# --- 5. ARAYÜZ ---
with st.sidebar:
    st.title("🚀 Navigation")
    if st.button("📝 Smart Study"): 
        st.session_state.view = 'Study'
        st.session_state.smart_list = get_smart_questions()
        st.session_state.q_idx = 0
    if st.button("📊 AI Analytics"): st.session_state.view = 'Analytics'

# --- A. ÇALIŞMA MODU ---
if st.session_state.view == 'Study':
    if len(st.session_state.smart_list) == 0:
        st.session_state.smart_list = get_smart_questions()
    
    df = st.session_state.smart_list
    if not df.empty:
        curr = df.iloc[st.session_state.q_idx]
        st.progress((st.session_state.q_idx + 1) / len(df))
        
        st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
        st.write("")

        for opt in ['A', 'B', 'C', 'D']:
            if st.button(f"{opt}) {curr[f'option_{opt.lower()}']}", key=f"btn_{opt}"):
                st.session_state.feedback = (opt == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

        if st.session_state.feedback is not None:
            if st.session_state.feedback:
                st.success("✅ Brilliant! Correct.")
                st.write("How confident are you?")
                c1, c2 = st.columns(2)
                if c1.button("🎯 100% Sure"):
                    save_result(st.session_state.last_q_id, True, "Sure", None)
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if c2.button("🎲 I Guessed"):
                    save_result(st.session_state.last_q_id, True, "Guessed", None)
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Not quite. Correct answer: {curr['correct_option']}")
                st.write("What went wrong?")
                r1, r2, r3 = st.columns(3)
                if r1.button("Knowledge Gap"):
                    save_result(st.session_state.last_q_id, False, None, "Knowledge Gap")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r2.button("Careless Mistake"):
                    save_result(st.session_state.last_q_id, False, None, "Attention")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r3.button("Hard to Interpret"):
                    save_result(st.session_state.last_q_id, False, None, "Interpretation")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# --- B. ANALİZ VE TAVSİYELER ---
else:
    st.header("📈 Personal Progress Report")
    stats = conn.read(worksheet="User_Stats")
    
    if not stats.empty:
        # Görsel Analiz
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(stats, names='is_correct', title="Success Ratio", hole=0.4)
            st.plotly_chart(fig)
        with col2:
            # AI Yazılı Tavsiyeler (Logic)
            st.subheader("💡 AI Study Recommendations")
            
            # Hata Analizi Tavsiyesi
            top_reason = stats['error_reason'].value_counts().idxmax() if not stats['error_reason'].isna().all() else "None"
            
            st.markdown('<div class="advice-box">', unsafe_allow_html=True)
            if top_reason == "Knowledge Gap":
                st.write("**Advice:** You are struggling with core concepts. Stop solving new questions and revisit your textbooks for this topic.")
            elif top_reason == "Attention":
                st.write("**Advice:** Your accuracy is high but you make 'careless mistakes'. Try to spend at least 10 more seconds on each question.")
            elif top_reason == "Interpretation":
                st.write("**Advice:** You understand the topic but the questions are confusing you. Focus on reading more case studies.")
            else:
                st.write("**Advice:** Keep it up! You are on a balanced track.")
            st.markdown('</div>', unsafe_allow_html=True)

            # Emin olunmayan sorular uyarısı
            guesses = stats[stats['confidence_level'] == 'Guessed'].shape[0]
            if guesses > 3:
                st.warning(f"Note: You have guessed {guesses} correct answers. These are hidden weaknesses!")

    else:
        st.info("No data yet. Start studying to unlock AI insights.")
