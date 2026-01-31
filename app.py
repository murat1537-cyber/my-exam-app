import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. TASARIM VE GÜVENLİK ---
st.set_page_config(page_title="AI Exam Mentor Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .explanation-box { background-color: #fff9db; padding: 20px; border-radius: 15px; border-left: 5px solid #fcc419; margin-top: 20px; font-style: italic; color: #856404; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    .admin-card { background: #e9ecef; padding: 20px; border-radius: 15px; border: 1px dashed #6c757d; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. OTURUM DURUMLARI ---
states = {
    'q_idx': 0, 'view': 'Main', 'feedback': None, 
    'smart_list': None, 'start_time': None, 
    'is_sprint_active': False, 'admin_auth': False
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 4. YARDIMCI FONKSİYONLAR ---
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

def create_error_report(stats_df, questions_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Personal AI Error Analysis", ln=True, align='C')
    pdf.ln(10)
    # Rapor mantığı (TRUE/FALSE kontrolü)
    stats_df['is_correct'] = stats_df['is_correct'].astype(str).str.upper()
    wrong_ids = stats_df[stats_df['is_correct'] == "FALSE"]['question_id'].unique()
    for qid in wrong_ids:
        q_info = questions_df[questions_df['id'].astype(str) == str(qid)]
        if not q_info.empty:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(185, 7, f"Q: {q_info['content_text'].values[0]}")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 7, f"Correct: {q_info['correct_option'].values[0]}", ln=True)
            pdf.ln(3)
    return bytes(pdf.output())

# --- 5. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Learning Hub")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint"): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate"): st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    else:
        if st.button("🚀 New 10-Min Sprint"):
            questions = conn.read(worksheet="Questions", ttl=0)
            st.session_state.smart_list = questions.sample(frac=1).reset_index(drop=True)
            st.session_state.q_idx = 0; st.session_state.start_time = datetime.now()
            st.session_state.is_sprint_active = True; st.session_state.view = 'Study'; st.rerun()
    
    st.write("---")
    if st.button("📊 AI Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Panel"): st.session_state.view = 'Admin'

# --- 6. GÖRÜNÜMLER ---

# A. ÇALIŞMA EKRANI
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Remaining: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (col1 if i % 2 == 0 else col2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Correct!")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box">{curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Guess"): save_stat(st.session_state.last_q_id, True, "Guessed", None); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Wrong! Correct: {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box">{curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Knowledge"): save_stat(st.session_state.last_q_id, False, None, "Knowledge"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Careless"): save_stat(st.session_state.last_q_id, False, None, "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Logic"): save_stat(st.session_state.last_q_id, False, None, "Logic"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# B. ANALİZ EKRANI
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Insights")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    if not stats.empty:
        stats['is_correct'] = stats['is_correct'].astype(str).str.upper()
        fig = px.pie(stats, names='is_correct', hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'})
        st.plotly_chart(fig)
        if st.button("Generate Error Report"):
            q_df = conn.read(worksheet="Questions", ttl=0)
            report = create_error_report(stats, q_df)
            st.download_button("📥 Download PDF", data=report, file_name="report.pdf")
    else: st.info("No data yet.")

# C. ADMIN PANELİ (YENİ!)
elif st.session_state.view == 'Admin':
    st.header("🔑 Admin Management Panel")
    
    if not st.session_state.admin_auth:
        pw = st.text_input("Enter Admin Password", type="password")
        if pw == "1234": # Şifreni buradan değiştirebilirsin
            st.session_state.admin_auth = True
            st.rerun()
    else:
        st.success("Authorized Access")
        st.markdown('<div class="admin-card">', unsafe_allow_html=True)
        st.subheader("📤 Bulk Question Upload")
        uploaded_file = st.file_uploader("Upload Excel (.xlsx) or CSV", type=['xlsx', 'csv'])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    new_q = pd.read_csv(uploaded_file)
                else:
                    new_q = pd.read_excel(uploaded_file)
                
                st.write("Preview of data to be uploaded:")
                st.dataframe(new_q.head())
                
                if st.button("🚀 Confirm and Upload to Cloud"):
                    current_q = conn.read(worksheet="Questions", ttl=0)
                    updated_q = pd.concat([current_q, new_q], ignore_index=True)
                    conn.update(worksheet="Questions", data=updated_q)
                    st.success(f"Successfully added {len(new_q)} new questions!")
            except Exception as e:
                st.error(f"Format Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("Logout Admin"):
            st.session_state.admin_auth = False
            st.session_state.view = 'Main'
            st.rerun()
