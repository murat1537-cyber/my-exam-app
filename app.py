import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import time

# --- 1. CISSP DOMAIN MAPPING ---
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

# --- 2. THEME & STYLING ---
st.set_page_config(page_title="CISSP AI Mentor", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .q-card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #007bff; }
    .explanation-box { background-color: #fff9db; padding: 15px; border-radius: 10px; border-left: 5px solid #fcc419; margin-top: 10px; color: #856404; }
    .timer-box { font-size: 24px; font-weight: bold; color: #d32f2f; text-align: center; background: #ffebee; border-radius: 8px; padding: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 10px; height: 3.5em; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & SESSION MANAGEMENT ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. CORE FUNCTIONS ---

def safe_text(text):
    """Sanitizes text for FPDF to avoid encoding crashes [cite: 8]"""
    mapping = str.maketrans("ğĞçÇşŞüÜöÖıİ", "gGcCsSuUoOiI")
    return str(text).translate(mapping).encode('latin-1', 'replace').decode('latin-1')

def create_pdf(stats_df, questions_df):
    """Generates a professional PDF with proper margins and wrapping [cite: 4, 7]"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CISSP Incorrect Answers Report", ln=True, align='C')
    pdf.ln(10)
    
    stats_df['is_correct_clean'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})
    wrong_entries = stats_df[stats_df['is_correct_clean'] == "FALSE"]
    
    if wrong_entries.empty:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No incorrect answers recorded yet.", ln=True)
    else:
        for _, row in wrong_entries.iterrows():
            q_id_str = str(row['question_id']).split('.')[0]
            q_info = questions_df[questions_df['id'].astype(str).str.split('.').str[0] == q_id_str]
            
            if not q_info.empty:
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 8, safe_text(f"Question: {q_info['content_text'].values[0]}"))
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 7, safe_text(f"Correct Answer: {q_info['correct_option'].values[0]}"))
                pdf.ln(4); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
                if pdf.get_y() > 250: pdf.add_page()
    return bytes(pdf.output())

# --- 5. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🛡️ CISSP Mentor")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint"): 
            st.session_state.view = 'Study'
            st.rerun()
        if st.button("🛑 Terminate Sprint"): 
            st.session_state.is_sprint_active = False
            st.session_state.view = 'Analytics'
            st.rerun()
    else:
        if st.button("🚀 Start 10-Min Sprint"):
            q_df = conn.read(worksheet="Questions", ttl=0)
            # FIXED: Corrected sample logic 
            num_to_sample = min(len(q_df), 25)
            st.session_state.smart_list = q_df.sample(n=num_to_sample).reset_index(drop=True)
            st.session_state.q_idx = 0; st.session_state.start_time = time.time()
            st.session_state.is_sprint_active = True
            st.session_state.view = 'Study'
            st.rerun()
    
    st.write("---")
    if st.button("📊 Performance Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Panel"): st.session_state.view = 'Admin'

# --- 6. STUDY INTERFACE ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # LIVE TIMER: Place inside a container to refresh 
    timer_placeholder = st.empty()
    elapsed = time.time() - st.session_state.start_time
    remaining = max(0, int(600 - elapsed))
    
    if remaining <= 0:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    
    mins, secs = divmod(remaining, 60)
    timer_placeholder.markdown(f'<div class="timer-box">⏱️ Time Left: {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    st.caption(f"📍 Domain: {TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General Domain')}")
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (col1 if i % 2 == 0 else col2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

    if st.session_state.feedback is not None:
        # FEEDBACK: Explicitly show the correct answer regardless of choice 
        if st.session_state.feedback:
            st.success(f"✅ Correct! The answer is {curr['correct_option']}")
        else:
            st.error(f"❌ Incorrect! The correct answer is {curr['correct_option']}")
        
        if 'explanation' in curr: 
            st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
        
        r1, r2 = st.columns(2)
        if r1.button("➡️ Next Question"):
            st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        if r2.button("⬅️ Previous Question") and st.session_state.q_idx > 0:
            st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# --- 7. ANALYTICS ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Dashboard")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty and not questions.empty:
        stats['qid_clean'] = stats['question_id'].astype(str).str.split('.').str[0]
        questions['qid_clean'] = questions['id'].astype(str).str.split('.').str[0]
        merged = pd.merge(stats, questions[['qid_clean', 'topic_id']], on='qid_clean')
        merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP).fillna("Other Domains")
        merged['is_correct_clean'] = merged['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})

        col_p, col_b = st.columns([1, 2])
        with col_p:
            st.plotly_chart(px.pie(merged, names='is_correct_clean', title="Success Rate", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
            if st.button("📥 Download Incorrect Answers PDF"):
                report = create_pdf(stats, questions)
                st.download_button("Download Report", data=report, file_name="incorrect_answers.pdf")
        
        with col_b:
            # Proficiency Matrix (%)
            domain_perf = merged.groupby('Domain')['is_correct_clean'].value_counts(normalize=True).unstack().fillna(0) * 100
            if 'TRUE' not in domain_perf: domain_perf['TRUE'] = 0
            st.subheader("Domain Success Rates (%)")
            st.dataframe(domain_perf[['TRUE']].rename(columns={'TRUE': 'Success Rate %'}).style.background_gradient(cmap='RdYlGn'))
    else:
        st.info("Start a sprint to generate your performance data.")
