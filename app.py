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

# --- 2. CONFIGURATION & HIGH READABILITY STYLING ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; }
    
    /* --- BÜYÜK FONT AYARLARI --- */
    
    /* 1. Soru Kartı Metni */
    .q-card { 
        background: white; 
        padding: 3rem; /* Daha geniş boşluk */
        border-radius: 15px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        border-left: 8px solid #2c3e50; 
        margin-bottom: 30px; 
    }
    .q-card h3 {
        font-size: 28px !important; /* Soru metni büyütüldü */
        line-height: 1.6 !important;
        font-weight: 700 !important;
        color: #2c3e50 !important;
    }
    
    /* 2. Cevap Şıkkı Butonları */
    div.stButton > button {
        font-size: 20px !important; /* Şık yazıları büyütüldü */
        height: 4.5em !important; /* Buton yüksekliği artırıldı */
        font-weight: 600 !important;
    }
    
    /* 3. Özel Butonlar (Primary & Secondary) */
    div.stButton > button[kind="primary"] { 
        background: linear-gradient(45deg, #FF512F 0%, #DD2476 100%); 
        color: white; 
        border: none; 
        border-radius: 12px;
        font-size: 22px !important; /* Start butonları daha da büyük */
    }
    div.stButton > button[kind="secondary"] { 
        border-radius: 12px; 
        border: 2px dashed #f39c12; 
        color: #d35400; 
        background-color: #fdf2e9; 
        font-size: 18px !important;
    }
    
    /* Diğer Bileşenler */
    .profile-card { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); padding: 20px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
    .result-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; border-radius: 20px; color: white; text-align: center; margin: 20px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    .metric-container { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; border-bottom: 4px solid #3498db; height: 100%; display: flex; flex-direction: column; justify-content: center; }
    .metric-value { font-size: 26px; font-weight: bold; color: #2c3e50; }
    
    .timer-box { font-size: 26px; font-weight: 800; color: #e74c3c; text-align: center; background: #fadbd8; border-radius: 10px; padding: 15px; margin-bottom: 25px; }
    .progress-box { font-size: 24px; font-weight: 800; color: #2980b9; text-align: center; background: #d6eaf8; border-radius: 10px; padding: 15px; margin-bottom: 25px; }
    
    /* Açıklama Kutusu (Explanation) */
    .explanation-box { 
        background-color: #e8f6f3; 
        padding: 25px; 
        border-radius: 10px; 
        border-left: 6px solid #1abc9c; 
        margin-top: 20px; 
        color: #16a085; 
        font-size: 20px !important; /* Açıklama yazısı büyütüldü */
        line-height: 1.6;
    }
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

# --- 5. SIDEBAR ---
with st.sidebar:
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
    
    if st.session_state.is_sprint_active:
        msg = "⏳ Time Sprint" if st.session_state.sprint_type == 'Time' else "📝 Question Sprint"
        st.info(f"{msg} Active")
        if st.button("▶️ Return to Study"): st.session_state.view = 'Study'; st.rerun()
        if st.button("🛑 Terminate Session"): 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    else:
        st.subheader("📚 Configuration")
        domain_options = ["All Domains (Mix)"] + list(TOPIC_MAP.values())
        selected_mode = st.selectbox("Domain:", domain_options)
        
        st.write("---")
        st.write("🚀 **Start New Sprint:**")
        
        c1, c2 = st.columns(2)
        if c1.button("⏱️ 10 Min", type="primary", use_container_width=True):
            q_df = prepare_sprint_data(selected_mode)
            if not q_df.empty:
                st.session_state.smart_list = q_df.sample(n=min(len(q_df), 30)).reset_index(drop=True)
                st.session_state.q_idx = 0; st.session_state.start_time = time.time()
                st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
                st.session_state.mode = 'Normal'
                st.session_state.sprint_type = 'Time'; st.session_state.sprint_target = 600
                st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
                st.rerun()
            else: st.error("No questions.")

        if c2.button("⚡ 5 Min", type="primary", use_container_width=True):
            q_df = prepare_sprint_data(selected_mode)
            if not q_df.empty:
                st.session_state.smart_list = q_df.sample(n=min(len(q_df), 15)).reset_index(drop=True)
                st.session_state.q_idx = 0; st.session_state.start_time = time.time()
                st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
                st.session_state.mode = 'Normal'
                st.session_state.sprint_type = 'Time'; st.session_state.sprint_target = 300
                st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
                st.rerun()
            else: st.error("No questions.")
            
        if st.button("📝 Ask me 10 Questions", use_container_width=True):
            q_df = prepare_sprint_data(selected_mode)
            if not q_df.empty:
                count = min(len(q_df), 10)
                st.session_state.smart_list = q_df.sample(n=count).reset_index(drop=True)
                st.session_state.q_idx = 0; st.session_state.start_time = time.time()
                st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
                st.session_state.mode = 'Normal'
                st.session_state.sprint_type = 'Count'; st.session_state.sprint_target = count
                st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
                st.rerun()
            else: st.error("No questions.")

        st.write("")
        if st.button("↺ Review Mistakes", type="secondary", use_container_width=True):
            try:
                stats_df = conn.read(worksheet="User_Stats", ttl=0)
                stats_df['is_correct_bool'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':False,'1':True,'FALSE':False,'TRUE':True,'0.0':False})
                wrong_ids = stats_df[stats_df['is_correct_bool'] == False]['question_id'].unique()
                
                if len(wrong_ids) == 0: st.success("No errors!")
                else:
                    all_q = conn.read(worksheet="Questions", ttl=600)
                    clean_wrong_ids = [str(x).split('.')[0] for x in wrong_ids]
                    all_q['clean_id'] = all_q['id'].astype(str).str.split('.').str[0]
                    review_list = all_q[all_q['clean_id'].isin(clean_wrong_ids)]
                    
                    if not review_list.empty:
                        count = min(len(review_list), 20)
                        st.session_state.smart_list = review_list.sample(n=count).reset_index(drop=True)
                        st.session_state.q_idx = 0; st.session_state.start_time = time.time()
                        st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
                        st.session_state.mode = 'Review'
                        st.session_state.sprint_type = 'Count'; st.session_state.sprint_target = count
                        st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
                        st.rerun()
            except: st.error("Review Error")

    st.write("---")
    if st.button("📊 Analytics"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin"): st.session_state.view = 'Admin'

# --- 6. VIEWS CONTROL ---

# A. SCORE SUMMARY VIEW
if st.session_state.view == 'Score_Summary':
    score = st.session_state.sprint_score
    total = st.session_state.sprint_total_attempted
    accuracy = (score / total * 100) if total > 0 else 0
    
    st.markdown(f"""
    <div class="result-card">
        <h1>🏁 Sprint Complete!</h1>
        <div style="font-size: 80px; font-weight: bold; margin: 20px 0;">{score} / {total}</div>
        <h3>Accuracy: {accuracy:.1f}%</h3>
        <p>Great job! Every interaction makes you stronger.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    if col1.button("📊 Go to Dashboard", use_container_width=True):
        st.session_state.view = 'Analytics'; st.rerun()
    if col2.button("🔁 Start New Sprint", use_container_width=True):
        st.session_state.view = 'Main'; st.session_state.is_sprint_active = False; st.rerun()

# B. STUDY VIEW
elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    ph = st.empty()
    should_end = False
    
    if st.session_state.sprint_type == 'Time':
        rem = max(0, int(st.session_state.sprint_target - (time.time() - st.session_state.start_time)))
        if rem <= 0: should_end = True
        ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)
    else:
        current = st.session_state.q_idx + 1
        total = st.session_state.sprint_target
        if current > total: should_end = True
        else:
            ph.markdown(f'<div class="progress-box">📝 Question {current} / {total}</div>', unsafe_allow_html=True)

    if should_end:
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Score_Summary'
        st.rerun()

    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        topic_name = TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General')
        mode_badge = "🔴 REVIEW" if st.session_state.mode == 'Review' else f"📍 {topic_name.upper()}"
        
        st.markdown(f"""
        <div class="q-card">
            <div style="color:#7f8c8d; font-size:16px; margin-bottom:15px; font-weight:bold;">{mode_badge}</div>
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
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                
                sc1, sc2 = st.columns(2)
                if sc1.button("🎯 Sure"):
                    save_stat(st.session_state.last_q_id, True, "Sure", "None")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if sc2.button("🎲 Guess"):
                    save_stat(st.session_state.last_q_id, True, "Guessed", "None")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Wrong. Correct: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                
                ec1, ec2, ec3 = st.columns(3)
                if ec1.button("🧠 Knowledge"):
                    save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if ec2.button("👀 Attention"):
                    save_stat(st.session_state.last_q_id, False, "None", "Attention")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if ec3.button("🤔 Logic"):
                    save_stat(st.session_state.last_q_id, False, "None", "Interpretation")
                    st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
    else:
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

# C. ANALYTICS VIEW
elif st.session_state.view == 'Analytics':
    st.header("📊 Intelligence Dashboard")
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0) 
        questions = conn.read(worksheet="Questions", ttl=600)
        
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            merged['is_correct_bool'] = merged['is_correct'].astype(str).str.upper().replace({'0':False,'1':True, '0.0':False, '1.0':True, 'FALSE':False, 'TRUE':True})
            
            total_int = len(merged)
            acc = (merged['is_correct_bool'].sum() / total_int * 100) if total_int > 0 else 0
            unique_q = merged['qid'].nunique()
            total_pool = len(questions)
            cov = (unique_q / total_pool * 100) if total_pool > 0 else 0
            dom_acc = merged.groupby('Domain')['is_correct_bool'].mean()
            best_dom = dom_acc.idxmax() if not dom_acc.empty else "N/A"

            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f'<div class="metric-container"><div class="metric-value">{total_int}</div><div class="metric-label">Interactions</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="metric-container"><div class="metric-value">%{acc:.1f}</div><div class="metric-label">Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="metric-container"><div class="metric-value">{unique_q}/{total_pool}</div><div class="metric-label">Coverage ({cov:.1f}%)</div></div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="metric-container"><div class="metric-value" style="font-size:16px;">{best_dom}</div><div class="metric-label">Strongest Domain</div></div>', unsafe_allow_html=True)
            
            st.write("---")
            
            c1, c2 = st.columns([1,2])
            merged['res'] = merged['is_correct_bool'].apply(lambda x: 'TRUE' if x else 'FALSE')
            with c1:
                st.plotly_chart(px.pie(merged, names='res', title="Success Ratio", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
                errs = merged[merged['res']=='FALSE']
                if not errs.empty: st.plotly_chart(px.pie(errs, names='error_reason', title="Error Causes", hole=0.4), use_container_width=True)
            with c2:
                perf = merged.groupby('Domain')['res'].value_counts(normalize=True).unstack().fillna(0)*100
                if 'TRUE' in perf.columns:
                    st.subheader("Domain Mastery (%)")
                    st.dataframe(perf[['TRUE']].rename(columns={'TRUE':'%'}).style.format("{:.1f}").bar(color='#2ecc71'), use_container_width=True)
                st.plotly_chart(px.bar(merged, x='Domain', color='res', title="Volume Analysis"), use_container_width=True)
        else: st.info("No data.")
    except Exception as e: st.error(str(e))

# D. ADMIN VIEW
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
