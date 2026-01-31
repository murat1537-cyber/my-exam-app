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

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="CISSP AI Mentor", layout="wide")
st.markdown("""
    <style>
    .q-card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 5px solid #007bff; margin-bottom: 20px;}
    .explanation-box { background-color: #fff9db; padding: 15px; border-radius: 10px; border-left: 5px solid #fcc419; margin-top: 10px; color: #856404; }
    .timer-box { font-size: 24px; font-weight: bold; color: #d32f2f; text-align: center; background: #ffebee; border-radius: 8px; padding: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 10px; height: 3.5em; font-weight: 600; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. FUNCTIONS ---

def safe_text(text):
    """PDF için güvenli metin temizliği"""
    mapping = str.maketrans("ğĞçÇşŞüÜöÖıİ", "gGcCsSuUoOiI")
    return str(text).translate(mapping).encode('latin-1', 'replace').decode('latin-1')

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
    except: pass # Basit hata yönetimi

def create_pdf(stats_df, questions_df):
    """PDF oluşturma (Genişlik hatası düzeltildi)"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CISSP Report", ln=True, align='C')
    pdf.ln(10)
    
    stats_df['is_correct_clean'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})
    wrong = stats_df[stats_df['is_correct_clean'] == "FALSE"]
    
    if wrong.empty:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No errors found.", ln=True)
    else:
        for _, row in wrong.iterrows():
            q_id = str(row['question_id']).split('.')[0]
            q_info = questions_df[questions_df['id'].astype(str).str.split('.').str[0] == q_id]
            if not q_info.empty:
                pdf.set_font("Helvetica", "B", 10)
                # Genişliği 190 olarak sabitledik
                pdf.multi_cell(190, 7, safe_text(f"Q: {q_info['content_text'].values[0]}"))
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(190, 7, safe_text(f"Correct: {q_info['correct_option'].values[0]} | Reason: {row['error_reason']}"))
                pdf.ln(5); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
    return bytes(pdf.output())

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ CISSP Mentor")
    if st.session_state.is_sprint_active:
        if st.button("▶️ Return to Sprint"): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate Sprint"): 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    else:
        if st.button("🚀 Start Sprint"):
            q_df = conn.read(worksheet="Questions", ttl=0)
            # Örnekleme hatası düzeltildi
            sample_n = min(len(q_df), 25)
            st.session_state.smart_list = q_df.sample(n=sample_n).reset_index(drop=True)
            st.session_state.q_idx = 0; st.session_state.start_time = time.time()
            st.session_state.is_sprint_active = True; st.session_state.view = 'Study'; st.rerun()
    
    st.write("---")
    if st.button("📊 Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin"): st.session_state.view = 'Admin'

# --- 6. STUDY VIEW ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    # Timer
    ph = st.empty()
    rem = max(0, int(600 - (time.time() - st.session_state.start_time)))
    if rem <= 0: st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    
    st.caption(f"Topic: {TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General')}")
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (c1 if i%2==0 else c2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']
                st.rerun() # Feedback durumunu güncellemek için hemen yenile

    # GERİ BİLDİRİM VE BUTONLAR (Burada yeniden çiziliyor)
    if st.session_state.feedback is not None:
        st.write("---")
        if st.session_state.feedback:
            st.success(f"✅ Correct! Answer: {curr['correct_option']}")
            if 'explanation' in curr: st.info(f"ℹ️ {curr['explanation']}")
            
            # Doğru Cevap Butonları
            sc1, sc2 = st.columns(2)
            if sc1.button("🎯 Sure (Kesin)"):
                save_stat(st.session_state.last_q_id, True, "Sure", "None")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if sc2.button("🎲 Guessed (Tahmin)"):
                save_stat(st.session_state.last_q_id, True, "Guessed", "None")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Incorrect! Correct Answer: {curr['correct_option']}")
            if 'explanation' in curr: st.info(f"ℹ️ {curr['explanation']}")
            
            # Yanlış Cevap Butonları
            ec1, ec2, ec3 = st.columns(3)
            if ec1.button("🧠 Knowledge Gap"):
                save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if ec2.button("👀 Attention"):
                save_stat(st.session_state.last_q_id, False, "None", "Attention")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if ec3.button("🤔 Logic"):
                save_stat(st.session_state.last_q_id, False, "None", "Interpretation")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# --- 7. ANALYTICS VIEW ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Dashboard")
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0)
        questions = conn.read(worksheet="Questions", ttl=0)
        
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            merged['is_correct'] = merged['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})

            c1, c2 = st.columns([1,2])
            with c1:
                st.plotly_chart(px.pie(merged, names='is_correct', title="Success Rate", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
                if st.button("📥 Download PDF"):
                    st.download_button("Download", create_pdf(stats, questions), "report.pdf")
            
            with c2:
                # Matplotlib hatasını önlemek için basit dataframe kullanımı
                perf = merged.groupby('Domain')['is_correct'].value_counts(normalize=True).unstack().fillna(0) * 100
                st.subheader("Success by Domain (%)")
                st.dataframe(perf) # Gradient kaldırıldı, hata vermez
                
                st.plotly_chart(px.bar(merged, x='Domain', color='is_correct', barmode='group'), use_container_width=True)
        else: st.info("No data.")
    except Exception as e: st.error(f"Data error: {e}")

# --- 8. ADMIN VIEW ---
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        if st.text_input("Password", type="password") == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        up = st.file_uploader("Upload Excel", type=['xlsx'])
        if up and st.button("Sync"):
            conn.update(worksheet="Questions", data=pd.concat([conn.read(worksheet="Questions"), pd.read_excel(up)], ignore_index=True))
            st.success("Done!")
