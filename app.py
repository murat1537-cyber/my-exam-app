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

# --- 2. CONFIGURATION & MOBILE-FIRST CSS ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* GENEL AYARLAR */
    .stApp { background-color: #f8f9fa; }
    
    /* --- BUTON TASARIMLARI (MOBİL UYUMLU) --- */
    
    /* Standart Butonlar (Cevap Şıkları vb.) */
    div.stButton > button {
        width: 100%;
        border-radius: 12px !important;
        border: 1px solid #e0e0e0;
        padding: 10px 10px !important;
        font-size: 20px !important; /* Okunaklı boyut */
        font-weight: 500 !important;
        background-color: white;
        color: #2c3e50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        height: auto !important; /* İçeriğe göre uzasın */
        min-height: 70px; /* Mobilde parmakla basmak kolay olsun */
        white-space: normal !important; /* Uzun yazılar alt satıra geçsin */
        line-height: 1.4 !important;
    }
    
    div.stButton > button:hover {
        border-color: #3498db;
        color: #3498db;
        background-color: #fdfdfd;
    }

    /* Primary Butonlar (Başlatıcılar - Kırmızı/Turuncu) */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #FF6B6B 0%, #EE5253 100%);
        color: white !important;
        border: none;
        font-size: 22px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 10px rgba(238, 82, 83, 0.3);
        min-height: 80px;
    }
    
    /* Secondary Butonlar (Review - Turuncu/Sarı) */
    div.stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #f0932b 0%, #ffbe76 100%);
        color: white !important;
        border: none;
        font-size: 20px !important;
        font-weight: 700 !important;
        min-height: 80px;
    }

    /* --- KART VE METİN TASARIMLARI --- */
    
    /* Soru Kartı */
    .q-card { 
        background: white; 
        padding: 25px; 
        border-radius: 16px; 
        box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
        border-top: 6px solid #2c3e50; 
        margin-bottom: 25px; 
    }
    .q-card h3 {
        font-size: 24px !important; /* Mobilde taşmayacak ideal boyut */
        line-height: 1.5 !important;
        color: #2d3436 !important;
        font-weight: 700 !important;
    }
    
    /* Profil Kartı (Sidebar) */
    .profile-card { 
        background: white; 
        padding: 15px; 
        border-radius: 12px; 
        text-align: center; 
        border: 1px solid #eee;
        margin-bottom: 20px;
    }
    
    /* Sayaçlar */
    .timer-box { font-size: 22px; font-weight: bold; color: #e74c3c; text-align: center; background: #fff5f5; border-radius: 8px; padding: 10px; margin-bottom: 15px; border: 1px solid #feb2b2; }
    
    /* Açıklama Kutusu */
    .explanation-box { background-color: #e3fcf7; padding: 15px; border-radius: 10px; border-left: 5px solid #00b894; margin-top: 15px; color: #006266; font-size: 18px !important; }
    
    /* Dashboard Kartları */
    .metric-card { background: white; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; border-bottom: 3px solid #74b9ff; }
    .metric-num { font-size: 28px; font-weight: 800; color: #2c3e50; }
    .metric-lbl { font-size: 14px; text-transform: uppercase; color: #636e72; margin-top: 5px; }

    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

defaults = {
    'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None,
    'start_time': None, 'admin_auth': False, 'is_sprint_active': False,
    'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600,
    'sprint_score': 0, 'sprint_total_attempted': 0
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

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
    if df.empty: return "Novice", 0
    count = len(df)
    if count < 10: return "🟢 Novice", count
    elif count < 50: return "🔵 Junior Analyst", count
    elif count < 100: return "🟣 Security Architect", count
    else: return "👑 CISO Master", count

def prepare_sprint_data(selected_domain):
    q_df = conn.read(worksheet="Questions", ttl=600)
    if selected_domain != "All Domains (Mix)":
        target_id = [k for k, v in TOPIC_MAP.items() if v == selected_domain][0]
        q_df = q_df[q_df['topic_id'].astype(str).str.split('.').str[0] == target_id]
    return q_df

def start_sprint(mode_type, target_val, domain):
    q_df = prepare_sprint_data(domain)
    if q_df.empty:
        st.error("No questions found for this domain.")
        return

    if mode_type == 'Time': 
        count = min(len(q_df), 40)
    else:
        count = min(len(q_df), target_val)

    st.session_state.smart_list = q_df.sample(n=count).reset_index(drop=True)
    st.session_state.q_idx = 0
    st.session_state.start_time = time.time()
    st.session_state.is_sprint_active = True
    st.session_state.view = 'Study'
    st.session_state.mode = 'Normal'
    st.session_state.sprint_type = mode_type
    st.session_state.sprint_target = target_val
    st.session_state.sprint_score = 0
    st.session_state.sprint_total_attempted = 0
    st.rerun()

def start_review_sprint():
    try:
        stats_df = conn.read(worksheet="User_Stats", ttl=0)
        # Fix: Convert mixed types to boolean safely
        stats_df['is_correct_bool'] = stats_df['is_correct'].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '1': True, '0': False, '1.0': True, '0.0': False})
        
        wrong_ids = stats_df[stats_df['is_correct_bool'] == False]['question_id'].unique()
        
        if len(wrong_ids) == 0:
            st.success("🎉 Clean sheet! No errors to review.")
            return

        all_q = conn.read(worksheet="Questions", ttl=600)
        clean_wrong_ids = [str(x).split('.')[0] for x in wrong_ids]
        all_q['clean_id'] = all_q['id'].astype(str).str.split('.').str[0]
        review_list = all_q[all_q['clean_id'].isin(clean_wrong_ids)]
        
        if review_list.empty:
            st.warning("Errors exist in logs but questions are missing from database.")
            return

        count = min(len(review_list), 20)
        st.session_state.smart_list = review_list.sample(n=count).reset_index(drop=True)
        st.session_state.q_idx = 0
        st.session_state.start_time = time.time()
        st.session_state.is_sprint_active = True
        st.session_state.view = 'Study'
        st.session_state.mode = 'Review'
        st.session_state.sprint_type = 'Count'
        st.session_state.sprint_target = count
        st.session_state.sprint_score = 0
        st.session_state.sprint_total_attempted = 0
        st.rerun()
    except Exception as e: st.error(f"Review Error: {e}")

# --- 5. SIDEBAR ---
with st.sidebar:
    try:
        stats_preview = conn.read(worksheet="User_Stats", ttl=60)
        rank, total_q = get_user_rank(stats_preview)
    except: rank, total_q = "Novice", 0
    
    st.markdown(f"""
    <div class="profile-card">
        <div style="font-size: 32px;">🛡️</div>
        <div style="font-weight:bold; font-size:18px;">Cyber Warrior</div>
        <div style="font-size:12px; opacity:0.8;">{rank}</div>
        <div style="font-size:12px; margin-top:5px;">Solved: {total_q}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("---")
    
    if st.button("🏠 Home / Lobby"): 
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Main'; st.rerun()
        
    if st.button("📊 Analytics"): 
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Analytics'; st.rerun()
        
    if st.button("🔑 Admin Panel"): 
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Admin'; st.rerun()

# --- 6. VIEWS ---

# A. MAIN VIEW (LOBBY)
if st.session_state.view == 'Main':
    st.title("🛡️ CISSP Mentor Pro")
    st.markdown("Ready to train? Select a mode to begin.")
    
    domain_options = ["All Domains (Mix)"] + list(TOPIC_MAP.values())
    selected_mode = st.selectbox("🎯 Target Domain:", domain_options)
    
    st.write("")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⏱️ 10 Min Sprint", type="primary", use_container_width=True):
            start_sprint('Time', 600, selected_mode)
    with c2:
        if st.button("⚡ 5 Min Blitz", type="primary", use_container_width=True):
            start_sprint('Time', 300, selected_mode)
            
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📝 10 Questions", type="primary", use_container_width=True):
            start_sprint('Count', 10, selected_mode)
    with c4:
        if st.button("↺ Review Errors", type="secondary", use_container_width=True):
            start_review_sprint()

# B. STUDY VIEW
elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    c_timer, c_exit = st.columns([3, 1])
    with c_timer:
        ph = st.empty()
    with c_exit:
        if st.button("Exit", key="exit_btn"):
            st.session_state.is_sprint_active = False
            st.session_state.view = 'Main'
            st.rerun()

    should_end = False
    if st.session_state.sprint_type == 'Time':
        rem = max(0, int(st.session_state.sprint_target - (time.time() - st.session_state.start_time)))
        if rem <= 0: should_end = True
        ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)
    else:
        current = st.session_state.q_idx + 1
        total = st.session_state.sprint_target
        if current > total: should_end = True
        ph.markdown(f'<div class="timer-box">Question {current} / {total}</div>', unsafe_allow_html=True)

    if should_end:
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Score_Summary'
        st.rerun()

    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        topic_name = TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General')
        mode_badge = "🔴 REVIEW MODE" if st.session_state.mode == 'Review' else f"📍 {topic_name.upper()}"
        
        st.markdown(f"""
        <div class="q-card">
            <div style="color:#7f8c8d; font-size:12px; margin-bottom:10px; font-weight:bold;">{mode_badge}</div>
            <h3>{curr["content_text"]}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
        
        for i, (code, col) in enumerate(opts):
            with (c1 if i%2==0 else c2):
                if st.button(f"{code}) {curr[col]}", use_container_width=True):
                    st.session_state.feedback = (code == curr['correct_option'])
                    st.session_state.last_q_id = curr['id']
                    if st.session_state.feedback: st.session_state.sprint_score += 1
                    st.session_state.sprint_total_attempted += 1
                    st.rerun()

        if st.session_state.feedback is not None:
            st.write("---")
            if st.session_state.feedback:
                st.success(f"✅ Correct! Answer: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                
                sc1, sc2 = st.columns(2)
                if sc1.button("🎯 Sure", use_container_width=True):
                    save_stat(st.session_state.last_q_id, True, "Sure", "None")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if sc2.button("🎲 Guess", use_container_width=True):
                    save_stat(st.session_state.last_q_id, True, "Guessed", "None")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Wrong. Correct: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                
                ec1, ec2, ec3 = st.columns(3)
                if ec1.button("🧠 Knowledge", use_container_width=True):
                    save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if ec2.button("👀 Attention", use_container_width=True):
                    save_stat(st.session_state.last_q_id, False, "None", "Attention")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if ec3.button("🤔 Logic", use_container_width=True):
                    save_stat(st.session_state.last_q_id, False, "None", "Interpretation")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
    else:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

# C. SCORE SUMMARY
elif st.session_state.view == 'Score_Summary':
    score = st.session_state.sprint_score
    total = st.session_state.sprint_total_attempted
    acc = (score / total * 100) if total > 0 else 0
    
    st.markdown(f"""
    <div style="text-align:center; padding: 40px; background:white; border-radius:20px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
        <h1 style="color:#2c3e50;">🏁 Sprint Finished!</h1>
        <div style="font-size: 60px; font-weight: 800; color:#3498db; margin: 20px 0;">{score} / {total}</div>
        <h3 style="color:#7f8c8d;">Accuracy: {acc:.1f}%</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("🏠 Return to Home", use_container_width=True):
        st.session_state.view = 'Main'; st.rerun()
    if c2.button("📊 View Analytics", use_container_width=True):
        st.session_state.view = 'Analytics'; st.rerun()

# D. ANALYTICS
elif st.session_state.view == 'Analytics':
    st.header("📊 Intelligence Dashboard")
    try:
        try: stats = conn.read(worksheet="User_Stats", ttl=0)
        except: stats = conn.read(worksheet="User_Stats", ttl=60)
        
        questions = conn.read(worksheet="Questions", ttl=600)
        
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            
            # --- CRITICAL TYPE FIX ---
            # Zorla sayısal değere (1/0) çevirme
            merged['is_correct_val'] = merged['is_correct'].astype(str).str.upper().map({
                'TRUE': 1, 'FALSE': 0, '1': 1, '0': 0, '1.0': 1, '0.0': 0
            }).fillna(0).astype(int)
            
            total_int = len(merged)
            # Sayısal toplam alma (Artık string değil, int)
            acc = (merged['is_correct_val'].sum() / total_int * 100) if total_int > 0 else 0
            
            unique_q = merged['qid'].nunique()
            cov = (unique_q / len(questions) * 100) if len(questions) > 0 else 0

            k1, k2, k3 = st.columns(3)
            k1.markdown(f'<div class="metric-card"><div class="metric-num">{total_int}</div><div class="metric-lbl">Interactions</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="metric-card"><div class="metric-num">%{acc:.1f}</div><div class="metric-lbl">Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="metric-card"><div class="metric-num">{unique_q}</div><div class="metric-lbl">Unique Qs ({cov:.1f}%)</div></div>', unsafe_allow_html=True)
            
            st.write("---")
            
            c1, c2 = st.columns([1,2])
            # Görselleştirme için String versiyonunu ayrıca oluştur
            merged['Result'] = merged['is_correct_val'].apply(lambda x: 'TRUE' if x == 1 else 'FALSE')
            
            with c1:
                st.plotly_chart(px.pie(merged, names='Result', title="Success Ratio", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
            with c2:
                # Value counts on String column works fine
                perf = merged.groupby('Domain')['Result'].value_counts(normalize=True).unstack().fillna(0)*100
                if 'TRUE' in perf.columns:
                    st.subheader("Domain Mastery (%)")
                    st.dataframe(perf[['TRUE']].rename(columns={'TRUE':'%'}).style.format("{:.1f}").bar(color='#2ecc71'), use_container_width=True)
        else: st.info("No data.")
    except Exception as e: st.error(f"Dashboard Error: {str(e)}")

# E. ADMIN
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        if st.text_input("Admin Code", type="password") == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        st.subheader("Data Sync")
        up = st.file_uploader("Questions (.xlsx)", type=['xlsx'])
        if up and st.button("Sync"):
            try:
                c = conn.read(worksheet="Questions", ttl=0)
                n = pd.read_excel(up)
                conn.update(worksheet="Questions", data=pd.concat([c, n], ignore_index=True))
                st.success("Synced.")
            except Exception as e: st.error(e)
