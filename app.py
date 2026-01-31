import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF

# --- 1. GÜVENLİK VE TASARIM ---
st.set_page_config(page_title="Secure Exam Master", layout="wide")

st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .main { background-color: #f8f9fa; }
    .q-card { background: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; margin-bottom: 20px; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; padding: 10px; background: #ffebee; border-radius: 10px; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; height: 3.5em; font-weight: 600; font-size: 16px; }
    .watermark { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-45deg); font-size: 40px; color: rgba(0, 0, 0, 0.03); z-index: 1000; pointer-events: none; }
    </style>
    <div class="watermark">CONFIDENTIAL - SECURE EXAM</div>
    """, unsafe_allow_html=True)

# --- 2. BAĞLANTI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Secrets hatası! Lütfen TOML formatını kontrol edin.")
    st.stop()

# --- 3. OTURUM DURUMLARI ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Study'
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'smart_list' not in st.session_state: st.session_state.smart_list = None
if 'start_time' not in st.session_state: st.session_state.start_time = None

# --- 4. GÜVENLİ VERİ YAZMA FONKSİYONU (DÜZELTİLDİ) ---
def save_stat(q_id, correct, confidence, reason):
    try:
        # Mevcut veriyi oku
        existing_data = conn.read(worksheet="User_Stats")
        
        # Yeni satırı hazırla
        new_row = pd.DataFrame([{
            "user_id": "User_01",
            "question_id": str(q_id),
            "is_correct": bool(correct),
            "confidence_level": str(confidence),
            "error_reason": str(reason) if reason else "None",
            "attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        
        # Mevcut verinin altına ekle ve sayfayı GÜNCELLE (Create yerine Update/Update_worksheet mantığı)
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="User_Stats", data=updated_df)
        return True
    except Exception as e:
        st.error(f"⚠️ Yazma Hatası: {e}")
        return False

# --- 5. PDF RAPOR FONKSİYONU ---
def create_pdf(results_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Exam Performance Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    total = len(results_df)
    correct = results_df['is_correct'].astype(bool).sum()
    pdf.cell(200, 10, f"Total Questions Solved: {total}", ln=True)
    pdf.cell(200, 10, f"Correct Answers: {correct}", ln=True)
    pdf.cell(200, 10, f"Accuracy: %{(correct/total)*100 if total > 0 else 0:.2f}", ln=True)
    return pdf.output()

# --- 6. NAVİGASYON ---
with st.sidebar:
    st.title("🏆 Control Center")
    if st.button("📝 Start 10-Min Sprint"):
        try:
            all_questions = conn.read(worksheet="Questions")
            if not all_questions.empty:
                st.session_state.smart_list = all_questions.sample(frac=1).reset_index(drop=True)
                st.session_state.q_idx = 0
                st.session_state.view = 'Study'
                st.session_state.start_time = datetime.now()
                st.rerun()
        except Exception:
            st.error("'Questions' sayfası bulunamadı!")
            
    if st.button("📊 Performance Analytics"):
        st.session_state.view = 'Analytics'

# --- 7. ÇALIŞMA MODU ---
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    if st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        remaining = timedelta(minutes=10) - elapsed
        if remaining.total_seconds() > 0:
            st.markdown(f'<div class="timer-box">⏱️ Time Left: {str(remaining).split(".")[0]}</div>', unsafe_allow_html=True)
        else:
            st.warning("Süre doldu!")
            st.session_state.view = 'Analytics'
            st.rerun()

    df = st.session_state.smart_list
    if st.session_state.q_idx < len(df):
        curr = df.iloc[st.session_state.q_idx]
        st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"A) {curr['option_a']}", use_container_width=True): st.session_state.feedback = ('A' == curr['correct_option']); st.session_state.last_q_id = curr['id']
            if st.button(f"C) {curr['option_c']}", use_container_width=True): st.session_state.feedback = ('C' == curr['correct_option']); st.session_state.last_q_id = curr['id']
        with col2:
            if st.button(f"B) {curr['option_b']}", use_container_width=True): st.session_state.feedback = ('B' == curr['correct_option']); st.session_state.last_q_id = curr['id']
            if st.button(f"D) {curr['option_d']}", use_container_width=True): st.session_state.feedback = ('D' == curr['correct_option']); st.session_state.last_q_id = curr['id']

        if st.session_state.feedback is not None:
            if st.session_state.feedback:
                st.success("✅ Doğru!")
                c1, c2 = st.columns(2)
                if c1.button("🎯 Eminim"): 
                    if save_stat(st.session_state.last_q_id, True, "Sure", None):
                        st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if c2.button("🎲 Tahmin"): 
                    if save_stat(st.session_state.last_q_id, True, "Guessed", None):
                        st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
            else:
                st.error(f"❌ Yanlış! Doğru cevap: {curr['correct_option']}")
                r1, r2, r3 = st.columns(3)
                if r1.button("Bilgi Eksikliği"): 
                    if save_stat(st.session_state.last_q_id, False, None, "Knowledge Gap"):
                        st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r2.button("Dikkat Hatası"): 
                    if save_stat(st.session_state.last_q_id, False, None, "Attention"):
                        st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
                if r3.button("Yorum Hatası"): 
                    if save_stat(st.session_state.last_q_id, False, None, "Interpretation"):
                        st.session_state.q_idx += 1; st.session_state.feedback = None; st.rerun()
    else:
        st.success("Seans tamamlandı!")

# --- 8. ANALİZ ---
elif st.session_state.view == 'Analytics':
    st.header("📊 Başarı Durumun")
    try:
        stats = conn.read(worksheet="User_Stats")
        if not stats.empty:
            fig = px.pie(stats, names='is_correct', title="Doğruluk Oranı", hole=0.4)
            st.plotly_chart(fig)
            
            if st.button("Rapor Oluştur (PDF)"):
                pdf_bytes = create_pdf(stats)
                st.download_button("📥 İndir", data=pdf_bytes, file_name="rapor.pdf", mime="application/pdf")
        else:
            st.info("Henüz veri yok.")
    except Exception:
        st.error("'User_Stats' yüklenemedi.")
else:
    st.info("Sınava başlamak için soldaki butonu kullanın!")
