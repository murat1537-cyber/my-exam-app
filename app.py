import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
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

# --- 2. CONFIGURATION & PRO UI STYLING ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* Genel Arka Plan */
    .stApp { background-color: #f4f6f9; }
    
    /* Kart Tasarımları */
    .q-card { 
        background: white; 
        padding: 2.5rem; 
        border-radius: 15px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        border-left: 6px solid #2c3e50;
        margin-bottom: 25px;
    }
    
    /* Sidebar Profil Kartı */
    .profile-card {
        background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .profile-rank { font-size: 14px; opacity: 0.9; letter-spacing: 1px; text-transform: uppercase; }
    .profile-name { font-size: 24px; font-weight: bold; margin: 10px 0; }
    
    /* KPI Kartları */
    .metric-container {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
        border-bottom: 4px solid #3498db;
    }
    .metric-value { font-size: 28px; font-weight: bold; color: #2c3e50; }
    .metric-label { font-size: 14px; color: #7f8c8d; text-transform: uppercase; }
    
    /* DEV START BUTONU ÖZELLEŞTİRMESİ */
    /* Sadece type="primary" olan butonu hedefler */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(45deg, #FF512F 0%, #DD2476 100%);
        color: white;
        height: 80px; /* Daha yüksek */
        font-size: 24px !important; /* Daha büyük yazı */
        font-weight: 800;
        border: none;
        border-radius: 12px;
        box-shadow: 0 10px 20px rgba(221, 36, 118, 0.3);
        transition: all 0.3s ease;
        animation: pulse 2s infinite;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 15px 25px rgba(221, 36, 118, 0.4);
    }
    
    /* Pulse Animasyonu */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(221, 36, 118, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(221, 36, 118, 0); }
        100% { box-shadow: 0 0 0 0 rgba(221, 36, 118, 0); }
    }

    /* Diğer Standart Butonlar */
    div.stButton > button[kind="secondary"] {
        border-radius: 8px; 
        height: 3.2em; 
        font-weight: 600; 
        border: 1px solid #dfe6e9;
    }

    /* Timer & Uyarılar */
    .timer-box { font-size: 22px; font-weight: 800; color: #e74c3c; text-align: center; background: #fadbd8; border-radius: 8px; padding: 12px; margin-bottom: 20px; }
    .explanation-box { background-color: #e8f6f3; padding: 20px; border-radius: 10px; border-left: 5px solid #1abc9c; margin-top: 15px; color: #16a085; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'is_sprint_active' not in st.session_state: st.session_state.is_sprint_active = False

# --- 4. DATA FUNCTIONS ---
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
    except: pass 

def get_user_rank(df):
    """Kullanıcının çözdüğü soru sayısına göre rütbe belirler"""
    if df.empty: return "Novice", 0
    count = len(df)
    if count < 10: return "🟢 Novice", count
    elif count < 50: return "🔵 Junior Analyst", count
    elif count < 100: return "🟣 Security Architect", count
    else: return "👑 CISO Master", count

# --- 5. SIDEBAR ---
with st.sidebar:
    # --- Profil Kartı ---
    try:
        stats_preview = conn.read(worksheet="User_Stats", ttl=60)
        rank, total_q = get_user_rank(stats_preview)
    except: rank, total_q = "Novice", 0
    
    st.markdown(f"""
    <div class="profile-card">
        <div style="font-size: 40px;">🛡️</div>
        <div class="profile-name">Cyber Warrior</div>
        <div class="profile-rank">{rank}</div>
        <div style="margin-top:10px; font-size:12px;">Questions Solved: {total_q}</div>
    </div>
    """, unsafe_allow_html=True)
    # --------------------

    if st.session_state.is_sprint_active:
        st.info("⚡ Sprint in Progress")
        if st.button("▶️ Return to Sprint"): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate Sprint"): 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    else:
        st.subheader("📚 Study Configuration")
        domain_options = ["All Domains (Mix)"] + list(TOPIC_MAP.values())
        selected_mode = st.selectbox("Target Domain:", domain_options)
        
        st.write("") # Biraz boşluk bırak
        
        # --- DEV START BUTONU (type='primary' ile CSS hedeflendi) ---
        if st.button("🚀 START SPRINT", type="primary", use_container_width=True):
            q_df = conn.read(worksheet="Questions", ttl=0)
            if selected_mode != "All Domains (Mix)":
                target_id = [k for k, v in TOPIC_MAP.items() if v == selected_mode][0]
                q_df = q_df[q_df['topic_id'].astype(str).str.split('.').str[0] == target_id]
            
            if q_df.empty:
                st.error("No intelligence data found for this domain.")
            else:
                sample_n = min(len(q_df), 25)
                st.session_state.smart_list = q_df.sample(n=sample_n).reset_index(drop=True)
                st.session_state.q_idx = 0; st.session_state.start_time = time.time()
                st.session_state.is_sprint_active = True; st.session_state.view = 'Study'; st.rerun()
    
    st.write("---")
    if st.button("📊 Analytics Dashboard"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Access"): st.session_state.view = 'Admin'

# --- 6. STUDY VIEW ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    ph = st.empty()
    rem = max(0, int(600 - (time.time() - st.session_state.start_time)))
    if rem <= 0: st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    topic_name = TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General Domain')
    
    st.markdown(f"""
    <div class="q-card">
        <div style="color:#7f8c8d; font-size:14px; margin-bottom:10px;">📍 DOMAIN: {topic_name.upper()}</div>
        <h3 style="color:#2c3e50; margin:0;">{curr["content_text"]}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (c1 if i%2==0 else c2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']
                st.rerun()

    if st.session_state.feedback is not None:
        st.write("---")
        if st.session_state.feedback:
            st.success(f"✅ Correct! The answer is {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            
            sc1, sc2 = st.columns(2)
            if sc1.button("🎯 I knew it (Sure)"):
                save_stat(st.session_state.last_q_id, True, "Sure", "None")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if sc2.button("🎲 Lucky Guess"):
                save_stat(st.session_state.last_q_id, True, "Guessed", "None")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Incorrect. The correct answer is {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            
            ec1, ec2, ec3 = st.columns(3)
            if ec1.button("🧠 Knowledge Gap"):
                save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if ec2.button("👀 Careless Error"):
                save_stat(st.session_state.last_q_id, False, "None", "Attention")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if ec3.button("🤔 Logic Trap"):
                save_stat(st.session_state.last_q_id, False, "None", "Interpretation")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

# --- 7. ANALYTICS VIEW ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Performance Intelligence")
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0)
        questions = conn.read(worksheet="Questions", ttl=0)
        
        if not stats.empty and not questions.empty:
            # Data Prep
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            merged['is_correct_bool'] = merged['is_correct'].astype(str).str.upper().replace({'0':False,'1':True, '0.0':False, '1.0':True, 'FALSE':False, 'TRUE':True})
            
            # KPI Hesaplamaları
            total_solved = len(merged)
            accuracy = (merged['is_correct_bool'].sum() / total_solved * 100) if total_solved > 0 else 0
            
            # En güçlü domain
            domain_acc = merged.groupby('Domain')['is_correct_bool'].mean()
            strongest_domain = domain_acc.idxmax() if not domain_acc.empty else "N/A"

            # KPI Kartlarını Göster
            k1, k2, k3 = st.columns(3)
            k1.markdown(f'<div class="metric-container"><div class="metric-value">{total_solved}</div><div class="metric-label">Questions Solved</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="metric-container"><div class="metric-value">%{accuracy:.1f}</div><div class="metric-label">Global Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="metric-container"><div class="metric-value" style="font-size:18px; padding-top:8px;">{strongest_domain}</div><div class="metric-label">Strongest Domain</div></div>', unsafe_allow_html=True)
            
            st.write("---")

            # Grafikler
            c1, c2 = st.columns([1,2])
            merged['is_correct_str'] = merged['is_correct_bool'].apply(lambda x: 'TRUE' if x else 'FALSE')
            
            with c1:
                st.plotly_chart(px.pie(merged, names='is_correct_str', title="Accuracy Distribution", 
                                       color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
                
                err = merged[merged['is_correct_str'] == 'FALSE']
                if not err.empty:
                    st.plotly_chart(px.pie(err, names='error_reason', title="Error Root Causes", hole=0.5), use_container_width=True)
            
            with c2:
                perf = merged.groupby('Domain')['is_correct_str'].value_counts(normalize=True).unstack().fillna(0) * 100
                if 'TRUE' in perf.columns:
                    st.subheader("Domain Mastery Matrix (%)")
                    st.dataframe(perf[['TRUE']].rename(columns={'TRUE': 'Success %'}).style.format("{:.1f}").bar(color='#2ecc71'), use_container_width=True)
                
                st.plotly_chart(px.bar(merged, x='Domain', color='is_correct_str', barmode='group', title="Raw Volume Analysis"), use_container_width=True)
        else: st.info("Awaiting mission data. Initiate a sprint to gather intelligence.")
    except Exception as e: st.error(f"System Error: {str(e)}")

# --- 8. ADMIN VIEW ---
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        if st.text_input("Enter Clearance Code", type="password") == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        st.subheader("💾 Database Injection")
        up = st.file_uploader("Upload Question Data (.xlsx)", type=['xlsx'])
        if up and st.button("Execute Sync"):
            try:
                curr = conn.read(worksheet="Questions", ttl=0)
                new = pd.read_excel(up)
                conn.update(worksheet="Questions", data=pd.concat([curr, new], ignore_index=True))
                st.success("Data injection successful.")
            except Exception as e: st.error(f"Injection Failed: {e}")
