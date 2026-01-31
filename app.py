import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. SAYFA AYARLARI VE GÜVENLİK
st.set_page_config(page_title="Exam Prep Master", layout="wide")

# Görünüm ve Güvenlik Kalkanı (OWASP A03 - Metin Kopyalama Engeli) [cite: 17, 18, 165]
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f0f2f6; }
    .question-box { background-color: white; padding: 25px; border-radius: 15px; border-left: 5px solid #007bff; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 10px; height: 3.5em; }
    </style>
    """, unsafe_allow_html=True) # Hata burada düzeltildi: allow_html olmalı.

# 2. VERİ BAĞLANTISI
conn = st.connection("gsheets", type=GSheetsConnection)

def get_questions():
    return conn.read(worksheet="Questions")

# 3. DURUM YÖNETİMİ (Session State)
if 'question_index' not in st.session_state: st.session_state.question_index = 0
if 'show_feedback' not in st.session_state: st.session_state.show_feedback = False

df_questions = get_questions()
total_q = len(df_questions)

# 4. ARAYÜZ
st.title("📝 Study Mode")
st.progress((st.session_state.question_index + 1) / total_q)

if total_q > 0:
    current_q = df_questions.iloc[st.session_state.question_index]
    
    st.markdown(f'<div class="question-box">', unsafe_allow_html=True)
    st.markdown(f"**Question {st.session_state.question_index + 1}:**")
    st.markdown(f"### {current_q['content_text']}")
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")

    # Cevap Şıkları (OWASP: Input temizliği Streamlit tarafından otomatik yapılır)
    options = ['A', 'B', 'C', 'D']
    cols = st.columns(2)
    for i, opt in enumerate(options):
        col = cols[i % 2]
        if col.button(f"{opt}) {current_q[f'option_{opt.lower()}']}", key=f"btn_{opt}"):
            st.session_state.selected_answer = opt
            st.session_state.show_feedback = True

    # 5. METCOGNITION POP-UP (Emin misin? / Neden Yanlış?) [cite: 50, 51, 198]
    if st.session_state.show_feedback:
        is_correct = st.session_state.selected_answer == current_q['correct_option']
        
        if is_correct:
            st.success("✅ Correct!")
            # "Emin misin?" Sorgusu [cite: 51, 203]
            st.write("**Are you sure?**")
            c1, c2 = st.columns(2)
            if c1.button("I was sure", key="sure"): 
                # Burada User_Stats'a kayıt kodu gelecek [cite: 142]
                st.session_state.show_feedback = False
                st.session_state.question_index += 1
                st.rerun()
            if c2.button("I guessed", key="guess"):
                st.session_state.show_feedback = False
                st.session_state.question_index += 1
                st.rerun()
        else:
            st.error(f"❌ Incorrect. The correct answer was {current_q['correct_option']}.")
            # "Hata Nedeni" Sorgusu [cite: 53, 209]
            st.write("**What was the reason for the error?**")
            r1, r2, r3 = st.columns(3)
            reasons = ["Knowledge Gap", "Interpretation", "Attention"] [cite: 54, 55, 56]
            if r1.button(reasons[0]): st.session_state.show_feedback = False; st.session_state.question_index += 1; st.rerun()
            if r2.button(reasons[1]): st.session_state.show_feedback = False; st.session_state.question_index += 1; st.rerun()
            if r3.button(reasons[2]): st.session_state.show_feedback = False; st.session_state.question_index += 1; st.rerun()

else:
    st.warning("Please add questions to your Google Sheet.")
