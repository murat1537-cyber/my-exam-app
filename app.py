import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. KONU EŞLEŞTİRME ---
TOPIC_MAP = {
    "1": "Trafik ve Çevre Bilgisi",
    "2": "İlk Yardım Bilgisi",
    "3": "Araç Tekniği",
    "4": "Trafik Adabı",
    "5": "Trafik İşaretleri",
    "6": "Güvenli Sürüş Teknikleri",
    "7": "Motor Bilgisi",
    "8": "Genel Mevzuat"
}

# --- 2. TASARIM ---
st.set_page_config(page_title="AI Exam Mentor Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .explanation-box { background-color: #fff9db; padding: 15px; border-radius: 12px; border-left: 5px solid #fcc419; margin-top: 15px; color: #856404; }
    .timer-box { font-size: 20px; font-weight: bold; color: #d32f2f; text-align: center; background: #ffebee; border-radius: 10px; padding: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BAĞLANTI VE DURUM ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- 4. VERİ YAZMA VE RAPOR ---
def save_stat(q_id, correct, confidence, reason):
    try:
        existing_df = conn.read(worksheet="User_Stats", ttl=0)
        new_row = pd.DataFrame([{
            "user_id": "User_01", "question_id": str(q_id),
            "is_correct": "TRUE" if correct else "FALSE",
            "confidence_level": str(confidence), "error_reason": str(reason),
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).dropna(how='all')
        conn.update(worksheet="User_Stats", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Save error: {e}"); return False

def create_pdf_report(stats_df, questions_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Personal Performance & Error Analysis", ln=True, align='C')
    pdf.ln(10)
    
    # Veri temizleme
    stats_df['is_correct'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})
    wrong_entries = stats_df[stats_df['is_correct'] == "FALSE"]
    
    for _, row in wrong_entries.iterrows():
        q_info = questions_df[questions_df['id'].astype(str) == str(row['question_id'])]
        if not q_info.empty:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(180, 7, f"Question: {q_info['content_text'].values[0]}")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(180, 6, f"Correct Answer: {q_info['correct_option'].values[0]} | Error Type: {row['error_reason']}")
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            if pdf.get_y() > 260: pdf.add_page()
    return bytes(pdf.output())

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🏆 AI Mentor Pro")
    if st.button("🚀 Start New Sprint"):
        q_df = conn.read(worksheet="Questions", ttl=0)
        st.session_state.smart_list = q_df.sample(frac=1).reset_index(drop=True)
        st.session_state.q_idx = 0; st.session_state.start_time = datetime.now()
        st.session_state.view = 'Study'; st.rerun()
    
    st.write("---")
    if st.button("📊 Advanced Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Panel"): st.session_state.view = 'Admin'

# --- 6. GÖRÜNÜMLER ---

# A. STUDY MODE (Butonlar buraya eklendi!)
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # Sayaç
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    topic_name = TOPIC_MAP.get(str(curr['topic_id']), "General")
    
    st.caption(f"📍 Topic: {topic_name}")
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    # Şık Butonları
    col1, col2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (col1 if i % 2 == 0 else col2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

    # Geri Bildirim
    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Correct!")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Guess"): save_stat(st.session_state.last_q_id, True, "Guessed", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Wrong! Correct Answer: {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Knowledge"): save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Attention"): save_stat(st.session_state.last_q_id, False, "None", "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Logic"): save_stat(st.session_state.last_q_id, False, "None", "Logic"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

    # Önceki Soru Opsiyonu
    st.write("---")
    if st.button("⬅️ Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# B. ANALYTICS (Gelişmiş Konu Analizi)
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Dashboard")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty and not questions.empty:
        # Merge for topic analytics
        stats['question_id'] = stats['question_id'].astype(str)
        questions['id'] = questions['id'].astype(str)
        merged = pd.merge(stats, questions[['id', 'topic_id']], left_on='question_id', right_on='id')
        merged['Topic'] = merged['topic_id'].astype(str).map(TOPIC_MAP)
        merged['is_correct'] = merged['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})

        col_pie, col_bar = st.columns([1, 2])
        with col_pie:
            st.plotly_chart(px.pie(merged, names='is_correct', title="Overall Success", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}))
            if st.button("Download Detailed PDF"):
                report = create_pdf_report(stats, questions)
                st.download_button("📥 Get PDF", data=report, file_name="analysis.pdf")
        
        with col_bar:
            topic_chart = px.bar(merged, x='Topic', color='is_correct', barmode='group', title="Success by Topic", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'})
            st.plotly_chart(topic_chart, use_container_width=True)
    else:
        st.info("No data yet.")

# C. ADMIN
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        pw = st.text_input("Password", type="password")
        if pw == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        uploaded = st.file_uploader("Upload Excel", type=['xlsx'])
        if uploaded:
            new_q = pd.read_excel(uploaded)
            if st.button("Update Questions"):
                old_q = conn.read(worksheet="Questions", ttl=0)
                conn.update(worksheet="Questions", data=pd.concat([old_q, new_q], ignore_index=True))
                st.success("Uploaded!")
