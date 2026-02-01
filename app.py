import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import pyotp
import qrcode
import io

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

# --- 2. CONFIGURATION & MOBILE CSS ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    
    /* BUTONLAR */
    div.stButton > button {
        width: 100%; border-radius: 12px !important; border: 1px solid #e0e0e0;
        padding: 10px !important; font-size: 20px !important; font-weight: 500 !important;
        background-color: white; color: #2c3e50; min-height: 70px;
        white-space: normal !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div.stButton > button:hover { border-color: #3498db; color: #3498db; }
    
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #FF6B6B 0%, #EE5253 100%);
        color: white !important; border: none; font-size: 22px !important;
        font-weight: 700 !important; min-height: 80px;
        box-shadow: 0 4px 10px rgba(238, 82, 83, 0.3);
    }
    
    div.stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #f0932b 0%, #ffbe76 100%);
        color: white !important; border: none; font-size: 20px !important;
        font-weight: 700 !important; min-height: 80px;
    }

    /* KARTLAR */
    .q-card { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-top: 6px solid #2c3e50; margin-bottom: 25px; }
    .q-card h3 { font-size: 24px !important; line-height: 1.5 !important; color: #2d3436 !important; font-weight: 700 !important; }
    .profile-card { background: white; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #eee; margin-bottom: 20px; }
    .metric-card { background: white; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; border-bottom: 3px solid #74b9ff; }
    .metric-num { font-size: 28px; font-weight: 800; color: #2c3e50; }
    .metric-lbl { font-size: 14px; text-transform: uppercase; color: #636e72; margin-top: 5px; }
    
    /* LOGIN KUTUSU */
    .login-container { max-width: 450px; margin: 30px auto; padding: 30px; background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
    .timer-box { font-size: 22px; font-weight: 800; color: #e74c3c; text-align: center; background: #fff5f5; border-radius: 8px; padding: 10px; margin-bottom: 15px; border: 1px solid #feb2b2; }
    .explanation-box { background-color: #e3fcf7; padding: 15px; border-radius: 10px; border-left: 5px solid #00b894; margin-top: 15px; color: #006266; font-size: 18px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Session State Tanımları (2FA Durumları Eklendi)
defaults = {
    'is_logged_in': False, 'current_user': None,
    'login_step': 'credentials', # 'credentials' veya '2fa'
    'temp_user_data': None,      # 2FA doğrulaması sırasında geçici veri
    'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None,
    'start_time': None, 'admin_auth': False, 'is_sprint_active': False,
    'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600,
    'sprint_score': 0, 'sprint_total_attempted': 0,
    'show_2fa_setup': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. AUTH HELPER FUNCTIONS ---
def get_all_users():
    try:
        # Cache kullanmıyoruz (ttl=0) çünkü yeni kayıtları anlık görmeliyiz
        return conn.read(worksheet="Users", ttl=0)
    except:
        return pd.DataFrame(columns=["username", "email", "password", "is_2fa_enabled", "gdpr_consent", "2fa_secret"])

def clean_boolean(val):
    """Excel verisini güvenli boolean'a çevirir"""
    s = str(val).strip().upper()
    return True if s in ['TRUE', '1', '1.0', 'YES', 'ON'] else False

def register_new_user(username, email, password, gdpr):
    users = get_all_users()
    if not users.empty:
        if username in users['username'].values: return False, "Username already exists!"
        if 'email' in users.columns and email in users['email'].values: return False, "Email already registered!"
    
    # 2fa_secret sütunu eklendi
    new_user = pd.DataFrame([{
        "username": username, "email": email, "password": password,
        "is_2fa_enabled": "FALSE", "gdpr_consent": "TRUE" if gdpr else "FALSE",
        "2fa_secret": ""
    }])
    updated_users = pd.concat([users, new_user], ignore_index=True)
    conn.update(worksheet="Users", data=updated_users)
    return True, "Account created! Please login."

def verify_credentials(username, password):
    users = get_all_users()
    if not users.empty:
        user_record = users[users['username'] == username]
        if not user_record.empty and str(user_record.iloc[0]['password']) == str(password):
            return True, user_record.iloc[0]
    return False, None

def enable_2fa_for_user(username, secret):
    users = get_all_users()
    idx = users.index[users['username'] == username].tolist()
    if idx:
        users.at[idx[0], 'is_2fa_enabled'] = "TRUE"
        users.at[idx[0], '2fa_secret'] = secret
        conn.update(worksheet="Users", data=users)
        return True
    return False

def disable_2fa_for_user(username):
    users = get_all_users()
    idx = users.index[users['username'] == username].tolist()
    if idx:
        users.at[idx[0], 'is_2fa_enabled'] = "FALSE"
        users.at[idx[0], '2fa_secret'] = ""
        conn.update(worksheet="Users", data=users)
        return True
    return False

# --- 5. LOGIN FLOW (2FA ENTEGRE EDİLDİ) ---
if not st.session_state.is_logged_in:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown('<div class="login-container"><h2 style="text-align:center;">🛡️ CISSP Portal</h2>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])
        
        with tab1:
            if st.session_state.login_step == 'credentials':
                l_u = st.text_input("Username", key="l_u")
                l_p = st.text_input("Password", type="password", key="l_p")
                if st.button("Login", type="primary", key="btn_login"):
                    valid, u_data = verify_credentials(l_u, l_p)
                    if valid:
                        # 2FA Kontrolü
                        if clean_boolean(u_data.get('is_2fa_enabled', 'FALSE')):
                            st.session_state.login_step = '2fa'
                            st.session_state.temp_user_data = u_data
                            st.rerun()
                        else:
                            st.session_state.is_logged_in = True
                            st.session_state.current_user = l_u
                            st.rerun()
                    else: st.error("Invalid credentials.")
            
            elif st.session_state.login_step == '2fa':
                st.info("🔐 Enter 2FA Code")
                otp = st.text_input("Authenticator Code", max_chars=6)
                cb, cv = st.columns(2)
                with cb:
                    if st.button("Back"): st.session_state.login_step = 'credentials'; st.rerun()
                with cv:
                    if st.button("Verify", type="primary"):
                        sec = st.session_state.temp_user_data.get('2fa_secret', '')
                        if sec and pyotp.TOTP(sec).verify(otp):
                            st.session_state.is_logged_in = True
                            st.session_state.current_user = st.session_state.temp_user_data['username']
                            st.session_state.login_step = 'credentials'
                            st.rerun()
                        else: st.error("Invalid Code")

        with tab2:
            s_u = st.text_input("Username", key="s_u"); s_e = st.text_input("Email", key="s_e"); s_p = st.text_input("Password", type="password", key="s_p"); s_g = st.checkbox("GDPR Consent", key="s_g")
            if st.button("Register", type="secondary"):
                if s_u and s_p and s_e and s_g:
                    suc, msg = register_new_user(s_u, s_e, s_p, s_g)
                    if suc: st.success(msg)
                    else: st.error(msg)
                else: st.warning("All fields required.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# ANA UYGULAMA (Giriş Başarılı)
# ==========================================

# --- CORE FUNCTIONS ---
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
    # Kota hatasını önlemek için soruları 10 dk (600sn) önbellekte tutuyoruz
    q = conn.read(worksheet="Questions", ttl=600)
    if dom != "All Domains (Mix)":
        tid = [k for k, v in TOPIC_MAP.items() if v == dom][0]
        q = q[q['topic_id'].astype(str).str.split('.').str[0] == tid]
    return q

def start_sprint(m_type, val, dom):
    q = prepare_sprint_data(dom)
    if q.empty: st.error("No questions."); return
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
        stats = stats[stats['user_id'] == st.session_state.current_user]
        # Robust boolean cleaning for review mode too
        stats['is_correct_val'] = stats['is_correct'].apply(clean_boolean)
        wrong_ids = stats[stats['is_correct_val'] == 0]['question_id'].unique()
        if len(wrong_ids) == 0: st.success("🎉 No errors!"); return
        
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
    
    st.markdown(f"""<div class="profile-card"><div style="font-size: 32px;">🛡️</div><div style="font-weight:bold; font-size:18px;">{st.session_state.current_user}</div><div style="font-size:12px; opacity:0.8;">{rank}</div><div style="font-size:12px; margin-top:5px;">Solved: {total_q}</div></div>""", unsafe_allow_html=True)
    st.write("---")
    
    if st.button("🏠 Home"): st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.session_state.show_2fa_setup = False; st.rerun()
    if st.button("📊 Analytics"): st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.session_state.show_2fa_setup = False; st.rerun()
    
    # 2FA SETUP BUTTON
    if st.button("🔐 2FA Settings"):
        st.session_state.is_sprint_active = False
        st.session_state.view = 'Main'
        st.session_state.show_2fa_setup = True
        st.rerun()

    if st.button("🚪 Logout"): 
        st.session_state.is_logged_in = False; st.session_state.current_user = None; 
        st.session_state.login_step = 'credentials'; st.rerun()

# --- VIEWS ---
if st.session_state.view == 'Main':
    st.title("🛡️ CISSP Mentor Pro")
    
    # 2FA SETUP UI (Eğer butona basıldıysa)
    if st.session_state.get('show_2fa_setup', False):
        st.markdown("### 🔐 Two-Factor Setup")
        users_df = get_all_users()
        u_row = users_df[users_df['username'] == st.session_state.current_user].iloc[0]
        
        if clean_boolean(u_row.get('is_2fa_enabled', 'FALSE')):
            st.success("✅ 2FA is currently ENABLED.")
            if st.button("Disable 2FA", type="secondary"):
                if disable_2fa_for_user(st.session_state.current_user): st.success("Disabled."); time.sleep(1); st.rerun()
        else:
            st.warning("⚠️ 2FA Disabled.")
            if 'temp_secret' not in st.session_state: st.session_state.temp_secret = pyotp.random_base32()
            sec = st.session_state.temp_secret
            
            # QR Kod Oluşturma
            uri = pyotp.TOTP(sec).provisioning_uri(name=st.session_state.current_user, issuer_name="CISSP Mentor")
            img = io.BytesIO(); qrcode.make(uri).save(img, format='PNG')
            
            c_qr, c_vf = st.columns([1, 2])
            with c_qr: st.image(img.getvalue(), width=200)
            with c_vf:
                st.text(f"Secret: {sec}")
                otp = st.text_input("Verify Code", key="s_otp")
                if st.button("Enable"):
                    if pyotp.TOTP(sec).verify(otp):
                        if enable_2fa_for_user(st.session_state.current_user, sec): st.success("Enabled!"); del st.session_state.temp_secret; time.sleep(1); st.rerun()
                    else: st.error("Invalid Code")
        st.write("---")

    if not st.session_state.get('show_2fa_setup', False):
        st.markdown(f"Welcome, **{st.session_state.current_user}**!")
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
    c_tm, c_ex = st.columns([3, 1])
    with c_tm: ph = st.empty()
    with c_ex:
        if st.button("Exit"): st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()

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
        st.markdown(f"""<div class="q-card"><div style="color:#7f8c8d; font-size:12px; margin-bottom:10px; font-weight:bold;">{bdg}</div><h3>{curr["content_text"]}</h3></div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
        for i, (cd, cl) in enumerate(opts):
            with (c1 if i%2==0 else c2):
                if st.button(f"{cd}) {curr[cl]}"):
                    st.session_state.feedback = (cd == curr['correct_option'])
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
                if sc1.button("🎯 Sure"): save_stat(st.session_state.last_q_id, True, "Sure", "None"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if sc2.button("🎲 Guess"): save_stat(st.session_state.last_q_id, True, "Guessed", "None"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
            else:
                st.error(f"❌ Wrong. Correct: {curr['correct_option']}")
                if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>Insight:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
                ec1, ec2, ec3 = st.columns(3)
                if ec1.button("🧠 Knowledge"): save_stat(st.session_state.last_q_id, False, "None", "Knowledge Gap"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if ec2.button("👀 Attention"): save_stat(st.session_state.last_q_id, False, "None", "Attention"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if ec3.button("🤔 Logic"): save_stat(st.session_state.last_q_id, False, "None", "Interpretation"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
    else: st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

elif st.session_state.view == 'Score_Summary':
    sc = st.session_state.sprint_score; tot = st.session_state.sprint_total_attempted
    ac = (sc / tot * 100) if tot > 0 else 0
    st.markdown(f"""<div style="text-align:center; padding: 40px; background:white; border-radius:20px; box-shadow:0 4px 15px rgba(0,0,0,0.1);"><h1 style="color:#2c3e50;">🏁 Sprint Finished!</h1><div style="font-size: 60px; font-weight: 800; color:#3498db; margin: 20px 0;">{sc} / {tot}</div><h3 style="color:#7f8c8d;">Accuracy: {ac:.1f}%</h3></div>""", unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("🏠 Home"): st.session_state.view = 'Main'; st.rerun()
    if c2.button("📊 Analytics"): st.session_state.view = 'Analytics'; st.rerun()

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
            
            # Veri Temizliği: clean_boolean ile hataları önle
            merged['is_correct_val'] = merged['is_correct'].apply(clean_boolean)
            
            total_int = len(merged); acc = (merged['is_correct_val'].sum() / total_int * 100) if total_int > 0 else 0
            unique_q = merged['qid'].nunique(); cov = (unique_q / len(questions) * 100) if len(questions) > 0 else 0
            k1, k2, k3 = st.columns(3)
            k1.markdown(f'<div class="metric-card"><div class="metric-num">{total_int}</div><div class="metric-lbl">Interactions</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="metric-card"><div class="metric-num">%{acc:.1f}</div><div class="metric-lbl">Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="metric-card"><div class="metric-num">{unique_q}</div><div class="metric-lbl">Unique Qs ({cov:.1f}%)</div></div>', unsafe_allow_html=True)
            st.write("---")
            c1, c2 = st.columns([1,2])
            merged['Result'] = merged['is_correct_val'].apply(lambda x: 'TRUE' if x == 1 else 'FALSE')
            with c1: st.plotly_chart(px.pie(merged, names='Result', title="Success Ratio", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}), use_container_width=True)
            with c2: perf = merged.groupby('Domain')['Result'].value_counts(normalize=True).unstack().fillna(0)*100; st.dataframe(perf)
        else: st.info("No data yet.")
    except Exception as e: st.error(str(e))

elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        if st.text_input("Admin Code", type="password") == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        st.subheader("Data Sync")
        up = st.file_uploader("Questions (.xlsx)", type=['xlsx'])
        if up and st.button("Sync"):
            c = conn.read(worksheet="Questions", ttl=0); n = pd.read_excel(up)
            conn.update(worksheet="Questions", data=pd.concat([c, n], ignore_index=True)); st.success("Synced.")
