import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import pyotp
import qrcode
import io

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div.stButton > button { width: 100%; border-radius: 12px; border: 1px solid #e0e0e0; padding: 10px; font-size: 20px; font-weight: 500; background-color: white; color: #2c3e50; min-height: 70px; white-space: normal; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    div.stButton > button:hover { border-color: #3498db; color: #3498db; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B6B 0%, #EE5253 100%); color: white !important; border: none; font-size: 22px; font-weight: 700; min-height: 80px; box-shadow: 0 4px 10px rgba(238, 82, 83, 0.3); }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #f0932b 0%, #ffbe76 100%); color: white !important; border: none; font-size: 20px; font-weight: 700; min-height: 80px; }
    .q-card { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-top: 6px solid #2c3e50; margin-bottom: 25px; }
    .profile-card { background: white; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #eee; margin-bottom: 20px; }
    .metric-card { background: white; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; border-bottom: 3px solid #74b9ff; }
    .metric-num { font-size: 28px; font-weight: 800; color: #2c3e50; }
    .metric-lbl { font-size: 14px; text-transform: uppercase; color: #636e72; margin-top: 5px; }
    .login-container { max-width: 450px; margin: 30px auto; padding: 30px; background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
    .timer-box { font-size: 22px; font-weight: 800; color: #e74c3c; text-align: center; background: #fff5f5; border-radius: 8px; padding: 10px; margin-bottom: 15px; border: 1px solid #feb2b2; }
    .explanation-box { background-color: #e3fcf7; padding: 15px; border-radius: 10px; border-left: 5px solid #00b894; margin-top: 15px; color: #006266; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA MAPPING ---
TOPIC_MAP = {
    "1": "Security and Risk Management", "2": "Asset Security", "3": "Security Architecture and Engineering",
    "4": "Communication and Network Security", "5": "Identity and Access Management (IAM)",
    "6": "Security Assessment and Testing", "7": "Security Operations", "8": "Software Development Security"
}

# --- 3. STATE & CONN ---
conn = st.connection("gsheets", type=GSheetsConnection)
defaults = {'is_logged_in': False, 'current_user': None, 'login_step': 'credentials', 'temp_user_data': None, 'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None, 'start_time': None, 'admin_auth': False, 'is_sprint_active': False, 'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600, 'sprint_score': 0, 'sprint_total_attempted': 0, 'show_2fa_setup': False}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. FUNCTIONS ---
def get_users():
    try: return conn.read(worksheet="Users", ttl=0)
    except: return pd.DataFrame(columns=["username", "email", "password", "is_2fa_enabled", "gdpr_consent", "2fa_secret"])

def clean_bool(val):
    return str(val).strip().upper() in ['TRUE', '1', '1.0', 'YES', 'ON']

def register(u, e, p, g):
    users = get_users()
    if not users.empty:
        if u in users['username'].values: return False, "Username exists"
        if 'email' in users.columns and e in users['email'].values: return False, "Email used"
    new_user = pd.DataFrame([{"username": u, "email": e, "password": p, "is_2fa_enabled": "FALSE", "gdpr_consent": "TRUE" if g else "FALSE", "2fa_secret": ""}])
    conn.update(worksheet="Users", data=pd.concat([users, new_user], ignore_index=True))
    return True, "Created! Login now."

def verify_cred(u, p):
    users = get_users()
    if not users.empty:
        rec = users[users['username'] == u]
        if not rec.empty and str(rec.iloc[0]['password']) == str(p): return True, rec.iloc[0]
    return False, None

def set_2fa(u, sec, status):
    users = get_users()
    idx = users.index[users['username'] == u].tolist()
    if idx:
        users.at[idx[0], 'is_2fa_enabled'] = "TRUE" if status else "FALSE"
        users.at[idx[0], '2fa_secret'] = sec if status else ""
        conn.update(worksheet="Users", data=users)
        return True
    return False

def save_stat(qid, corr, conf, reason):
    try:
        ex = conn.read(worksheet="User_Stats", ttl=0)
        new = pd.DataFrame([{"user_id": st.session_state.current_user, "question_id": str(qid), "is_correct": "TRUE" if corr else "FALSE", "confidence_level": str(conf), "error_reason": str(reason), "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
        conn.update(worksheet="User_Stats", data=pd.concat([ex, new], ignore_index=True).dropna(how='all'))
    except: pass

def get_rank(df):
    if df.empty: return "Novice", 0
    c = len(df[df['user_id'] == st.session_state.current_user])
    if c < 10: return "🟢 Novice", c
    elif c < 50: return "🔵 Junior Analyst", c
    elif c < 100: return "🟣 Security Architect", c
    else: return "👑 CISO Master", c

# --- 5. LOGIN LOGIC ---
if not st.session_state.is_logged_in:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown('<div class="login-container"><h2 style="text-align:center;">🛡️ CISSP Portal</h2>', unsafe_allow_html=True)
        t1, t2 = st.tabs(["Login", "Sign Up"])
        with t1:
            if st.session_state.login_step == 'credentials':
                u = st.text_input("Username", key="lu"); p = st.text_input("Password", type="password", key="lp")
                if st.button("Login", type="primary"):
                    valid, data = verify_cred(u, p)
                    if valid:
                        if clean_bool(data.get('is_2fa_enabled', 'FALSE')):
                            st.session_state.login_step = '2fa'; st.session_state.temp_user_data = data; st.rerun()
                        else: st.session_state.is_logged_in = True; st.session_state.current_user = u; st.rerun()
                    else: st.error("Invalid credentials")
            elif st.session_state.login_step == '2fa':
                st.info("🔐 2FA Code Required")
                otp = st.text_input("Code", max_chars=6)
                if st.button("Verify", type="primary"):
                    sec = st.session_state.temp_user_data.get('2fa_secret', '')
                    if sec and pyotp.TOTP(sec).verify(otp):
                        st.session_state.is_logged_in = True; st.session_state.current_user = st.session_state.temp_user_data['username']; st.session_state.login_step = 'credentials'; st.rerun()
                    else: st.error("Invalid Code")
        with t2:
            su = st.text_input("User", key="su"); se = st.text_input("Email", key="se"); sp = st.text_input("Pass", type="password", key="sp"); sg = st.checkbox("GDPR Consent", key="sg")
            if st.button("Create Account", type="secondary"):
                if su and sp and se and sg:
                    suc, msg = register(su, se, sp, sg)
                    if suc: st.success(msg)
                    else: st.error(msg)
                else: st.warning("All fields required")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 6. APP LOGIC ---
def prep_data(dom):
    q = conn.read(worksheet="Questions", ttl=600)
    if dom != "All Domains (Mix)":
        tid = [k for k, v in TOPIC_MAP.items() if v == dom][0]
        q = q[q['topic_id'].astype(str).str.split('.').str[0] == tid]
    return q

with st.sidebar:
    try: stats_p = conn.read(worksheet="User_Stats", ttl=60); rank, total_q = get_rank(stats_p)
    except: rank, total_q = "Novice", 0
    st.markdown(f"""<div class="profile-card"><div style="font-size:32px;">🛡️</div><b>{st.session_state.current_user}</b><br><small>{rank}</small><br><small>Solved: {total_q}</small></div>""", unsafe_allow_html=True)
    if st.button("🏠 Home"): st.session_state.view = 'Main'; st.session_state.show_2fa_setup = False; st.rerun()
    if st.button("📊 Analytics"): st.session_state.view = 'Analytics'; st.session_state.show_2fa_setup = False; st.rerun()
    if st.button("🔐 2FA Settings"): st.session_state.view = 'Main'; st.session_state.show_2fa_setup = True; st.rerun()
    if st.button("🚪 Logout"): st.session_state.is_logged_in = False; st.session_state.current_user = None; st.rerun()

if st.session_state.view == 'Main':
    st.title("🛡️ CISSP Mentor Pro")
    if st.session_state.show_2fa_setup:
        st.markdown("### 🔐 2FA Setup")
        u_row = get_users(); u_row = u_row[u_row['username'] == st.session_state.current_user].iloc[0]
        if clean_bool(u_row.get('is_2fa_enabled', 'FALSE')):
            st.success("✅ Enabled"); 
            if st.button("Disable"): set_2fa(st.session_state.current_user, "", False); st.rerun()
        else:
            if 'temp_sec' not in st.session_state: st.session_state.temp_sec = pyotp.random_base32()
            sec = st.session_state.temp_sec
            uri = pyotp.TOTP(sec).provisioning_uri(name=st.session_state.current_user, issuer_name="CISSP Mentor")
            img = io.BytesIO(); qrcode.make(uri).save(img, format='PNG')
            c1, c2 = st.columns([1,2]); c1.image(img.getvalue(), width=200); c2.text(f"Key: {sec}")
            otp = c2.text_input("Verify Code"); 
            if c2.button("Enable"): 
                if pyotp.TOTP(sec).verify(otp): set_2fa(st.session_state.current_user, sec, True); del st.session_state.temp_sec; st.rerun()
                else: st.error("Invalid")
    else:
        dom = st.selectbox("Domain:", ["All Domains (Mix)"] + list(TOPIC_MAP.values()))
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        if c1.button("⏱️ 10 Min Sprint", type="primary"): 
            q = prep_data(dom)
            if not q.empty: st.session_state.smart_list = q.sample(n=min(len(q), 40)).reset_index(drop=True); st.session_state.start_time = time.time(); st.session_state.view = 'Study'; st.session_state.sprint_type = 'Time'; st.rerun()
        if c2.button("⚡ 5 Min Blitz", type="primary"):
            q = prep_data(dom)
            if not q.empty: st.session_state.smart_list = q.sample(n=min(len(q), 20)).reset_index(drop=True); st.session_state.start_time = time.time(); st.session_state.view = 'Study'; st.session_state.sprint_type = 'Time'; st.rerun()
        if c3.button("📝 10 Questions", type="primary"):
            q = prep_data(dom)
            if not q.empty: st.session_state.smart_list = q.sample(n=min(len(q), 10)).reset_index(drop=True); st.session_state.start_time = time.time(); st.session_state.view = 'Study'; st.session_state.sprint_type = 'Count'; st.session_state.sprint_target = 10; st.rerun()
        if c4.button("↺ Review Errors", type="secondary"):
            st_df = conn.read(worksheet="User_Stats", ttl=0); st_df = st_df[st_df['user_id'] == st.session_state.current_user]
            w_ids = st_df[st_df['is_correct'].apply(clean_bool) == False]['question_id'].unique()
            if len(w_ids) > 0:
                aq = conn.read(worksheet="Questions", ttl=600); aq['cid'] = aq['id'].astype(str).str.split('.').str[0]
                rl = aq[aq['cid'].isin([str(x).split('.')[0] for x in w_ids])]
                if not rl.empty: st.session_state.smart_list = rl.sample(n=min(len(rl), 20)).reset_index(drop=True); st.session_state.start_time = time.time(); st.session_state.view = 'Study'; st.session_state.mode = 'Review'; st.rerun()

elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    c1, c2 = st.columns([3,1]); c1.empty(); 
    if c2.button("Exit"): st.session_state.view = 'Main'; st.rerun()
    
    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        for i, (k, col) in enumerate([('A','option_a'), ('B','option_b'), ('C','option_c'), ('D','option_d')]):
            with (c1 if i%2==0 else c2):
                if st.button(f"{k}) {curr[col]}"):
                    st.session_state.feedback = (k == curr['correct_option']); st.session_state.last_q_id = curr['id']; st.rerun()
        if st.session_state.feedback is not None:
            if st.session_state.feedback: st.success("Correct!"); st.session_state.sprint_score += 1
            else: st.error(f"Wrong. Answer: {curr['correct_option']}")
            st.markdown(f'<div class="explanation-box">{curr["explanation"]}</div>', unsafe_allow_html=True)
            if st.button("Next Question"):
                save_stat(st.session_state.last_q_id, st.session_state.feedback, "Normal", "None")
                st.session_state.q_idx += 1; st.session_state.feedback = None; st.session_state.sprint_total_attempted += 1; st.rerun()
    else: st.session_state.view = 'Main'; st.rerun()

elif st.session_state.view == 'Analytics':
    st.header("📊 Dashboard")
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0); stats = stats[stats['user_id'] == st.session_state.current_user]
        qs = conn.read(worksheet="Questions", ttl=600)
        if not stats.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]; qs['qid'] = qs['id'].astype(str).str.split('.').str[0]
            m = pd.merge(stats, qs[['qid', 'topic_id']], on='qid'); m['Correct'] = m['is_correct'].apply(clean_bool)
            c1, c2 = st.columns(2); c1.metric("Solved", len(m)); c2.metric("Accuracy", f"{(m['Correct'].sum()/len(m)*100):.1f}%")
            st.plotly_chart(px.pie(m, names='Correct', title="Success Rate"))
        else: st.info("No data")
    except: st.error("Error loading stats")
