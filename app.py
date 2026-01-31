import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. TASARIM VE GÜVENLİK ---
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

# --- 4. VERİ YAZMA ---
def save_stat(q_id, correct, confidence, reason):
    try:
        existing_df = conn.read(worksheet="User_Stats", ttl=0)
        new_row = pd.DataFrame([{
            "user_id": "User_01",
            "question_id": str(q_id),
            "is_correct": "True" if correct else "False",
            "confidence_level": str(confidence) if confidence else "None",
            "error_reason": str(reason) if reason else "None",
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).dropna(how='all')
        conn.update(worksheet="User_Stats", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

# --- 5. HATA RAPORU OLUŞTURMA (PDF) ---
def create_error_report(stats_df, questions_df):
    """Sadece yanlış yapılan soruları içeren detaylı PDF hazırlar [cite: 58, 61]"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Wrong Answers & Analysis Report", ln=True, align='C')
    pdf.ln(10)
    
    # Yanlış veya emin olunmayan soruları filtrele [cite: 44, 49, 151]
    wrong_stats = stats_df[(stats_df['is_correct'] == "False") | (stats_df['confidence_level'] == "Guessed")]
    
    if wrong_stats.empty:
        pdf.set_font("Arial", "", 12)
        pdf.cell(200, 10, "Great job! You have no recorded errors to report.", ln=True)
    else:
        for index, row in wrong_stats.iterrows():
            # Soru metnini bul [cite: 114, 153]
            q_text = questions_df[questions_df['id'].astype(str) == str(row['question_id'])]['content_text'].values[0]
            correct_ans = questions_df[questions_df['id'].astype(str) == str(row['question_id'])]['correct_option'].values[0]
            
            pdf.set_font("Arial", "B", 11)
            pdf.multi_cell(0, 10, f"Question: {q_text}")
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 10, f"Correct Answer: {correct_ans} | Reason for Error: {row['error_reason']}", ln=True)
            pdf.cell(0, 5, f"Confidence: {row['confidence_level']} | Date: {row['attempt_date']}", ln=True)
            pdf.ln(5)
            pdf.cell(0, 0, "", "T", ln=True) # Ayırıcı çizgi
            pdf.ln(5)
            
    return pdf.output()

# --- 6. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Control Center")
    if st.button("📝 Start 10-Min Sprint"):
        questions = conn.read(worksheet="Questions", ttl=0)
        st.session_state.smart_list = questions.sample(frac=1).reset_index(drop=True)
        st.session_state.q_idx = 0
        st.session_state.view = 'Study'
        st.session_state.start_time = datetime.now()
        st.rerun()
    
    if st.button("📊 Performance Analytics"):
        st.session_state.view = 'Analytics'
    
    if st.session_state.view == 'Study':
        st.write("---")
        if st.button("🛑 Finish Early"):
            st.session_state.view = 'Analytics'
            st.rerun()

# --- 7. ÇALIŞMA MODU ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
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
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"A) {curr['option_a']}", use_container_width=True): st.session_state.feedback = ('A' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"C) {curr['option_c']}", use_container_width=True): st.session_state.feedback = ('C' == curr['correct_option']); st.session_state.last_q_id = curr['id']
    with col2:
        if st.button(f"B) {curr['option_b']}", use_container_width=True): st.session_state.feedback = ('B' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        if st.button(f"D) {curr['option_d']}", use_container_width=True): st.session_state.feedback = ('D' == curr['correct_option']); st.session_state.last_q_id = curr['id']

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

    st.write("---")
    if st.button("⬅️ Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1
        st.session_state.feedback = None
        st.rerun()

# --- 8. ANALİZ VE ÖZEL RAPOR ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Analytics")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0) # Soru metinlerini PDF'e eklemek için oku [cite: 114]
    
    if not stats.empty:
        stats['is_correct'] = stats['is_correct'].astype(str)
        
        col_pie, col_bar = st.columns(2)
        with col_pie:
            fig_pie = px.pie(stats, names='is_correct', title="Accuracy Rate", 
                             color='is_correct', color_discrete_map={'True':'#2ecc71', 'False':'#e74c3c'})
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_bar:
            st.subheader("📋 Download Error Report")
            st.write("Click below to get a PDF of all your incorrect and guessed answers.")
            # PDF Rapor Butonu [cite: 58, 61]
            if st.button("Generate Detailed Error Report"):
                pdf_bytes = create_error_report(stats, questions)
                st.download_button("📥 Download Analysis (PDF)", data=pdf_bytes, file_name="error_analysis.pdf", mime="application/pdf")
            
            if not stats[stats['is_correct'] == 'False'].empty:
                fig_bar = px.bar(stats[stats['is_correct'] == 'False']['error_reason'].value_counts(), 
                                 title="Reasons for Mistakes")
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No stats recorded. Please solve some questions.")
