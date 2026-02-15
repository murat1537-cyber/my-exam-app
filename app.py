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
import pyotp
import qrcode
from io import BytesIO
from cryptography.fernet import Fernet

# --- 1. CONFIGURATION (EN ÜSTE TAŞINDI) ---
# Streamlit'te bu komut her zaman importlardan hemen sonra gelmelidir.
# ESKİ: page_title="CISSP AI Mentor"
# YENİ: page_title="Cyber Mentor Pro"
st.set_page_config(page_title="Cyber Mentor Pro", page_icon="🛡️", layout="wide")

# --- 2. EXAM DOMAIN MAPPINGS ---
CISSP_MAP = {
    "1": "Security and Risk Management",
    "2": "Asset Security",
    "3": "Security Architecture and Engineering",
    "4": "Communication and Network Security",
    "5": "Identity and Access Management (IAM)",
    "6": "Security Assessment and Testing",
    "7": "Security Operations",
    "8": "Software Development Security"
}

CISM_MAP = {
    "1": "Information Security Governance",
    "2": "Information Risk Management",
    "3": "Information Security Program Development and Management",
    "4": "Information Security Incident Management"
}

# Varsayılan Sınav Seçimi
if 'selected_exam' not in st.session_state: st.session_state.selected_exam = 'CISSP'

# Global Harita Tanımı
TOPIC_MAP = CISSP_MAP if st.session_state.selected_exam == 'CISSP' else CISM_MAP

# --- 3. CSS STYLES ---
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

# --- 3. CONNECTION, STATE & ENCRYPTION SETUP ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- KRİPTOGRAFİ ANAHTARI YÖNETİMİ ---
# NOT: Prodüksiyonda bu anahtarı st.secrets["encryption_key"] içine koymalısınız.
# Demo'da her seferinde değişmemesi için sabit bir key kullanıyoruz.
# Eğer anahtarı değiştirirseniz eski şifrelenmiş veriler okunamaz!
FIXED_KEY = b'wz7X5Xy1Y9Z8a2B3c4D5e6F7g8H9i0j1k2l3m4n5o6p=' 
try:
    cipher_suite = Fernet(FIXED_KEY)
except:
    # Key hatalıysa veya yoksa geçici oluştur (Veri kaybı riski uyarısı)
    temp_key = Fernet.generate_key()
    cipher_suite = Fernet(temp_key)

