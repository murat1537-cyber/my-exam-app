import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. KONU TANIMLAMALARI ---
TOPIC_MAP = {
    "1": "Trafik ve Çevre Bilgisi",
    "2": "İlk Yardım Bilgisi",
    "3": "Araç Tekniği",
    "4": "Trafik Adabı",
    "5": "Trafik İşaretleri",
    "6": "Güvenli Sürüş Teknikleri",
    "7": "Motor Bilgisi",
    "8": "Genel Mevzuat"
}

# --- 2. TASARIM ---
st.set_page_config(page_title="AI Exam Mentor Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .explanation-box { background-color: #fff9db; padding: 15px; border-radius: 12px; border-left: 5px solid #fcc419; margin-top: 15px; color: #856404; }
    .timer-box { font-size: 20px; font-weight: bold; color: #d32f2f; text-align: center; background: #ffebee; border-radius: 10px; padding: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BAĞLANTI VE DURUM ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- 4. VERİ YAZMA VE RAPOR FONKSİYONLARI ---
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
        return True
    except Exception as e:
        st.error(f"Save error: {e}"); return False

def create_pdf_report(stats_df, questions_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Personal Performance & Error Analysis", ln=True, align='C')
    pdf.ln(10)
    
    # Veri Temizleme: 0/1 karmaşasını çöz
    stats_df['is_correct'] = stats_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})
    wrong_entries = stats_df[stats_df['is_correct'] == "FALSE"]
    
    pdf.set_font("Helvetica", "", 12)
    if wrong_entries.empty:
        pdf.cell(0, 10, "Harika! Kayıtlı bir hatanız bulunmuyor.", ln=True)
    else:
        for _, row in wrong_entries.iterrows():
            q_info = questions_df[questions_df['id'].astype(str) == str(row['question_id'])]
            if not q_info.empty:
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(180, 7, f"Soru: {q_info['content_text'].values[0]}")
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(180, 6, f"Dogru Cevap: {q_info['correct_option'].values[0]} | Hata Nedeni: {row['error_reason']}")
                pdf.ln(5)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(5)
                if pdf.get_y() > 250: pdf.add_page()
    return bytes(pdf.output())

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🏆 AI Mentor Pro")
    if st.button("🚀 Yeni Sprint Başlat"):
        q_df = conn.read(worksheet="Questions", ttl=0)
        st.session_state.smart_list = q_df.sample(frac=1).reset_index(drop=True)
        st.session_state.q_idx = 0; st.session_state.start_time = datetime.now()
        st.session_state.view = 'Study'; st.rerun()
    
    st.write("---")
    if st.button("📊 Gelişmiş Analizler"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Paneli"): st.session_state.view = 'Admin'

# --- 6. GÖRÜNÜMLER ---

# STUDY MODE (Şıklar ve Butonlar Geri Geldi!)
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() <= 0:
        st.session_state.view = 'Analytics'; st.rerun()
    st.markdown(f'<div class="timer-box">⏱️ Kalan Süre: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)

    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    topic_name = TOPIC_MAP.get(str(curr['topic_id']), "Genel")
    
    st.caption(f"📍 Konu: {topic_name}")
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    opts = [('A', 'option_a'), ('B', 'option_b'), ('C', 'option_c'), ('D', 'option_d')]
    for i, (code, col) in enumerate(opts):
        with (col1 if i % 2 == 0 else col2):
            if st.button(f"{code}) {curr[col]}", use_container_width=True):
                st.session_state.feedback = (code == curr['correct_option'])
                st.session_state.last_q_id = curr['id']

    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Doğru!")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("🎯 Eminim"): save_stat(st.session_state.last_q_id, True, "Sure", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if c2.button("🎲 Salladım"): save_stat(st.session_state.last_q_id, True, "Guessed", "None"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
        else:
            st.error(f"❌ Yanlış! Doğru Cevap: {curr['correct_option']}")
            if 'explanation' in curr: st.markdown(f'<div class="explanation-box"><b>AI Mentor:</b> {curr["explanation"]}</div>', unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            if r1.button("Bilgi Eksikliği"): save_stat(st.session_state.last_q_id, False, "None", "Bilgi Eksikliği"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r2.button("Dikkat Hatası"): save_stat(st.session_state.last_q_id, False, "None", "Dikkat Hatası"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            if r3.button("Yorum Hatası"): save_stat(st.session_state.last_q_id, False, "None", "Yorum Hatası"); st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()

    st.write("---")
    if st.button("⬅️ Önceki Soru") and st.session_state.q_idx > 0:
        st.session_state.q_idx -= 1; st.session_state.feedback = None; st.rerun()

# ANALYTICS (Topic İsimleri Düzeldi!)
elif st.session_state.view == 'Analytics':
    st.header("📊 Performans Özetim")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty and not questions.empty:
        # Veri Temizleme ve Birleştirme
        stats['question_id'] = stats['question_id'].astype(float).astype(int).astype(str)
        questions['id'] = questions['id'].astype(float).astype(int).astype(str)
        merged = pd.merge(stats, questions[['id', 'topic_id']], left_on='question_id', right_on='id')
        
        # Topic ID -> İsim Dönüşümü
        merged['Konu'] = merged['topic_id'].astype(str).map(TOPIC_MAP).fillna("Diger")
        merged['is_correct'] = merged['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE', '0.0':'FALSE', '1.0':'TRUE'})

        col_pie, col_bar = st.columns([1, 2])
        with col_pie:
            st.plotly_chart(px.pie(merged, names='is_correct', title="Genel Başarı", hole=0.4, color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'}))
            if st.button("Hata Analiz PDF'i İndir"):
                report = create_pdf_report(stats, questions)
                st.download_button("📥 PDF'i Al", data=report, file_name="analiz.pdf")
        
        with col_bar:
            topic_chart = px.bar(merged, x='Konu', color='is_correct', barmode='group', title="Konu Bazlı Başarı", color_discrete_map={'TRUE':'#2ecc71','FALSE':'#e74c3c'})
            st.plotly_chart(topic_chart, use_container_width=True)
    else:
        st.info("Henüz analiz edilecek veri yok.")

# ADMIN
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        pw = st.text_input("Yönetici Şifresi", type="password")
        if pw == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        uploaded = st.file_uploader("Soru Excel'ini Yükle", type=['xlsx'])
        if uploaded:
            new_q = pd.read_excel(uploaded)
            if st.button("Buluta Yükle"):
                old_q = conn.read(worksheet="Questions", ttl=0)
                conn.update(worksheet="Questions", data=pd.concat([old_q, new_q], ignore_index=True))
                st.success("Sorular Güncellendi!")
