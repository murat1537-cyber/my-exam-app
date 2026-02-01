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

# --- 2. CONFIGURATION & HIGH READABILITY CSS ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* GENEL ARKA PLAN: Gözü yormayan yumuşak gri */
    .stApp { background-color: #f8f9fa; }
    
    /* --- 1. SEÇENEK BUTONLARI (VARSAYILAN BUTONLAR) --- */
    /* A, B, C, D şıkları artık birer "Kart" gibi görünecek */
    div.stButton > button {
        width: 100%; 
        border-radius: 12px !important; 
        border: 2px solid #e9ecef !important; /* İnce gri çerçeve */
        padding: 16px 24px !important; /* Geniş iç boşluk */
        font-size: 20px !important; /* OKUNABİLİR BÜYÜK FONT */
        font-weight: 500 !important;
        background-color: #ffffff !important; /* Bembeyaz zemin */
        color: #212529 !important; /* Koyu antrasit yazı (Maksimum kontrast) */
        min-height: 85px; /* Yükseklik artırıldı */
        white-space: normal !important; /* Uzun yazılar alt satıra geçsin */
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); /* Hafif gölge */
        text-align: left !important; /* Sola hizalı metin okumayı kolaylaştırır */
        line-height: 1.5 !important;
        transition: all 0.2s ease-in-out;
    }
    
    /* Üzerine gelince (Hover) */
    div.stButton > button:hover { 
        border-color: #3498db !important; 
        background-color: #f1f8ff !important; /* Çok açık mavi */
        color: #2980b9 !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
    }
    
    /* --- 2. AKSİYON BUTONLARI (Primary) --- */
    /* Login, Start, Next gibi ana butonlar renkli ve ortalı kalacak */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%) !important;
        color: white !important; 
        border: none !important;
        text-align: center !important; /* Aksiyon butonları ortalı olsun */
        font-weight: 700 !important;
        font-size: 22px !important;
    }
    
    /* --- 3. İKİNCİL BUTONLAR (Secondary - Prev/Exit gibi) --- */
    /* Bunlar da dikkat çeksin ama şıklar kadar büyük olmasın */
    div.stButton > button[kind="secondary"] {
        background-color: #e9ecef !important;
        color: #495057 !important;
        border: 1px solid #ced4da !important;
        text-align: center !important;
        font-size: 18px !important;
    }

    /* KART VE METİN DÜZENLEMELERİ */
    .q-card { 
        background: white; 
        padding: 40px; 
        border-radius: 16px; 
        box-shadow: 0 8px 30px rgba(0,0,0,0.06); 
        border-top: 8px solid #2c3e50; 
        margin-bottom: 30px; 
    }
    .q-card h3 { 
        font-size: 26px !important; /* Soru metni boyutu */
        line-height: 1.6 !important; 
        color: #212529 !important; 
        font-weight: 700 !important; 
    }
    
    .profile-card { background: white; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #eee; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    
    .login-wrapper {
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.08); border: 1px solid #f0f0f0;
        text-align: center; margin-top: 50px;
    }
    .login-title { font-size: 32px; font-weight: 800; color: #2c3e50; margin-bottom: 10px; }
    
    .explanation-box { 
        background-color: #d1e7dd; /* Pastel yeşil */
        padding: 25px; 
        border-radius: 12px; 
        border-left: 6px solid #198754; 
        margin-top: 25px; 
        color: #0f5132; 
        font-size: 18px !important; 
        line-height: 1.6;
    }
    
    /* Geri sayım sayacı */
    .timer-box { font-size: 22px; font-weight: 800; color: #dc3545; text-align: center; background: white; border-radius: 10px; padding: 15px; margin-bottom: 20px; border: 2px solid #f8d7da; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

defaults = {
    'is_logged_in': False, 'current_user': None, 'user_role': 'User',
    'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None,
    'start_time': None, 'admin_auth': False, 'is_sprint_active': False,
    'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600,
    'sprint_score': 0, 'sprint_total_attempted': 0
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. AUTH HELPER FUNCTIONS ---
def get_all_users():
    try: return conn.read(worksheet="Users", ttl=0)
    except: return pd.DataFrame(columns=["username", "email", "password", "is_2fa_enabled", "gdpr_consent", "role"])

def clean_boolean(val):
    return str(val).strip().upper() in ['TRUE', '1', '1.0', 'YES', 'ON']

def register_new_user(username, email, password, gdpr):
    users = get_all_users()
    username = username.strip()
    if not users.empty:
        if username in users['username'].astype(str).str.strip().values: return False, "Username exists!"
    
    new_user = pd.DataFrame([{
        "username": username, "email": email, "password": str(password).strip(),
        "is_2fa_enabled": "FALSE", "gdpr_consent": "TRUE" if gdpr else "FALSE",
        "role": "User"
    }])
    updated_users = pd.concat([users, new_user], ignore_index=True)
    conn.update(worksheet="Users", data=updated_users)
    return True, "Account created successfully!"

def verify_login(username, password):
    users = get_all_users()
    if users.empty: return False, None
    
    input_user = str(username).strip()
    input_pass = str(password).strip()
    users['username_clean'] = users['username'].astype(str).str.strip()
    user_record = users[users['username_clean'] == input_user]
    
    if not user_record.empty:
        stored_pass = str(user_record.iloc[0]['password']).strip()
        if stored_pass.endswith('.0'): stored_pass = stored_pass[:-2]
        
        if stored_pass == input_pass:
            role = user_record.iloc[0].get('role', 'User')
            if pd.isna(role) or str(role).strip() == '': role = 'User'
            return True, str(role).strip()
    return False, None

# --- 5. LOGIN FLOW ---
if not st.session_state.is_logged_in:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("""<div class="login-wrapper"><div style="font-size: 60px;">🛡️</div><div class="login-title">CISSP Mentor Pro</div><div style="color:#6c757d; margin-bottom:30px;">Your AI-Powered Certification Partner</div></div>""", unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["🔑 LOGIN", "📝 SIGN UP"])
        
        with tab_login:
            st.write("")
            with st.form("login_form"):
                st.markdown("##### Welcome Back")
                l_u = st.text_input("Username", placeholder="Enter username")
                l_p = st.text_input("Password", type="password", placeholder="Enter password")
                if st.form_submit_button("🚀 Login Dashboard", type="primary", use_container_width=True):
                    success, role = verify_login(l_u, l_p)
                    if success:
                        st.session_state.is_logged_in = True
                        st.session_state.current_user = l_u.strip()
                        st.session_state.user_role = role
                        st.session_state.view = 'Main' 
                        st.rerun()
                    else: st.error("❌ Incorrect username or password.")

        with tab_signup:
            st.write("")
            with st.form("signup_form"):
                st.markdown("##### Create New Account")
                s_u = st.text_input("Username", placeholder="Choose username")
                s_e = st.text_input("Email", placeholder="name@example.com")
                s_p = st.text_input("Password", type="password", placeholder="Create password")
                s_g = st.checkbox("I agree to data processing (GDPR).")
                if st.form_submit_button("✨ Create Account", type="secondary", use_container_width=True):
                    if s_u and s_p and s_e and s_g:
                        suc, msg = register_new_user(s_u, s_e, s_p, s_g)
                        if suc: st.success(f"✅ {msg}"); time.sleep(2); st.rerun()
                        else: st.error(f"⚠️ {msg}")
                    else: st.warning("Please fill all fields.")
    st.stop()

# ==========================================
# ANA UYGULAMA
# ==========================================

def save_stat(q_id, correct, confidence, reason):
    try:
        existing_df = conn.read(worksheet="User_Stats", ttl=0)
        new_row = pd.DataFrame([{
            "user_id": st.session_state.current_user,
            "question_id": str(q_id),
            "is_correct": "TRUE" if correct else "FALSE",
            "confidence_level": str(confidence), "error_reason": str(reason),
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).dropna(how='all')
        conn.update(worksheet="User_Stats", data=updated_df)
    except: pass 

def get_user_rank(df):
    if df.empty: return "Novice", 0
    u_df = df[df['user_id'] == st.session_state.current_user]
    c = len(u_df)
    if c < 10: return "🟢 Novice", c
    elif c < 50: return "🔵 Junior Analyst", c
    elif c < 100: return "🟣 Security Architect", c
    else: return "👑 CISO Master", c

def prepare_sprint_data(dom):
    q = conn.read(worksheet="Questions", ttl=600)
    if dom != "All Domains (Mix)":
        tid = [k for k, v in TOPIC_MAP.items() if v == dom][0]
        q = q[q['topic_id'].astype(str).str.split('.').str[0] == tid]
    return q

def start_sprint(m_type, val, dom):
    q = prepare_sprint_data(dom)
    if q.empty: st.error("No questions found."); return
    c = min(len(q), 40) if m_type == 'Time' else min(len(q), val)
    st.session_state.smart_list = q.sample(n=c).reset_index(drop=True)
    st.session_state.q_idx = 0; st.session_state.start_time = time.time()
    st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
    st.session_state.mode = 'Normal'; st.session_state.sprint_type = m_type
    st.session_state.sprint_target = val; st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
    st.rerun()

def start_review():
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0)
        if stats.empty: st.success("No errors found!"); return
        stats = stats[stats['user_id'] == st.session_state.current_user]
        stats['is_correct_val'] = stats['is_correct'].apply(clean_boolean)
        wrong_ids = stats[stats['is_correct_val'] == 0]['question_id'].unique()
        if len(wrong_ids) == 0: st.success("🎉 No errors recorded! Great job."); return
        all_q = conn.read(worksheet="Questions", ttl=600)
        clean_ids = [str(x).split('.')[0] for x in wrong_ids]
        all_q['clean_id'] = all_q['id'].astype(str).str.split('.').str[0]
        r_list = all_q[all_q['clean_id'].isin(clean_ids)]
        if r_list.empty: st.warning("Questions missing."); return
        c = min(len(r_list), 20)
        st.session_state.smart_list = r_list.sample(n=c).reset_index(drop=True)
        st.session_state.q_idx = 0; st.session_state.start_time = time.time(); st.session_state.is_sprint_active = True; st.session_state.view = 'Study'; st.session_state.mode = 'Review'; st.session_state.sprint_type = 'Count'; st.session_state.sprint_target = c; st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0; st.rerun()
    except Exception as e: st.error(f"Error: {e}")

# --- SIDEBAR ---
with st.sidebar:
    try:
        stats_p = conn.read(worksheet="User_Stats", ttl=60)
        rank, total_q = get_user_rank(stats_p)
    except: rank, total_q = "Novice", 0
    
    role_badge = "👑 ADMIN" if st.session_state.user_role == 'Admin' else "USER"
    
    st.markdown(f"""
    <div class="profile-card">
        <div style="font-size: 40px; margin-bottom:10px;">🛡️</div>
        <div style="font-weight:800; font-size:22px; color:#2c3e50;">{st.session_state.current_user}</div>
        <div style="font-size:12px; color:white; background:#34495e; padding:4px 10px; border-radius:12px; display:inline-block; margin-bottom:5px;">{role_badge}</div>
        <div style="font-size:14px; color:#7f8c8d; margin-top:5px;">{rank}</div>
        <div style="background:#fff3cd; color:#856404; padding:5px 10px; border-radius:8px; font-weight:bold; font-size:13px; display:inline-block; margin-top:10px;">Total Solved: {total_q}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("---")
    
    if st.button("🏠 Home / Lobby", use_container_width=True, type="secondary"): st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()
    if st.button("📊 Analytics", use_container_width=True, type="secondary"): st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
    
    if st.session_state.user_role == 'Admin':
        if st.button("🔑 Admin Panel", use_container_width=True, type="primary"): 
            st.session_state.is_sprint_active = False
            st.session_state.view = 'Admin'
            st.rerun()
    
    st.write("")
    if st.button("🚪 Logout", use_container_width=True, type="secondary"): 
        st.session_state.is_logged_in = False; st.session_state.current_user = None; st.session_state.user_role = 'User'; st.session_state.view = 'Main'; st.rerun()

# --- VIEWS ---
if st.session_state.view == 'Main':
    st.title("🛡️ CISSP Mentor Pro")
    st.markdown(f"### Ready to train, **{st.session_state.current_user}**?")
    dom = st.selectbox("🎯 Target Domain:", ["All Domains (Mix)"] + list(TOPIC_MAP.values()))
    st.write("")
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("⏱️ 10 Min Sprint", type="primary"): start_sprint('Time', 600, dom)
    with c2: 
        if st.button("⚡ 5 Min Blitz", type="primary"): start_sprint('Time', 300, dom)
    c3, c4 = st.columns(2)
    with c3: 
        if st.button("📝 10 Questions", type="primary"): start_sprint('Count', 10, dom)
    with c4: 
        if st.button("↺ Review Errors", type="secondary"): start_review()

elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    c_back, c_tm, c_ex = st.columns([1, 2, 1])
    with c_back:
        if st.session_state.q_idx > 0:
            if st.button("⬅️ Prev", use_container_width=True, type="secondary"):
                st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()
    with c_tm: ph = st.empty()
    with c_ex:
        if st.button("Exit ❌", use_container_width=True, type="secondary"): 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()

    end = False
    if st.session_state.sprint_type == 'Time':
        rem = max(0, int(st.session_state.sprint_target - (time.time() - st.session_state.start_time)))
        if rem <= 0: end = True
        ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)
    else:
        cur = st.session_state.q_idx + 1; tot = st.session_state.sprint_target
        if cur > tot: end = True
        ph.markdown(f'<div class="timer-box">Question {cur} / {tot}</div>', unsafe_allow_html=True)

    if end: st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        tn = TOPIC_MAP.get(str(curr['topic_id']).split('.')[0], 'General')
        bdg = "🔴 REVIEW MODE" if st.session_state.mode == 'Review' else f"📍 {tn.upper()}"
        st.markdown(f"""
        <div class="q-card">
            <div style="color:#6c757d; font-size:14px; margin-bottom:15px; font-weight:600; letter-spacing:1px;">{bdg}</div>
            <h3>{curr["content_text"]}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
        for i, (cd, cl) in enumerate(opts):
            with (c1 if i%2==0 else c2):
                # BURASI KRİTİK: Butonları kart gibi yapıyoruz
                if st.button(f"{cd}) {curr[cl]}", use_container_width=True):
                    st.session_state.feedback = (cd == curr['correct_option'])
                    st.session_state.last_q_id = curr['id']
                    if st.session_state.feedback: st.session_state.sprint_score += 1
                    st.session_state.sprint_total_attempted += 1
                    st.rerun()
        if st.session_state.feedback is not None:
            st.write("---")
            if st.session_state.feedback:
                st.success(f"✅ Correct! Answer: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>💡 Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                sc1, sc2 = st.columns(2)
                # Next butonları belirgin (Primary) olsun
                if sc1.button("🎯 Sure (Next)", type="primary", use_container_width=True): save_stat(st.session_state.last_q_id, True, "Sure", "None"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if sc2.button("🎲 Guess (Next)", type="primary", use_container_width=True): save_stat(st.session_state.last_q_id, True, "Guessed", "None"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
            else:
                st.error(f"❌ Wrong. Correct: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>💡 Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                ec1, ec2, ec3 = st.columns(3)
                # Hata analizi butonları
                if ec1.button("🧠 Knowledge", type="primary", use_container_width=True): save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if ec2.button("👀 Attention", type="primary", use_container_width=True): save_stat(st.session_state.last_q_id, False, "None", "Attention"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if ec3.button("🤔 Logic", type="primary", use_container_width=True): save_stat(st.session_state.last_q_id, False, "None", "Interpretation"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
    else: st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

elif st.session_state.view == 'Score_Summary':
    sc = st.session_state.sprint_score; tot = st.session_state.sprint_total_attempted
    ac = (sc / tot * 100) if tot > 0 else 0
    st.markdown(f"""<div style="text-align:center; padding: 60px; background:white; border-radius:20px; box-shadow:0 10px 30px rgba(0,0,0,0.1); margin-top:20px;"><h1 style="color:#2c3e50; font-size: 45px;">🏁 Sprint Finished!</h1><div style="font-size: 90px; font-weight: 800; color:#0d6efd; margin: 20px 0;">{sc} / {tot}</div><h3 style="color:#6c757d; letter-spacing:2px;">ACCURACY: {ac:.1f}%</h3></div>""", unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("🏠 Home", use_container_width=True, type="primary"): st.session_state.view = 'Main'; st.rerun()
    if c2.button("📊 Analytics", use_container_width=True, type="secondary"): st.session_state.view = 'Analytics'; st.rerun()

elif st.session_state.view == 'Analytics':
    st.header("📊 Intelligence Dashboard")
    try:
        try: stats = conn.read(worksheet="User_Stats", ttl=0)
        except: stats = conn.read(worksheet="User_Stats", ttl=60)
        if not stats.empty: stats = stats[stats['user_id'] == st.session_state.current_user]
        questions = conn.read(worksheet="Questions", ttl=600)
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            merged['is_correct_val'] = merged['is_correct'].apply(clean_boolean)
            total_int = len(merged); acc = (merged['is_correct_val'].sum() / total_int * 100) if total_int > 0 else 0
            unique_q = merged['qid'].nunique(); cov = (unique_q / len(questions) * 100) if len(questions) > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.markdown(f'<div style="background:white; padding:20px; border-radius:12px; text-align:center; box-shadow:0 2px 5px rgba(0,0,0,0.05); border-bottom:4px solid #0d6efd;"><div style="font-size:28px; font-weight:800; color:#212529;">{total_int}</div><div style="font-size:12px; text-transform:uppercase; color:#6c757d;">Total Interactions</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div style="background:white; padding:20px; border-radius:12px; text-align:center; box-shadow:0 2px 5px rgba(0,0,0,0.05); border-bottom:4px solid #198754;"><div style="font-size:28px; font-weight:800; color:#212529;">%{acc:.1f}</div><div style="font-size:12px; text-transform:uppercase; color:#6c757d;">Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div style="background:white; padding:20px; border-radius:12px; text-align:center; box-shadow:0 2px 5px rgba(0,0,0,0.05); border-bottom:4px solid #fd7e14;"><div style="font-size:28px; font-weight:800; color:#212529;">{unique_q}</div><div style="font-size:12px; text-transform:uppercase; color:#6c757d;">Unique Qs ({cov:.1f}%)</div></div>', unsafe_allow_html=True)
            
            st.write("---")
            c1, c2 = st.columns([1,2])
            merged['Result'] = merged['is_correct_val'].apply(lambda x: 'TRUE' if x == 1 else 'FALSE')
            with c1: st.plotly_chart(px.pie(merged, names='Result', title="Success Ratio", color_discrete_map={'TRUE':'#198754','FALSE':'#dc3545'}), use_container_width=True)
            with c2: 
                perf = merged.groupby('Domain')['Result'].value_counts(normalize=True).unstack().fillna(0)*100
                if 'TRUE' in perf.columns: st.subheader("Domain Mastery (%)"); st.dataframe(perf[['TRUE']].rename(columns={'TRUE':'Success %'}).style.format("{:.1f}").bar(color='#198754'), use_container_width=True)
        else: st.info("No analytics data yet.")
    except Exception as e: st.error(str(e))

elif st.session_state.view == 'Admin':
    if st.session_state.user_role != 'Admin': st.session_state.view = 'Main'; st.rerun()
    st.subheader("💾 Database Injection (Admin Only)")
    up = st.file_uploader("Upload Question Data (.xlsx)", type=['xlsx'])
    if up and st.button("Execute Sync"):
        try:
            c = conn.read(worksheet="Questions", ttl=0); n = pd.read_excel(up)
            conn.update(worksheet="Questions", data=pd.concat([c, n], ignore_index=True)); st.success("Data injection successful.")
        except Exception as e: st.error(f"Injection Failed: {e}")
