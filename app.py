import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import hashlib
import secrets
import re
import urllib.parse
import html

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

# --- 2. CONFIGURATION & CSS ---
st.set_page_config(page_title="CISSP AI Mentor", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; }
    div.stButton > button {
        width: 100%; border-radius: 12px !important; border: 2px solid #d1d8e0 !important;
        padding: 15px 20px !important; font-size: 20px !important; font-weight: 600 !important;
        background-color: #ffffff !important; color: #000000 !important;
        min-height: 85px; white-space: normal !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: left !important; transition: all 0.2s ease; line-height: 1.5 !important;
    }
    div.stButton > button:hover { border-color: #3498db !important; background-color: #f0f8ff !important; color: #000000 !important; transform: translateY(-2px); }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #FF6B6B 0%, #EE5253 100%) !important;
        color: white !important; border: none !important; text-align: center !important; font-weight: 700 !important;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #dfe6e9 !important; color: #2d3436 !important;
        border: 1px solid #b2bec3 !important; text-align: center !important; font-size: 18px !important;
    }
    .q-card { background: white; padding: 35px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); border-top: 6px solid #2c3e50; margin-bottom: 25px; }
    .q-card h3 { font-size: 24px !important; line-height: 1.5 !important; color: #000000 !important; font-weight: 700 !important; }
    .profile-card { background: white; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #eee; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    .login-wrapper { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #f0f0f0; text-align: center; margin-top: 50px; }
    .login-title { font-size: 28px; font-weight: 800; color: #2c3e50; margin-bottom: 10px; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%; border-bottom: 4px solid #3498db; }
    .metric-num { font-size: 28px; font-weight: 800; color: #2c3e50; }
    .metric-lbl { font-size: 12px; text-transform: uppercase; color: #95a5a6; letter-spacing: 1px; margin-top: 5px; }
    .timer-box { font-size: 22px; font-weight: 800; color: #e74c3c; text-align: center; background: white; border-radius: 10px; padding: 12px; margin-bottom: 20px; border: 2px solid #fab1a0; }
    .explanation-box { background-color: #e3fcf7; padding: 20px; border-radius: 12px; border-left: 5px solid #00b894; margin-top: 20px; color: #000000; font-size: 18px !important; line-height: 1.6; }
    .ai-btn { width: 100%; background-color: #e3f2fd; border: 1px solid #90caf9; color: #1565c0; padding: 12px; border-radius: 8px; text-align: center; text-decoration: none; display: inline-block; font-weight: bold; font-size: 16px; transition: all 0.3s; }
    .ai-btn:hover { background-color: #bbdefb; transform: translateY(-2px); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONNECTION & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

defaults = {
    'is_logged_in': False, 'current_user': None, 'user_role': 'User',
    'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None,
    'start_time': None, 'admin_auth': False, 'is_sprint_active': False,
    'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600,
    'sprint_score': 0, 'sprint_total_attempted': 0,
    'failed_login_attempts': 0,
    'last_activity_time': time.time(),
    'unsaved_stats': [] 
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. FUNCTIONS ---

def check_session_timeout():
    if st.session_state.is_logged_in:
        if time.time() - st.session_state.last_activity_time > 900: 
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.warning("Session expired. Login again.")
            st.stop()
        else: st.session_state.last_activity_time = time.time()
check_session_timeout()

SECURITY_QUESTIONS = ["Select...", "First pet?", "Birth city?", "Mother's maiden name?", "First car?", "Elementary school?"]

def sanitize_input(input_str):
    if not isinstance(input_str, str): return str(input_str)
    return re.sub(r'[^a-zA-Z0-9.@_ \-?]', '', input_str)

def validate_password_strength(password):
    if len(password) < 8: return False, "Min 8 chars."
    if not re.search(r"[a-zA-Z]", password): return False, "Need letter."
    if not re.search(r"\d", password): return False, "Need number."
    return True, "Valid"

def hash_password(password, salt=None):
    if salt is None: salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f"{salt}|{hashed}"

def check_password(stored_password, input_password):
    stored_password = str(stored_password).strip(); input_password = str(input_password).strip()
    if '|' in stored_password:
        salt, hashed = stored_password.split('|', 1)
        return secrets.compare_digest(hashlib.sha256((salt + input_password).encode('utf-8')).hexdigest(), hashed)
    else:
        if stored_password.endswith('.0'): stored_password = stored_password[:-2]
        return stored_password == input_password

def get_all_users():
    cols = ["username", "email", "password", "is_2fa_enabled", "gdpr_consent", "role", "security_question", "security_answer"]
    try:
        df = conn.read(worksheet="Users", ttl=0)
        for col in cols: 
            if col not in df.columns: df[col] = ""
        return df
    except: return pd.DataFrame(columns=cols)

def clean_boolean(val):
    return str(val).strip().upper() in ['TRUE', '1', '1.0', 'YES', 'ON']

def register_new_user(username, email, password, gdpr, sec_q, sec_a):
    clean_user = sanitize_input(username); clean_email = sanitize_input(email)
    if sec_q == SECURITY_QUESTIONS[0] or not sec_a: return False, "Security question missing."
    valid, msg = validate_password_strength(password)
    if not valid: return False, msg
    users = get_all_users()
    if not users.empty and clean_user in users['username'].astype(str).str.strip().values: return False, "Username exists."
    
    new_user = pd.DataFrame([{
        "username": clean_user, "email": clean_email, "password": hash_password(password.strip()),
        "is_2fa_enabled": "FALSE", "gdpr_consent": "TRUE" if gdpr else "FALSE", "role": "User",
        "security_question": sec_q, "security_answer": hash_password(sec_a.strip().lower())
    }])
    conn.update(worksheet="Users", data=pd.concat([users, new_user], ignore_index=True))
    return True, "Created!"

def verify_login(username, password):
    if st.session_state.failed_login_attempts >= 5: return False, "LOCKED"
    users = get_all_users()
    if users.empty: return False, None
    user_rec = users[users['username'].astype(str).str.strip() == str(username).strip()]
    if not user_rec.empty:
        if check_password(user_rec.iloc[0]['password'], password):
            st.session_state.failed_login_attempts = 0
            role = user_rec.iloc[0].get('role', 'User')
            return True, str(role).strip() if pd.notna(role) else 'User'
    return False, None

def save_stat_local(q_id, correct, confidence, reason):
    st.session_state.unsaved_stats.append({
        "user_id": st.session_state.current_user,
        "question_id": str(q_id),
        "is_correct": "TRUE" if correct else "FALSE",
        "confidence_level": str(confidence), "error_reason": str(reason),
        "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def flush_stats_to_db():
    if not st.session_state.unsaved_stats: return
    try:
        with st.spinner("Saving progress to cloud..."):
            existing = conn.read(worksheet="User_Stats", ttl=0)
            new_df = pd.DataFrame(st.session_state.unsaved_stats)
            final_df = pd.concat([existing, new_df], ignore_index=True).dropna(how='all')
            conn.update(worksheet="User_Stats", data=final_df)
            st.session_state.unsaved_stats = [] 
    except Exception as e: st.error(f"Save failed: {e}")

def get_security_question(username):
    users = get_all_users()
    rec = users[users['username'].astype(str).str.strip() == username]
    if not rec.empty:
        q = rec.iloc[0].get('security_question', '')
        if pd.notna(q) and q != SECURITY_QUESTIONS[0]: return True, q
    return False, None

def reset_password_with_security_answer(username, answer, new_password):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if not idx: return False, "User not found."
    if not check_password(users.at[idx[0], 'security_answer'], answer.strip().lower()): return False, "Wrong answer."
    valid, msg = validate_password_strength(new_password)
    if not valid: return False, msg
    users.at[idx[0], 'password'] = hash_password(new_password.strip())
    conn.update(worksheet="Users", data=users)
    return True, "Reset successful."

def update_user_password(username, curr_pass, new_pass):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if not idx: return False, "User not found."
    if not check_password(users.at[idx[0], 'password'], curr_pass): return False, "Wrong current password."
    valid, msg = validate_password_strength(new_pass)
    if not valid: return False, msg
    users.at[idx[0], 'password'] = hash_password(new_pass.strip())
    conn.update(worksheet="Users", data=users)
    return True, "Password updated."

def update_user_email(username, new_email):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        users.at[idx[0], 'email'] = sanitize_input(new_email)
        conn.update(worksheet="Users", data=users)
        return True, "Email updated."
    return False, "User not found."

def update_security_settings(username, sec_q, sec_a):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        users.at[idx[0], 'security_question'] = sec_q
        users.at[idx[0], 'security_answer'] = hash_password(sec_a.strip().lower())
        conn.update(worksheet="Users", data=users)
        return True, "Settings updated."
    return False, "Error."

def get_user_rank(df):
    if df.empty: return "Novice", 0
    c = len(df[df['user_id'] == st.session_state.current_user])
    if c < 10: return "🟢 Novice", c
    elif c < 50: return "🔵 Junior Analyst", c
    elif c < 100: return "🟣 Security Architect", c
    return "👑 CISO Master", c

def prepare_sprint_data(dom):
    q = conn.read(worksheet="Questions", ttl=3600)
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
        stats = conn.read(worksheet="User_Stats", ttl=600)
        if stats.empty: st.success("No errors!"); return
        stats = stats[stats['user_id'] == st.session_state.current_user]
        stats['is_correct_val'] = stats['is_correct'].apply(clean_boolean)
        wrong_ids = stats[stats['is_correct_val'] == 0]['question_id'].unique()
        if len(wrong_ids) == 0: st.success("Great job!"); return
        all_q = conn.read(worksheet="Questions", ttl=3600)
        clean_ids = [str(x).split('.')[0] for x in wrong_ids]
        all_q['clean_id'] = all_q['id'].astype(str).str.split('.').str[0]
        r_list = all_q[all_q['clean_id'].isin(clean_ids)]
        if r_list.empty: st.warning("Questions missing."); return
        c = min(len(r_list), 20)
        st.session_state.smart_list = r_list.sample(n=c).reset_index(drop=True)
        st.session_state.q_idx = 0; st.session_state.start_time = time.time(); st.session_state.is_sprint_active = True; st.session_state.view = 'Study'; st.session_state.mode = 'Review'; st.session_state.sprint_type = 'Count'; st.session_state.sprint_target = c; st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0; st.rerun()
    except Exception as e: st.error("Error loading review.")

# --- SIDEBAR CONTROL & GÜVENLİĞİ ---
# 1. GÜVENLİK ÖNLEMİ: Giriş yapılmadıysa sayfayı zorla 'Main' (Login) yap
if not st.session_state.is_logged_in:
    st.session_state.view = 'Main'

# 2. SIDEBAR SADECE GİRİŞ YAPILDIĞINDA GÖRÜNSÜN
if st.session_state.is_logged_in:
    with st.sidebar:
        try:
            stats_p = conn.read(worksheet="User_Stats", ttl=600)
            rank, total_q = get_user_rank(stats_p)
        except: rank, total_q = "Novice", 0
        
        role_badge = "👑 ADMIN" if st.session_state.user_role == 'Admin' else "USER"
        st.markdown(f"""<div class="profile-card"><div style="font-size: 36px; margin-bottom:10px;">🛡️</div><div style="font-weight:800; font-size:22px; color:#2c3e50;">{st.session_state.current_user}</div><div style="font-size:11px; color:white; background:#34495e; padding:4px 10px; border-radius:12px; display:inline-block; margin-bottom:5px;">{role_badge}</div><div style="font-size:13px; color:#7f8c8d; text-transform:uppercase; margin-top:5px;">{rank}</div><div style="background:#eec5a9; color:#d35400; padding:5px 10px; border-radius:8px; font-weight:bold; font-size:13px; display:inline-block; margin-top:10px;">Solved: {total_q}</div></div>""", unsafe_allow_html=True)
        st.write("---")
        
        if st.button("🏠 Home", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()
        if st.button("📊 Analytics", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
        if st.button("⚙️ Settings", use_container_width=True, type="secondary"): 
            flush_stats_to_db() 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Settings'; st.rerun()
        if st.session_state.user_role == 'Admin':
            if st.button("🔑 Admin", use_container_width=True, type="primary"): 
                flush_stats_to_db()
                st.session_state.is_sprint_active = False; st.session_state.view = 'Admin'; st.rerun()
        st.write("")
        if st.button("🚪 Logout", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# --- VIEWS ---
if st.session_state.view == 'Main':
    if not st.session_state.is_logged_in: # Login Flow
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            st.markdown("""<div class="login-wrapper"><div style="font-size: 50px;">🛡️</div><div class="login-title">CISSP Mentor Pro</div><div class="login-subtitle">Your AI-Powered Certification Partner</div></div>""", unsafe_allow_html=True)
            tab1, tab2, tab3 = st.tabs(["🔑 LOGIN", "📝 SIGN UP", "🆘 RECOVERY"])
            with tab1:
                st.write("")
                if st.session_state.failed_login_attempts >= 5: st.error("🔒 Account locked.")
                else:
                    with st.form("l_form"):
                        u = st.text_input("Username"); p = st.text_input("Password", type="password")
                        if st.form_submit_button("Login", type="primary", use_container_width=True):
                            time.sleep(0.5)
                            suc, role = verify_login(u, p)
                            if suc: st.session_state.is_logged_in=True; st.session_state.current_user=u.strip(); st.session_state.user_role=role; st.rerun()
                            else: 
                                st.session_state.failed_login_attempts += 1
                                st.error("Invalid credentials.")
            with tab2:
                st.write("")
                with st.form("s_form"):
                    u = st.text_input("Username"); e = st.text_input("Email"); p = st.text_input("Password", type="password")
                    st.markdown("---"); q = st.selectbox("Security Question", SECURITY_QUESTIONS); a = st.text_input("Answer")
                    g = st.checkbox("GDPR Consent")
                    if st.form_submit_button("Sign Up", type="secondary", use_container_width=True):
                        suc, msg = register_new_user(u, e, p, g, q, a)
                        if suc: st.success(msg)
                        else: st.error(msg)
            with tab3:
                st.write(""); u = st.text_input("Username for Recovery")
                if u:
                    has_q, quest = get_security_question(u)
                    if has_q:
                        st.info(f"❓ {quest}")
                        with st.form("r_form"):
                            ans = st.text_input("Answer"); new_p = st.text_input("New Password", type="password")
                            if st.form_submit_button("Reset", type="primary"):
                                suc, msg = reset_password_with_security_answer(u, ans, new_p)
                                if suc: st.success(msg)
                                else: st.error(msg)
                    else: st.warning("User not found.")
    else: # Logged In Main
        st.title("🛡️ CISSP Mentor Pro"); st.markdown(f"**Welcome, {st.session_state.current_user}!**")
        dom = st.selectbox("Target Domain:", ["All Domains (Mix)"] + list(TOPIC_MAP.values()))
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        with c1: 
            if st.button("⏱️ 10 Min Sprint", type="primary"): start_sprint('Time', 600, dom)
        with c2: 
            if st.button("⚡ 5 Min Blitz", type="primary"): start_sprint('Time', 300, dom)
        with c3: 
            if st.button("📝 10 Questions", type="primary"): start_sprint('Count', 10, dom)
        with c4: 
            if st.button("↺ Review Errors", type="secondary"): start_review()

elif st.session_state.view == 'Settings':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() # GÜVENLİK
    st.header("⚙️ Settings"); t1, t2 = st.tabs(["Account", "Security"])
    with t1:
        with st.form("e_up"):
            e = st.text_input("New Email"); 
            if st.form_submit_button("Update"): 
                suc, msg = update_user_email(st.session_state.current_user, e)
                if suc: st.success(msg)
                else: st.error(msg)
        with st.form("p_up"):
            cp = st.text_input("Current Pass", type="password"); np = st.text_input("New Pass", type="password")
            if st.form_submit_button("Change Password"):
                suc, msg = update_user_password(st.session_state.current_user, cp, np)
                if suc: st.success(msg)
                else: st.error(msg)
    with t2:
        with st.form("s_up"):
            q = st.selectbox("New Question", SECURITY_QUESTIONS); a = st.text_input("New Answer", type="password")
            if st.form_submit_button("Update Security"):
                suc, msg = update_security_settings(st.session_state.current_user, q, a)
                if suc: st.success(msg)
                else: st.error(msg)

elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() # GÜVENLİK
    c_back, c_tm, c_ex = st.columns([1, 2, 1])
    with c_back:
        if st.session_state.q_idx > 0:
            if st.button("⬅️ Prev", use_container_width=True, type="secondary"):
                st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()
    with c_tm: ph = st.empty()
    with c_ex:
        if st.button("Exit ❌", use_container_width=True, type="secondary"): 
            flush_stats_to_db() # Çıkarken kaydet
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

    if end: 
        flush_stats_to_db() # Bitişte kaydet
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        st.markdown(f"""<div class="q-card"><h3>{html.escape(curr["content_text"])}</h3></div>""", unsafe_allow_html=True)
        
        with st.expander("💡 🤖 Need a Hint?"):
            enc = urllib.parse.quote(curr["content_text"] + " CISSP explanation")
            st.markdown(f"""<a href="https://www.google.com/search?q={enc}" target="_blank"><div class="ai-btn">Google Search</div></a>""", unsafe_allow_html=True)
            st.text_area("Copy Prompt:", value=f"Explain:\n'{curr['content_text']}'")

        c1, c2 = st.columns(2)
        opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
        for i, (cd, cl) in enumerate(opts):
            with (c1 if i%2==0 else c2):
                if st.button(f"{cd}) {curr[cl]}", use_container_width=True):
                    st.session_state.feedback = (cd == curr['correct_option'])
                    st.session_state.last_q_id = curr['id']
                    if st.session_state.feedback: st.session_state.sprint_score += 1
                    st.session_state.sprint_total_attempted += 1
                    st.rerun()
        if st.session_state.feedback is not None:
            st.write("---")
            if st.session_state.feedback:
                st.success(f"✅ Correct! {curr['correct_option']}")
                st.markdown(f'<div class="explanation-box">{html.escape(str(curr["explanation"]))}</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("Next (Sure)", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, True, "Sure", "None") # LOCAL SAVE
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c2.button("Next (Guess)", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, True, "Guessed", "None") # LOCAL SAVE
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
            else:
                st.error(f"❌ Wrong. {curr['correct_option']}")
                st.markdown(f'<div class="explanation-box">{html.escape(str(curr["explanation"]))}</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                if c1.button("Knowledge", type="primary", use_container_width=True): save_stat_local(st.session_state.last_q_id, False, "None", "Knowledge Gap"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c2.button("Attention", type="primary", use_container_width=True): save_stat_local(st.session_state.last_q_id, False, "None", "Attention"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c3.button("Logic", type="primary", use_container_width=True): save_stat_local(st.session_state.last_q_id, False, "None", "Interpretation"); st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
    else: 
        flush_stats_to_db() # Liste bitti, kaydet
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

elif st.session_state.view == 'Score_Summary':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() # GÜVENLİK
    flush_stats_to_db()
    sc = st.session_state.sprint_score; tot = st.session_state.sprint_total_attempted
    ac = (sc / tot * 100) if tot > 0 else 0
    st.markdown(f"""<div style="text-align:center; padding: 60px; background:white; border-radius:20px; box-shadow:0 10px 30px rgba(0,0,0,0.1); margin-top:20px;"><h1 style="color:#2c3e50; font-size: 45px;">🏁 Finished!</h1><div style="font-size: 90px; font-weight: 800; color:#0d6efd; margin: 20px 0;">{sc} / {tot}</div><h3 style="color:#6c757d;">ACCURACY: {ac:.1f}%</h3></div>""", unsafe_allow_html=True)
    st.write(""); c1, c2 = st.columns(2)
    if c1.button("🏠 Home", use_container_width=True, type="primary"): st.session_state.view = 'Main'; st.rerun()
    if c2.button("📊 Analytics", use_container_width=True, type="secondary"): st.session_state.view = 'Analytics'; st.rerun()

elif st.session_state.view == 'Analytics':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() # GÜVENLİK
    st.header("📊 Intelligence Dashboard")
    try:
        stats = conn.read(worksheet="User_Stats", ttl=0) # Analiz için güncel veri şart
        if not stats.empty: stats = stats[stats['user_id'] == st.session_state.current_user]
        questions = conn.read(worksheet="Questions", ttl=3600)
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]; questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid')
            merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(TOPIC_MAP)
            merged['is_correct_val'] = merged['is_correct'].apply(clean_boolean)
            
            k1, k2, k3 = st.columns(3)
            k1.markdown(f'<div class="metric-card"><div class="metric-num">{len(merged)}</div><div class="metric-lbl">Total</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="metric-card"><div class="metric-num">%{(merged["is_correct_val"].sum()/len(merged)*100):.1f}</div><div class="metric-lbl">Accuracy</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="metric-card"><div class="metric-num">{merged["qid"].nunique()}</div><div class="metric-lbl">Unique Qs</div></div>', unsafe_allow_html=True)
            
            st.write("---"); c1, c2 = st.columns([1,2])
            merged['Result'] = merged['is_correct_val'].apply(lambda x: 'TRUE' if x == 1 else 'FALSE')
            with c1: st.plotly_chart(px.pie(merged, names='Result', title="Ratio", color_discrete_map={'TRUE':'#198754','FALSE':'#dc3545'}), use_container_width=True)
            with c2: 
                perf = merged.groupby('Domain')['is_correct_val'].mean().reset_index(); perf['Acc'] = perf['is_correct_val']*100
                st.plotly_chart(px.bar(perf, x='Acc', y='Domain', orientation='h', title='Domain Mastery', color='Acc', color_continuous_scale='RdYlGn'), use_container_width=True)
        else: st.info("No data.")
    except Exception as e: st.error(str(e))

elif st.session_state.view == 'Admin':
    if st.session_state.user_role != 'Admin': st.session_state.view = 'Main'; st.rerun()
    st.subheader("💾 Admin Sync")
    up = st.file_uploader("Questions (.xlsx)", type=['xlsx'])
    if up and st.button("Sync"):
        try:
            c = conn.read(worksheet="Questions", ttl=0); n = pd.read_excel(up)
            conn.update(worksheet="Questions", data=pd.concat([c, n], ignore_index=True)); st.success("Synced.")
        except Exception as e: st.error(f"Error: {e}")
