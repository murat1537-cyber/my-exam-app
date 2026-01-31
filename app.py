import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. CISSP TOPIC MAPPING (Updated) ---
TOPIC_MAP = {
    "1": "Security and Risk Management",
    "2": "Asset Security",
    "3": "Security Architecture and Engineering",
    "4": "Communication and Network Security",
    "5": "Identity and Access Management (IAM)",
    "6": "Security Assessment and Testing",
    "7": "Security Operations",
    "8": "Software Development Security"
}

# --- 2. DESIGN & SECURITY ---
st.set_page_config(page_title="CISSP AI Mentor Pro", layout="wide")
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

# --- 3. CONNECTION & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize Session States
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. UTILITY FUNCTIONS ---
def safe_text(text):
    """Replaces non-standard characters to prevent PDF crashes"""
    mapping = str.maketrans("ğĞçÇşŞüÜöÖıİ", "gGcCsSuUoOiI")
    return str(text).translate(mapping)

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

def create_pdf(stats_df, questions_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, safe_text("CISSP Performance Analysis"), ln=True, align='C')
    pdf.ln(10)
    
    # Data Normalization
    stats_df['is_correct_clean'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})
    wrong_entries = stats_df[stats_df['is_correct_clean'] == "FALSE"]
    
    if wrong_entries.empty:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No errors found to report.", ln=True)
    else:
        for _, row in wrong_entries.iterrows():
            q_id_str = str(row['question_id']).split('.')[0]
            q_info = questions_df[questions_df['id'].astype(str).str.split('.').str[0] == q_id_str]
            
            if not q_info.empty:
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(180, 7, safe_text(f"Question: {q_info['content_text'].values[0]}"))
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(180, 6, safe_text(f"Correct: {q_info['correct_option'].values[0]} | Reason: {row['error_reason']}"))
                pdf.ln(5); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
                if pdf.get_y() > 250: pdf.add_page()
    return bytes(pdf.output())

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🏆 AI Mentor Pro")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint"): 
            st.session_state.view = 'Study'
            st.rerun()
        if st.button("🛑 Terminate Sprint"): # Fixed swap logic
            st.session_state.is_sprint_active = False
            st.session_state.view = 'Analytics'
            st.rerun()
    else:
        if st.button("🚀 Start New Sprint"):
            q_df = conn.read(worksheet="Questions", ttl=0)
            st.session_state.smart_list = q_df.sample(frac=1).reset_index(drop=True)
            st.session_state.q_idx = 0; st.session_state.start_time = datetime.now()
            st.session_state.is_sprint_active = True
            st.session_state.view = 'Study'
            st.rerun()
    
    st.write("---")
    if st.button("📊 Performance Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Panel"): st.session_state.view = 'Admin'

# --- 6. VIEWS ---

# STUDY MODE
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    t_id_clean = str(curr['topic_id']).split('.')[0]
    topic_display = TOPIC_MAP.get(t_id_clean, "General Domain")
    
    st.caption(f"📍 Domain: {topic_display}")
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
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Guess"): save_stat(st.session_state.last_q_id, True, "Guessed", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Wrong! Correct: {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Knowledge Gap"): save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Attention"): save_stat(st.session_state.last_q_id, False, "None", "Attention"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Interpretation"): save_stat(st.session_state.last_q_id, False, "None", "Interpretation"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

    st.write("---")
    if st.button("⬅️ Previous Question") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# ANALYTICS
elif st.session_state.view == 'Analytics':
    st.header("📊 Domain Performance Analysis")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty and not questions.empty:
        # Clean IDs and Merge
        stats['qid_clean'] = stats['question_id'].astype(str).str.split('.').str[0]
        questions['qid_clean'] = questions['id'].astype(str).str.split('.').str[0]
        merged = pd.merge(stats, questions[['qid_clean', 'topic_id']], on='qid_clean')
        
        # Mapping CISSP Domains
        merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP).fillna("Other Domains")
        merged['is_correct_clean'] = merged['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})

        col_pie, col_bar = st.columns([1, 2])
        with col_pie:
            st.plotly_chart(px.pie(merged, names='is_correct_clean', title="Success Rate", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
            if st.button("📥 Download PDF Report"):
                report = create_pdf(stats, questions)
                st.download_button("Download Now", data=report, file_name="cissp_performance.pdf")
        
        with col_bar:
            topic_chart = px.bar(merged, x='Domain', color='is_correct_clean', barmode='group', title="Accuracy by CISSP Domain", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'})
            st.plotly_chart(topic_chart, use_container_width=True)
    else:
        st.info("No data recorded yet. Start a session!")

# ADMIN
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        pw = st.text_input("Admin Password", type="password")
        if pw == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        st.subheader("Admin Domain Management")
        uploaded = st.file_uploader("Upload .xlsx Question Set", type=['xlsx'])
        if uploaded:
            new_q = pd.read_excel(uploaded)
            if st.button("Sync Domain Data"):
                old_q = conn.read(worksheet="Questions", ttl=0)
                conn.update(worksheet="Questions", data=pd.concat([old_q, new_q], ignore_index=True))
                st.success("Domain database synchronized!")