defaults = {
    'is_logged_in': False, 'current_user': None, 'user_role': 'User',
    'q_idx': 0, 'view': 'Main', 'feedback': None, 'smart_list': None,
    'start_time': None, 'admin_auth': False, 'is_sprint_active': False,
    'mode': 'Normal', 'sprint_type': 'Time', 'sprint_target': 600,
    'sprint_score': 0, 'sprint_total_attempted': 0,
    'failed_login_attempts': 0,
    'last_activity_time': time.time(),
    'unsaved_stats': [],
    'login_step': 'credentials', 
    'temp_user_data': None,
    'settings_2fa_secret': None
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. SECURITY, LOGGING & ENCRYPTION FUNCTIONS ---

# --- YENİ: AUDIT LOGGING ---
def log_audit_event(event_type, username, details=""):
    """Güvenlik olaylarını Audit_Logs sayfasına HASH imzasıyla kaydeder."""
    try:
        # Mevcut logları oku
        try:
            logs_df = conn.read(worksheet="Audit_Logs", ttl=0)
        except:
            logs_df = pd.DataFrame(columns=["timestamp", "event_type", "username", "details", "checksum"])
        
        # Zaman damgası
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # --- BÜTÜNLÜK İMZASI (INTEGRITY HASH) OLUŞTURMA ---
        # Logun içeriğini birleştirip SHA-256 ile imzala.
        # Biri Excel'den veriyi değiştirirse, bu hash tutmayacağı için yakalanır.
        raw_data = f"{ts}|{event_type}|{username}|{details}|{st.secrets['general']['encryption_key']}"
        checksum = hashlib.sha256(raw_data.encode()).hexdigest()
        
        new_log = pd.DataFrame([{
            "timestamp": ts,
            "event_type": event_type,
            "username": username,
            "details": details,
            "checksum": checksum # İmzayı da kaydet
        }])
        
        updated_logs = pd.concat([logs_df, new_log], ignore_index=True)
        conn.update(worksheet="Audit_Logs", data=updated_logs)
    except Exception as e:
        print(f"Audit Log Error: {e}")

# --- YENİ: ŞİFRELEME YARDIMCILARI ---
def encrypt_data(data_str):
    """Hassas veriyi veritabanına yazmadan önce şifreler."""
    if not data_str: return ""
    try:
        return cipher_suite.encrypt(data_str.encode()).decode()
    except Exception as e:
        return data_str # Hata olursa ham döndür (Risk yönetimi)

def decrypt_data(token_str):
    """Veritabanından okunan şifreli veriyi çözer."""
    if not token_str: return ""
    try:
        return cipher_suite.decrypt(token_str.encode()).decode()
    except:
        # Şifre çözülemezse (belki eski düz metin veridir), olduğu gibi döndür
        return token_str

def check_session_timeout():
    if st.session_state.is_logged_in:
        if time.time() - st.session_state.last_activity_time > 900: 
            user = st.session_state.current_user
            for key in list(st.session_state.keys()): del st.session_state[key]
            log_audit_event("SESSION_TIMEOUT", user, "Auto logout due to inactivity")
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
    # 'failed_attempts' sütunu eklendi
    cols = ["username", "email", "password", "is_2fa_enabled", "gdpr_consent", "role", "security_question", "security_answer", "totp_secret", "is_premium", "failed_attempts"]
    try:
        df = conn.read(worksheet="Users", ttl=0)
        for col in cols: 
            if col not in df.columns: df[col] = ""
        return df
    except: return pd.DataFrame(columns=cols)

def clean_boolean(val):
    if isinstance(val, bool): return val
    if isinstance(val, (int, float)): return val == 1
    return str(val).strip().upper() in ['TRUE', '1', '1.0', 'YES', 'ON']

def register_new_user(username, email, password, gdpr, sec_q, sec_a):
    clean_user = sanitize_input(username); clean_email = sanitize_input(email)
    if sec_q == SECURITY_QUESTIONS[0] or not sec_a: return False, "Security question missing."
    valid, msg = validate_password_strength(password)
    if not valid: return False, msg
    users = get_all_users()
    if not users.empty and clean_user in users['username'].astype(str).str.strip().values: return False, "Username exists."
    
    # GÜVENLİK: Cevabı hashle, ama TOTP secret'ı boş başlat
    secure_password = hash_password(password.strip())
    secure_answer = hash_password(sec_a.strip().lower()) 
    # Not: Security Answer'ı hashliyoruz (geri dönüşü yok), TOTP Secret'ı şifreliyoruz (geri dönüşü var)
    
    new_user = pd.DataFrame([{
        "username": clean_user, "email": clean_email, "password": secure_password,
        "is_2fa_enabled": "FALSE", "gdpr_consent": "TRUE" if gdpr else "FALSE", "role": "User",
        "security_question": sec_q, 
        "security_answer": secure_answer, # Hashli sakla
        "totp_secret": "" 
    }])
    conn.update(worksheet="Users", data=pd.concat([users, new_user], ignore_index=True))
    log_audit_event("REGISTER", clean_user, "New account created")
    return True, "Created! You can enable 2FA in Settings."

def verify_login_step1(username, password):
    users = get_all_users()
    if users.empty: return False, "INVALID", None
    
    # Kullanıcıyı bul
    idx = users.index[users['username'].astype(str).str.strip() == str(username).strip()].tolist()
    
    if not idx:
        time.sleep(0.5) 
        log_audit_event("LOGIN_FAIL", username, "User not found")
        return False, "INVALID", None
        
    row_idx = idx[0]
    user_row = users.iloc[row_idx] # Bu artık tek bir satırdır (Series)
    
    # --- 1. KİLİT KONTROLÜ ---
    try:
        raw_fails = user_row.get('failed_attempts', 0)
        if pd.isna(raw_fails) or str(raw_fails).strip() == '': fails = 0
        else: fails = int(float(str(raw_fails)))
    except: fails = 0
    
    if fails >= 5:
        log_audit_event("LOGIN_LOCKOUT", username, "Account locked (Database enforced)")
        return False, "LOCKED", None

    # --- 2. ŞİFRE KONTROLÜ ---
    # Not: user_row tekil olduğu için doğrudan ['password'] ile erişiyoruz
    if check_password(user_row['password'], password):
        # BAŞARILI: Sayacı sıfırla
        if fails > 0:
            users.at[row_idx, 'failed_attempts'] = 0
            conn.update(worksheet="Users", data=users)
            
        # 2FA ve Rol Bilgisi (DÜZELTİLEN KISIM BURASI)
        # user_row zaten satırın kendisi olduğu için .iloc[0] KULLANMIYORUZ.
        is_2fa = clean_boolean(user_row.get('is_2fa_enabled', False))
        role = user_row.get('role', 'User') # .iloc[0] kaldırıldı
        
        encrypted_secret = str(user_row.get('totp_secret', ''))
        decrypted_secret = decrypt_data(encrypted_secret)
        
        user_data = {
            'username': str(username).strip(),
            'role': str(role).strip() if pd.notna(role) else 'User',
            'secret': decrypted_secret
        }
        return True, "2FA_REQ" if is_2fa else "SUCCESS", user_data
    
    else:
        # BAŞARISIZ
        new_fails = fails + 1
        users.at[row_idx, 'failed_attempts'] = new_fails
        conn.update(worksheet="Users", data=users)
        
        log_audit_event("LOGIN_FAIL", username, f"Bad pass. Attempt {new_fails}/5")
        
        if new_fails >= 5:
            return False, "LOCKED", None
        else:
            return False, "INVALID", None

def verify_totp_code(secret, code):
    if not secret or len(secret) < 16: return False 
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    except: return False

def enable_2fa_for_user(username, secret):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        # GÜVENLİK: Secret'ı veritabanına yazarken ENCRYPT et
        encrypted_secret = encrypt_data(secret)
        
        users.at[idx[0], 'totp_secret'] = encrypted_secret
        users.at[idx[0], 'is_2fa_enabled'] = "TRUE"
        conn.update(worksheet="Users", data=users)
        log_audit_event("2FA_ENABLE", username, "2FA activated")
        return True
    return False

def disable_2fa_for_user(username):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        users.at[idx[0], 'totp_secret'] = ""
        users.at[idx[0], 'is_2fa_enabled'] = "FALSE"
        conn.update(worksheet="Users", data=users)
        log_audit_event("2FA_DISABLE", username, "2FA deactivated")
        return True
    return False

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
        with st.spinner("Saving..."):
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
    # Security answer HASH'li olduğu için check_password kullanırız (Decryption gerekmez)
    if not check_password(users.at[idx[0], 'security_answer'], answer.strip().lower()): 
        log_audit_event("RESET_FAIL", username, "Wrong security answer")
        return False, "Wrong answer."
    
    valid, msg = validate_password_strength(new_password)
    if not valid: return False, msg
    users.at[idx[0], 'password'] = hash_password(new_password.strip())
    conn.update(worksheet="Users", data=users)
    log_audit_event("PASSWORD_RESET", username, "Reset via recovery")
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
    log_audit_event("PASSWORD_CHANGE", username, "User changed password")
    return True, "Password updated."

def update_user_email(username, new_email):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        users.at[idx[0], 'email'] = sanitize_input(new_email)
        conn.update(worksheet="Users", data=users)
        log_audit_event("EMAIL_CHANGE", username, "Email updated")
        return True, "Email updated."
    return False, "User not found."

def update_security_settings(username, sec_q, sec_a):
    users = get_all_users()
    idx = users.index[users['username'].astype(str).str.strip() == username].tolist()
    if idx:
        users.at[idx[0], 'security_question'] = sec_q
        users.at[idx[0], 'security_answer'] = hash_password(sec_a.strip().lower())
        conn.update(worksheet="Users", data=users)
        log_audit_event("SEC_SETTINGS", username, "Security Q/A updated")
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
    # Seçili sınava göre doğru sayfayı ve konuları belirle
    exam = st.session_state.get('selected_exam', 'CISSP')
    target_sheet = "Questions" if exam == 'CISSP' else "Questions_CISM"
    current_map = CISSP_MAP if exam == 'CISSP' else CISM_MAP
    
    # İlgili sayfadan soruları çek
    try:
        q = conn.read(worksheet=target_sheet, ttl=0) # Anlık değişim için ttl=0
    except:
        st.error(f"Sheet '{target_sheet}' not found. Please create it in Google Sheets.")
        return pd.DataFrame()

    if dom != "All Domains (Mix)":
        # Domain ismine göre ID'yi bul (Tersine arama)
        tid = [k for k, v in current_map.items() if v == dom]
        if tid:
            q = q[q['topic_id'].astype(str).str.split('.').str[0] == tid[0]]
            
    return q

def start_sprint(m_type, val, dom):
    # --- 1. KULLANICI PREMIUM MU KONTROL ET (DÜZELTİLDİ) ---
    users = get_all_users()
    # Kullanıcıyı bul
    user_row = users[users['username'].astype(str).str.strip() == st.session_state.current_user]
    
    is_premium = False
    if not user_row.empty:
        # HATA DÜZELTMESİ: Veriyi clean_boolean ile okuyoruz.
        # Bu sayede 1, 1.0, TRUE, True, YES hepsini kabul eder.
        raw_val = user_row.iloc[0].get('is_premium', 'FALSE')
        is_premium = clean_boolean(raw_val)
    
    # Durumu hafızaya kaydet
    st.session_state.is_user_premium = is_premium

    # --- 2. KISITLAMALARI UYGULA ---
    if not is_premium:
        # Eğer kullanıcı Premium DEĞİLSE ve:
        # a) Mock Exam (Deneme) açmaya çalışıyorsa
        # b) VEYA 10 Soru / Zamanlı modda 5 sorudan fazlasını seçtiyse (val > 5)
        if m_type == 'Mock' or (m_type != 'Mock' and val > 5):
            st.error("🔒 The Full Mock Exam and Unlimited Practice are for PREMIUM members only.")
            st.info("Free users are limited to 5 questions per session.")
            st.markdown("""
                <a href="https://stripe.com" target="_blank">
                    <button style="background-color:#FF4B4B; color:white; border:none; padding:10px 20px; font-size:16px; border-radius:8px; cursor:pointer;">
                        🚀 Upgrade Now
                    </button>
                </a>
                """, unsafe_allow_html=True)
            return
    # --------------------------------

    q = prepare_sprint_data(dom)
    if q.empty: st.error("No questions."); return
    
    if m_type == 'Mock':
        c = min(len(q), 100)
        st.session_state.sprint_type = 'Time'
        st.session_state.sprint_target = 10800 
    elif m_type == 'Time':
        c = min(len(q), 40)
        st.session_state.sprint_type = 'Time'
        st.session_state.sprint_target = val
    else:
        c = min(len(q), val)
        st.session_state.sprint_type = 'Count'
        st.session_state.sprint_target = val

    st.session_state.smart_list = q.sample(n=c).reset_index(drop=True)
    st.session_state.q_idx = 0; st.session_state.start_time = time.time()
    st.session_state.is_sprint_active = True; st.session_state.view = 'Study'
    st.session_state.mode = 'Normal'
    st.session_state.sprint_score = 0; st.session_state.sprint_total_attempted = 0
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
if not st.session_state.is_logged_in:
    st.session_state.view = 'Main'

if st.session_state.is_logged_in:
    with st.sidebar:
        try:
            stats_p = conn.read(worksheet="User_Stats", ttl=600)
            rank, total_q = get_user_rank(stats_p)
        except: rank, total_q = "Novice", 0
        
        users_sidebar = conn.read(worksheet="Users", ttl=600)
        user_row_sb = users_sidebar[users_sidebar['username'].astype(str).str.strip() == st.session_state.current_user]
        is_2fa_sb = False
        if not user_row_sb.empty:
            is_2fa_sb = clean_boolean(user_row_sb.iloc[0].get('is_2fa_enabled', 'FALSE'))
        
        sec_icon = "🟢" if is_2fa_sb else "⚠️"
        role_badge = "👑 ADMIN" if st.session_state.user_role == 'Admin' else "USER"
        st.markdown(f"""
        <div class="profile-card">
            <div style="font-size: 36px; margin-bottom:10px;">🛡️</div>
            <div style="font-weight:800; font-size:22px; color:#2c3e50;">{st.session_state.current_user}</div>
            <div style="font-size:11px; color:white; background:#34495e; padding:4px 10px; border-radius:12px; display:inline-block; margin-bottom:5px;">{role_badge}</div>
            <div style="font-size:12px; color:#7f8c8d; margin-top:2px;">Security: {sec_icon}</div>
            <div style="font-size:13px; color:#7f8c8d; text-transform:uppercase; margin-top:5px;">{rank}</div>
            <div style="background:#eec5a9; color:#d35400; padding:5px 10px; border-radius:8px; font-weight:bold; font-size:13px; display:inline-block; margin-top:10px;">Solved: {total_q}</div>
        </div>
        """, unsafe_allow_html=True)
        st.write("---")
        
        if st.button("🏠 Home", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()
        if st.button("📊 Analytics", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            st.session_state.is_sprint_active = False; st.session_state.view = 'Analytics'; st.rerun()
        settings_label = "⚙️ Settings (Enable 2FA)" if not is_2fa_sb else "⚙️ Settings"
        if st.button(settings_label, use_container_width=True, type="secondary"): 
            flush_stats_to_db() 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Settings'; st.rerun()
        if st.session_state.user_role == 'Admin':
            if st.button("🔑 Admin", use_container_width=True, type="primary"): 
                flush_stats_to_db()
                st.session_state.is_sprint_active = False; st.session_state.view = 'Admin'; st.rerun()
        st.write("")
        if st.button("🚪 Logout", use_container_width=True, type="secondary"): 
            flush_stats_to_db()
            log_audit_event("LOGOUT", st.session_state.current_user, "User logged out")
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# --- VIEWS ---
if st.session_state.view == 'Main':
    if not st.session_state.is_logged_in: # Login Flow
        # Kurtarma ekranı geçişi için state kontrolü
        if 'show_recovery' not in st.session_state: st.session_state.show_recovery = False

        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            # "CISSP Mentor Pro" yerine "Cyber Mentor Pro" yazıldı.
            st.markdown("""<div class="login-wrapper"><div style="font-size: 50px;">🛡️</div><div class="login-title">Cyber Mentor Pro</div><div class="login-subtitle">Your AI-Powered Certification Partner</div></div>""", unsafe_allow_html=True)            
            # --- DURUM 1: KURTARMA EKRANI AKTİFSE ---
            if st.session_state.show_recovery:
                st.markdown("### 🔄 Account Recovery")
                st.info("Enter your username to answer your security question.")
                
                if st.button("⬅️ Back to Login", type="secondary", use_container_width=True):
                    st.session_state.show_recovery = False
                    st.rerun()
                
                u = st.text_input("Username for Recovery")
                if u:
                    has_q, quest = get_security_question(u)
                    if has_q:
                        st.info(f"❓ Security Question: **{quest}**")
                        with st.form("r_form"):
                            ans = st.text_input("Answer")
                            new_p = st.text_input("New Password", type="password")
                            if st.form_submit_button("Reset Password", type="primary", use_container_width=True):
                                suc, msg = reset_password_with_security_answer(u, ans, new_p)
                                if suc: 
                                    st.success(msg)
                                    time.sleep(1.5)
                                    st.session_state.show_recovery = False # Logine dön
                                    st.rerun()
                                else: st.error(msg)
                    else: st.warning("User not found or security settings missing.")

           # --- DURUM 2: NORMAL GİRİŞ EKRANI (2 TAB) ---
            else:
                tab1, tab2 = st.tabs(["🔑 LOGIN", "📝 SIGN UP"])
                
                with tab1:
                    st.write("")
                    if st.session_state.failed_login_attempts >= 5: st.error("🔒 Account locked.")
                    else:
                        if st.session_state.login_step == 'credentials':
                            with st.form("l_form"):
                                u = st.text_input("Username")
                                p = st.text_input("Password", type="password")
                                if st.form_submit_button("Login", type="primary", use_container_width=True):
                                    time.sleep(0.5)
                                    success, msg, data = verify_login_step1(u, p)
                                    if success and msg == "SUCCESS":
                                        log_audit_event("LOGIN_SUCCESS", data['username'], "Login without 2FA")
                                        st.session_state.is_logged_in=True; st.session_state.current_user=data['username']; st.session_state.user_role=data['role']; st.session_state.failed_login_attempts=0; st.rerun()
                                    elif success and msg == "2FA_REQ":
                                        st.session_state.login_step = '2fa_check'; st.session_state.temp_user_data = data; st.session_state.failed_login_attempts=0; st.rerun()
                                    else:
                                        st.session_state.failed_login_attempts += 1; st.error("Invalid credentials.")
                            
                            # ŞİFREMİ UNUTTUM BUTONU
                            st.write("")
                            if st.button("❓ Forgot Password?", type="secondary", use_container_width=True):
                                st.session_state.show_recovery = True
                                st.rerun()

                        elif st.session_state.login_step == '2fa_check':
                            st.info("🔐 Two-Factor Authentication Required")
                            with st.form("2fa_form"):
                                code = st.text_input("Enter 6-digit Authenticator Code", max_chars=6)
                                if st.form_submit_button("Verify Code", type="primary", use_container_width=True):
                                    secret = st.session_state.temp_user_data.get('secret')
                                    if verify_totp_code(secret, code):
                                        log_audit_event("LOGIN_SUCCESS", st.session_state.temp_user_data['username'], "Login with 2FA")
                                        st.session_state.is_logged_in=True; st.session_state.current_user=st.session_state.temp_user_data['username']; st.session_state.user_role=st.session_state.temp_user_data['role']; st.session_state.login_step = 'credentials'; st.session_state.temp_user_data = None; st.rerun()
                                    else: 
                                        log_audit_event("LOGIN_FAIL_2FA", st.session_state.temp_user_data['username'], "Invalid TOTP")
                                        st.error("❌ Invalid Code")
                            if st.button("Cancel Login"): st.session_state.login_step = 'credentials'; st.session_state.temp_user_data = None; st.rerun()

                # DÜZELTME BURADA YAPILDI: tab_signup -> tab2 ve girintiler düzeltildi
                with tab2:
                    st.write("")
                    with st.form("s_form"):
                        st.markdown("##### Create New Account")
                        u = st.text_input("Username"); e = st.text_input("Email"); p = st.text_input("Password", type="password")
                        st.markdown("---"); q = st.selectbox("Security Question", SECURITY_QUESTIONS); a = st.text_input("Answer")
                        
                        st.write("")
                        # GİZLİLİK BİLDİRİMİ
                        with st.expander("📜 Read Privacy Policy (Gizlilik Bildirimi)"):
                            st.markdown("""
                            **Privacy Statement (Privacyverklaring)**
                            
                            1. **Data Collection:** We collect your username, email address, and encrypted password solely for authentication purposes. We also store your quiz performance data to generate analytics.
                            2. **Storage:** Your data is stored securely in a private Google Sheets database. Passwords are hashed (SHA-256) and never stored in plain text.
                            3. **Usage:** We do not share your data with third parties or use it for advertising. It is used strictly to provide the exam simulation service.
                            4. **Your Rights:** Under GDPR (AVG), you have the right to request a copy of your data or request complete deletion of your account.
                            5. **Contact:** To exercise your rights, please contact the administrator.
                            """)
                        
                        g = st.checkbox("I have read and accept the Privacy Policy")
                        
                        if st.form_submit_button("Sign Up", type="secondary", use_container_width=True):
                            if not g:
                                st.error("⚠️ You must accept the Privacy Policy to register.")
                            else:
                                suc, msg = register_new_user(u, e, p, g, q, a)
                                if suc: st.success(msg)
                                else: st.error(msg)
    else: # Logged In Main
        # --- SINAV SEÇİCİ (HEADER) ---
        c_ex1, c_ex2 = st.columns([3, 1])
        with c_ex1:
            st.title(f"🛡️ {st.session_state.selected_exam} Mentor Pro")
            st.markdown(f"**Welcome, {st.session_state.current_user}!** Ready to master {st.session_state.selected_exam}?")
        with c_ex2:
            # Sınav Değiştirme Butonu
            exam_choice = st.radio("Select Exam:", ["CISSP", "CISM"], horizontal=True, 
                                   index=0 if st.session_state.selected_exam == 'CISSP' else 1)
            
            # Eğer seçim değişirse state'i güncelle ve sayfayı yenile
            if exam_choice != st.session_state.selected_exam:
                st.session_state.selected_exam = exam_choice
                st.rerun()

        # Konu haritasını seçime göre güncelle
        current_map = CISSP_MAP if st.session_state.selected_exam == 'CISSP' else CISM_MAP
        
        # Dropdown artık dinamik
        dom = st.selectbox("Target Domain:", ["All Domains (Mix)"] + list(current_map.values()))
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        with c1: 
            if st.button("⏱️ 10 Min Sprint", type="primary"): start_sprint('Time', 600, dom)
        with c2: 
            if st.button("⚡ 5 Min Blitz", type="primary"): start_sprint('Time', 300, dom)
        with c3: 
            if st.button("📝 10 Questions", type="primary"): start_sprint('Count', 10, dom)
        with c4: 
            if st.button("↺ Review Errors", type="secondary"): start_review()
        
        st.write("")
        if st.button("🔥 Full Mock Exam (100 Qs - 3 Hours)", type="primary", use_container_width=True):
            start_sprint('Mock', 0, dom)

elif st.session_state.view == 'Settings':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() 
    st.header("⚙️ Settings"); t1, t2, t3 = st.tabs(["Account", "Security", "2FA (Authenticator)"])
    
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
    
    with t3:
        st.markdown("### 🔐 Two-Factor Authentication")
        users = get_all_users()
        user_row = users[users['username'].astype(str).str.strip() == st.session_state.current_user]
        is_enabled = False
        if not user_row.empty:
            is_enabled = clean_boolean(user_row.iloc[0].get('is_2fa_enabled', 'FALSE'))
        
        if is_enabled:
            st.success("✅ 2FA is currently ENABLED.")
            if st.button("Disable 2FA", type="secondary"):
                if disable_2fa_for_user(st.session_state.current_user):
                    st.success("2FA Disabled."); time.sleep(1); st.rerun()
        else:
            st.warning("⚠️ 2FA is DISABLED. Enable it for better security.")
            if st.session_state.settings_2fa_secret is None:
                st.session_state.settings_2fa_secret = pyotp.random_base32()
            secret = st.session_state.settings_2fa_secret
            
            totp = pyotp.TOTP(secret)
            uri = totp.provisioning_uri(name=st.session_state.current_user, issuer_name="CISSP Mentor")
            qr = qrcode.make(uri)
            img_bytes = BytesIO()
            qr.save(img_bytes, format='PNG')
            
            c1, c2 = st.columns([1, 2])
            with c1: st.image(img_bytes, caption="Scan with Google Auth", width=200)
            with c2:
                st.write(f"**Manual Key:** `{secret}`")
                st.write("1. Scan the QR code.")
                st.write("2. Enter the 6-digit code below to confirm.")
                c_code = st.text_input("Verification Code", max_chars=6)
                if st.button("Verify & Enable 2FA", type="primary"):
                    if verify_totp_code(secret, c_code):
                        if enable_2fa_for_user(st.session_state.current_user, secret):
                            st.success("2FA Enabled Successfully!"); st.session_state.settings_2fa_secret = None; time.sleep(1); st.rerun()
                    else: st.error("Invalid Code. Please try again.")

elif st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun()
    
    # --- ÜST MENÜ ---
    c_back, c_tm, c_ex = st.columns([1, 2, 1])
    with c_back:
        if st.session_state.q_idx > 0:
            if st.button("⬅️ Prev", use_container_width=True, type="secondary"):
                st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()
    with c_tm: ph = st.empty()
    with c_ex:
        if st.button("Exit ❌", use_container_width=True, type="secondary"): 
            flush_stats_to_db() 
            st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()

    # --- FREEMIUM DUVARI (THE WALL) ---
    # Eğer kullanıcı Premium değilse ve 5 soru çözdüyse durdur.
    if not st.session_state.get('is_user_premium', False):
        if st.session_state.sprint_total_attempted >= 5:
            st.warning("🔒 Free Limit Reached (5 Questions)")
            st.info("To continue practicing unlimited questions, please upgrade.")
            
            # BURAYA KENDİ ÖDEME LİNKİNİZİ KOYUN
            # Şu an 'stripe.com' koydum ki hata vermesin.
            st.markdown("""
                <a href="https://stripe.com" target="_blank">
                    <button style="background-color:#FF4B4B; color:white; border:none; padding:15px 32px; text-align:center; text-decoration:none; display:inline-block; font-size:16px; border-radius:12px; cursor:pointer; width:100%;">
                        🚀 Upgrade to Premium ($19.99)
                    </button>
                </a>
                """, unsafe_allow_html=True)
            
            if st.button("🏠 Return to Home", type="secondary", use_container_width=True):
                flush_stats_to_db()
                st.session_state.is_sprint_active = False; st.session_state.view = 'Main'; st.rerun()
            st.stop() # Kodun geri kalanını (soruyu) gösterme!
    # ----------------------------------

    end = False
    # ... (Kod buradan aynen devam ediyor: if st.session_state.sprint_type == 'Time': ...)
    if st.session_state.sprint_type == 'Time':
        rem = max(0, int(st.session_state.sprint_target - (time.time() - st.session_state.start_time)))
        if rem <= 0: end = True
        ph.markdown(f'<div class="timer-box">⏱️ {rem//60:02d}:{rem%60:02d}</div>', unsafe_allow_html=True)
    else:
        cur = st.session_state.q_idx + 1; tot = st.session_state.sprint_target
        if cur > tot: end = True
        ph.markdown(f'<div class="timer-box">Question {cur} / {tot}</div>', unsafe_allow_html=True)

    if end: 
        flush_stats_to_db()
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

    if st.session_state.q_idx < len(st.session_state.smart_list):
        curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
        st.markdown(f"""<div class="q-card"><h3>{html.escape(curr["content_text"])}</h3></div>""", unsafe_allow_html=True)
        
      # --- AI DESTEK ALANI (KOPYALA BUTONLU) ---
        with st.expander("💡 🤖 Need a Hint? (AI & Search Tools)"):
            # 1. Google Araması Hazırlığı
            q_text_raw = curr["content_text"]
            options_inline = f"A) {curr['option_a']} B) {curr['option_b']} C) {curr['option_c']} D) {curr['option_d']}"
            
            search_str = f"{q_text_raw} {options_inline} CISSP explanation"
            enc_q = urllib.parse.quote(search_str)
            
            c_h1, c_h2 = st.columns([1, 1])
            with c_h1:
                st.markdown(f"""
                <a href="https://www.google.com/search?q={enc_q}" target="_blank" style="text-decoration:none;">
                    <div class="ai-btn">🌐 Search on Google (w/ Options)</div>
                </a>
                """, unsafe_allow_html=True)
            
            with c_h2:
                # 2. ChatGPT Prompt Hazırlığı
                prompt = f"""Act as a CISSP expert. Analyze this question.
Explain why the correct answer is the best choice, and why the other options are incorrect.

Question:
{q_text_raw}

Options:
A) {curr['option_a']}
B) {curr['option_b']}
C) {curr['option_c']}
D) {curr['option_d']}"""
                
                # GÜNCELLEME: st.text_area yerine st.code kullanıldı.
                # Bu sayede sağ üstte otomatik "Kopyala" ikonu çıkacak.
                st.markdown("**📋 Copy Prompt for ChatGPT:**")
                st.code(prompt, language="markdown")
        # -------------------------------------------------------
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
       # --- GÜNCELLENMİŞ FEEDBACK ALANI ---
        if st.session_state.feedback is not None:
            st.write("---")
            
            # Doğru şıkkın tam metnini veritabanından çekiyoruz
            # Örn: 'B' -> 'option_b' sütunundaki yazı
            correct_letter = curr['correct_option']
            correct_text = curr[f"option_{correct_letter.lower()}"]
            
            if st.session_state.feedback:
                # DOĞRU CEVAP MESAJI
                st.success(f"✅ Correct! Correct answer is {correct_letter}) {correct_text}")
                
                # Açıklama Kutusu
                st.markdown(f'<div class="explanation-box">{html.escape(str(curr["explanation"]))}</div>', unsafe_allow_html=True)
                
                # İlerleme Butonları
                c1, c2 = st.columns(2)
                if c1.button("Next (Sure)", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, True, "Sure", "None")
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c2.button("Next (Guess)", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, True, "Guessed", "None")
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
            else:
                # YANLIŞ CEVAP MESAJI
                st.error(f"❌ Wrong! Correct answer is {correct_letter}) {correct_text}")
                
                # Açıklama Kutusu
                st.markdown(f'<div class="explanation-box">{html.escape(str(curr["explanation"]))}</div>', unsafe_allow_html=True)
                
                # Hata Analiz Butonları
                c1, c2, c3 = st.columns(3)
                if c1.button("Knowledge", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, False, "None", "Knowledge Gap")
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c2.button("Attention", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, False, "None", "Attention")
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
                if c3.button("Logic", type="primary", use_container_width=True): 
                    save_stat_local(st.session_state.last_q_id, False, "None", "Interpretation")
                    st.session_state.q_idx+=1; st.session_state.feedback=None; st.rerun()
        # -----------------------------------
    else: 
        flush_stats_to_db() 
        st.session_state.is_sprint_active = False; st.session_state.view = 'Score_Summary'; st.rerun()

elif st.session_state.view == 'Score_Summary':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() 
    flush_stats_to_db()
    sc = st.session_state.sprint_score; tot = st.session_state.sprint_total_attempted
    ac = (sc / tot * 100) if tot > 0 else 0
    st.markdown(f"""<div style="text-align:center; padding: 60px; background:white; border-radius:20px; box-shadow:0 10px 30px rgba(0,0,0,0.1); margin-top:20px;"><h1 style="color:#2c3e50; font-size: 45px;">🏁 Finished!</h1><div style="font-size: 90px; font-weight: 800; color:#0d6efd; margin: 20px 0;">{sc} / {tot}</div><h3 style="color:#6c757d;">ACCURACY: {ac:.1f}%</h3></div>""", unsafe_allow_html=True)
    st.write(""); c1, c2 = st.columns(2)
    if c1.button("🏠 Home", use_container_width=True, type="primary"): st.session_state.view = 'Main'; st.rerun()
    if c2.button("📊 Analytics", use_container_width=True, type="secondary"): st.session_state.view = 'Analytics'; st.rerun()

elif st.session_state.view == 'Analytics':
    if not st.session_state.is_logged_in: st.session_state.view='Main'; st.rerun() 
    
    # --- 1. SEÇİLİ SINAVA GÖRE VERİ HAZIRLIĞI ---
    exam = st.session_state.get('selected_exam', 'CISSP')
    target_sheet = "Questions" if exam == 'CISSP' else "Questions_CISM"
    current_map = CISSP_MAP if exam == 'CISSP' else CISM_MAP
    
    st.header(f"📊 {exam} Intelligence Dashboard")
    
    try:
        # İstatistikleri Çek
        stats = conn.read(worksheet="User_Stats", ttl=0) 
        if not stats.empty: stats = stats[stats['user_id'] == st.session_state.current_user]
        
        questions = conn.read(worksheet=target_sheet, ttl=3600)
        
        if not stats.empty and not questions.empty:
            stats['qid'] = stats['question_id'].astype(str).str.split('.').str[0]
            questions['qid'] = questions['id'].astype(str).str.split('.').str[0]
            
            # İç Birleştirme (Sadece seçili sınavın soruları)
            merged = pd.merge(stats, questions[['qid', 'topic_id']], on='qid', how='inner')
            
            if merged.empty:
                st.info(f"No analytics data found for {exam} yet.")
            else:
                # Veri İşleme
                merged['Domain'] = merged['topic_id'].astype(str).str.split('.').str[0].map(current_map)
                merged['is_correct_val'] = merged['is_correct'].apply(clean_boolean)
                
                # --- GRAFİKLER ---
                k1, k2, k3 = st.columns(3)
                k1.markdown(f'<div class="metric-card"><div class="metric-num">{len(merged)}</div><div class="metric-lbl">Total Questions</div></div>', unsafe_allow_html=True)
                k2.markdown(f'<div class="metric-card"><div class="metric-num">%{(merged["is_correct_val"].sum()/len(merged)*100):.1f}</div><div class="metric-lbl">Overall Accuracy</div></div>', unsafe_allow_html=True)
                k3.markdown(f'<div class="metric-card"><div class="metric-num">{merged["qid"].nunique()}</div><div class="metric-lbl">Unique Qs Solved</div></div>', unsafe_allow_html=True)
                
                st.write("---")
                c1, c2 = st.columns([1,2])
                merged['Result'] = merged['is_correct_val'].apply(lambda x: 'Correct' if x == 1 else 'Wrong')
                
                with c1: 
                    st.plotly_chart(px.pie(merged, names='Result', title="Success Distribution", color_discrete_map={'Correct':'#198754','Wrong':'#dc3545'}, hole=0.4), use_container_width=True)
                
                with c2: 
                    # Domain Mastery
                    perf = merged.groupby('Domain')['is_correct_val'].mean().reset_index()
                    perf['Acc'] = perf['is_correct_val']*100
                    st.plotly_chart(px.bar(perf, x='Acc', y='Domain', orientation='h', title='Domain Mastery (%)', color='Acc', color_continuous_scale='RdYlGn', range_x=[0,100]), use_container_width=True)
                
                # --- 🤖 YENİ: AI MENTOR ANALİZİ ---
                st.write("---")
                st.subheader("🤖 AI Mentor Analysis & Recommendations")
                
                # Analiz Hesaplamaları
                weakest_domain = perf.sort_values('Acc').iloc[0]
                strongest_domain = perf.sort_values('Acc', ascending=False).iloc[0]
                
                # Hata Sebeplerini Analiz Et
                wrong_answers = merged[merged['is_correct_val'] == False]
                if not wrong_answers.empty:
                    # 'None' olmayan hata sebeplerini say
                    error_counts = wrong_answers[wrong_answers['error_reason'] != 'None']['error_reason'].value_counts()
                    primary_issue = error_counts.index[0] if not error_counts.empty else "General"
                else:
                    primary_issue = "None"

                # Tavsiye Mesajı Oluştur (Chat Arayüzü ile)
                with st.chat_message("assistant", avatar="🛡️"):
                    st.write(f"Hello **{st.session_state.current_user}**, I've analyzed your performance data. Here is your personalized strategy:")
                    
                    # 1. Zayıf Nokta Analizi
                    st.markdown(f"**📉 Priority Focus Area:**")
                    st.info(f"Your weakest domain is **{weakest_domain['Domain']}** with **{weakest_domain['Acc']:.1f}%** accuracy. You should prioritize reviewing this chapter in your study guide immediately.")
                    
                    # 2. Hata Tipi Analizi
                    st.markdown(f"**🔍 Error Pattern Detection:**")
                    if primary_issue == "Knowledge Gap":
                        st.warning("I detected frequent **'Knowledge Gaps'**. This means you are often guessing or don't know the core concept. **Recommendation:** Stop solving questions for 1 day and focus solely on reading/watching lectures.")
                    elif primary_issue == "Attention":
                        st.warning("I detected frequent **'Attention Errors'**. You know the topic but miss keywords like 'NOT', 'BEST', 'MOST'. **Recommendation:** Slow down. Read each question twice before looking at the options.")
                    elif primary_issue == "Interpretation":
                        st.warning("I detected **'Logic/Interpretation'** issues. You are eliminating options but picking the distractor. **Recommendation:** Focus on the 'CISSP Mindset' (Think like a Manager, not a Tech).")
                    else:
                        st.success("Your error patterns are balanced. Keep practicing to build muscle memory.")
                    
                    # 3. Genel Motivasyon
                    if strongest_domain['Acc'] > 85:
                        st.markdown(f"**🌟 Strength:** You are dominating **{strongest_domain['Domain']}**! Great job.")
                    
                    if len(merged) < 30:
                        st.caption("⚠️ *Note: You have solved fewer than 30 questions. Solve more to make this analysis more accurate.*")

        else: 
            st.info("No data available yet. Start solving questions to populate the dashboard!")
            
    except Exception as e: st.error(f"Analytics Error: {str(e)}")

elif st.session_state.view == 'Admin':
    if st.session_state.user_role != 'Admin': st.session_state.view = 'Main'; st.rerun()
    st.subheader("💾 Admin Console")
    
    # 3 TAB OLACAK ŞEKİLDE GÜNCELLENDİ
    tab_sync, tab_logs, tab_backup = st.tabs(["Sync Questions", "Audit Logs", "📦 Backup Data"])
    
    with tab_sync:
        st.info("Select which exam database you want to update.")
        target_db = st.selectbox("Target Database", ["CISSP (Questions)", "CISM (Questions_CISM)"])
        sheet_name = "Questions" if target_db.startswith("CISSP") else "Questions_CISM"
        
        up = st.file_uploader(f"Upload {sheet_name} Excel (.xlsx)", type=['xlsx'])
        if up and st.button("Sync Data"):
            try:
                c = conn.read(worksheet=sheet_name, ttl=0); n = pd.read_excel(up)
                conn.update(worksheet=sheet_name, data=pd.concat([c, n], ignore_index=True))
                st.success(f"Synced successfully to {sheet_name}!")
            except Exception as e: st.error(f"Error: {e}")
            
    with tab_logs:
        try:
            logs = conn.read(worksheet="Audit_Logs", ttl=0)
            
            if not logs.empty:
                st.markdown("### 🕵️ Audit Integrity Monitor")
                
                # --- INTEGRITY CHECK (VERİ BÜTÜNLÜĞÜ KONTROLÜ) ---
                # Her satırı kontrol et: Hash tutuyor mu?
                def verify_log(row):
                    try:
                        # Kayıtlı Hash
                        stored_hash = str(row.get('checksum', ''))
                        
                        # Olması Gereken Hash (Yeniden Hesapla)
                        # Not: timestamp string formatı önemli, birebir aynı olmalı
                        ts = str(row['timestamp'])
                        # Secret key'i de hesaba katıyoruz ki dışarıdan biri hash üretemesin
                        raw = f"{ts}|{row['event_type']}|{row['username']}|{row['details']}|{st.secrets['general']['encryption_key']}"
                        calculated_hash = hashlib.sha256(raw.encode()).hexdigest()
                        
                        if stored_hash == calculated_hash:
                            return "✅ Valid"
                        else:
                            return "❌ CORRUPTED" # Biri elle değiştirmiş!
                    except:
                        return "⚠️ Unknown"

                # Kontrol sütununu ekle
                # (Eski loglarda checksum sütunu boşsa 'Unknown' yazar, yenilerde çalışır)
                if 'checksum' in logs.columns:
                    logs['Integrity Status'] = logs.apply(verify_log, axis=1)
                    
                    # Gösterim için sütun sırasını ayarla (En başa durumu koy)
                    cols = ['Integrity Status', 'timestamp', 'event_type', 'username', 'details']
                    st.dataframe(logs[cols].sort_index(ascending=False), use_container_width=True)
                    
                    # Eğer bozulmuş log varsa uyarı ver
                    if "❌ CORRUPTED" in logs['Integrity Status'].values:
                        st.error("🚨 SECURITY ALERT: Some logs have been tampered with! The database integrity is compromised.")
                else:
                    st.warning("Old log format detected. Integrity check will active for new logs.")
                    st.dataframe(logs.sort_index(ascending=False), use_container_width=True)

            else: 
                st.info("Log file exists but is empty.")
                
        except Exception as e:
            st.info(f"Log Error: {e}")

    # --- YENİ EKLENEN YEDEKLEME TABI ---
    with tab_backup:
        st.markdown("### 📥 Download Full Database Backup")
        st.info("This will download all worksheets (Users, Stats, Questions, Logs) as a single Excel file.")
        
        if st.button("Generate Backup File"):
            try:
                # Tüm sayfaları hafızaya çek
                with st.spinner("Reading all data from Google Sheets..."):
                    df_users = conn.read(worksheet="Users", ttl=0)
                    df_stats = conn.read(worksheet="User_Stats", ttl=0)
                    df_logs = conn.read(worksheet="Audit_Logs", ttl=0)
                    df_q_cissp = conn.read(worksheet="Questions", ttl=0)
                    # CISM sayfası yoksa hata vermesin diye try-except ile çekelim
                    try: df_q_cism = conn.read(worksheet="Questions_CISM", ttl=0)
                    except: df_q_cism = pd.DataFrame()

                # Excel dosyasını RAM'de oluştur (Diske kaydetmeden)
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_users.to_excel(writer, sheet_name='Users', index=False)
                    df_stats.to_excel(writer, sheet_name='User_Stats', index=False)
                    df_logs.to_excel(writer, sheet_name='Audit_Logs', index=False)
                    df_q_cissp.to_excel(writer, sheet_name='Questions', index=False)
                    if not df_q_cism.empty:
                        df_q_cism.to_excel(writer, sheet_name='Questions_CISM', index=False)
                
                # İndirme Butonunu Göster
                st.download_button(
                    label="⬇️ Click to Download Backup.xlsx",
                    data=buffer.getvalue(),
                    file_name=f"CyberMentor_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
                st.success("Backup generated! Click the button above to save.")
                
            except Exception as e:
                st.error(f"Backup failed: {e}")
