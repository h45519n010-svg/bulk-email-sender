import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
import zipfile
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="نِظَامُ الإِرْسَالِ المَالِيِّ الذَّكِيِّ", layout="wide", page_icon="📊")

# --- RTL SUPPORT & CUSTOM STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [data-testid="stSidebar"], .main {
        font-family: 'Tajawal', sans-serif;
        direction: RTL; text-align: right;
    }
    .stTextInput input, .stTextArea textarea, [data-testid="stSelectbox"], .stNumberInput input {
        direction: RTL; text-align: right;
    }
    .batch-config-card {
        padding: 15px;
        background-color: #f1f3f4;
        border-radius: 10px;
        border-right: 5px solid #1a73e8;
        margin-bottom: 10px;
    }
    .auto-dist-card {
        padding: 15px;
        background-color: #e8f0fe;
        border-radius: 10px;
        border-right: 5px solid #34a853;
        margin-bottom: 10px;
    }
    .timer-active {
        color: #d93025;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .info-box {
        background-color: #fff3cd;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #ffeeba;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'auto_times' not in st.session_state: st.session_state.auto_times = [datetime.now().time()]

def reset_all():
    st.session_state.logs = []
    st.session_state.is_running = False
    st.session_state.auto_times = [datetime.now().time()]

# --- CORE FUNCTIONS ---
def extract_emails(text):
    return re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)

def send_mail(server, sender, to, subject, body, atts, is_html):
    try:
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = sender, to, subject
        msg.attach(MIMEText(body, 'html' if is_html else 'plain'))
        for a in atts:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(a['content'])
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={a["name"]}')
            msg.attach(part)
        server.send_message(msg)
        return True, "Success"
    except Exception as e:
        return False, str(e)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔐 إِعْدَادَاتُ الحِسَابِ")
    u_mail = st.text_input("إِيمِيلُ Gmail", placeholder="example@gmail.com")
    u_pass = st.text_input("كَلِمَةُ مُرُورِ التَّطْبِيقِ", type="password")
    st.divider()
    if st.button("🗑️ مَسْحُ السِّجِلَّاتِ وَالجَدْوَلَةِ"):
        reset_all()
        st.rerun()

# --- MAIN INTERFACE ---
st.title("📊 نِظَامُ الإِرْسَالِ الذَّكِيِّ")

t1, t2, t3 = st.tabs(["📂 مَصَادِرُ البَيَانَاتِ", "📝 التَّصْمِيمُ", "🚀 جَدْوَلَةُ الدَّفَعَاتِ المَفْتُوحَةِ"])

with t1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ قَائِمَةُ المُسْتَلِمِينَ")
        file = st.file_uploader("رَفْعُ مَلَفِّ Excel أَوْ CSV", type=['xlsx', 'csv'])
        manual_text = st.text_area("أَوْ أَضِفِ الإِيمِيلَاتِ هُنَا", height=100)
    with col2:
        st.subheader("2️⃣ المُرْفَقَاتُ")
        zip_file = st.file_uploader("ارْفَعْ مَلَفَّ ZIP لِلْمُرْفَقَاتِ المُخَصَّصَةِ", type=['zip'])

    final_df = pd.DataFrame()
    if file:
        final_df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    if manual_text:
        found = extract_emails(manual_text)
        if found:
            m_df = pd.DataFrame(found, columns=['البريد'])
            m_df['الاسم'] = "عَمِيلَنَا العَزِيزُ"
            final_df = pd.concat([final_df, m_df], ignore_index=True)

    if not final_df.empty:
        st.success(f"تَمَّ اكْتِشَافُ {len(final_df)} مُسْتَلِمٍ.")
        e_col = st.selectbox("اخْتَرْ عَمُودَ البَرِيدِ", final_df.columns)
        n_col = st.selectbox("اخْتَرْ عَمُودَ الاسْمِ (اختياري)", [None] + list(final_df.columns))

with t2:
    subj = st.text_input("مَوْضُوعُ البَرِيدِ")
    m_mode = st.radio("التَّنْسِيقُ", ["نَصٌّ عَادِيٌّ", "HTML"], horizontal=True)
    msg_body = st.text_area("نَصُّ الرِّسَالَةِ (اسْتَخْدِمْ {name} لِالتَّخْصِيصِ)", height=200)
    general_atts = st.file_uploader("المُرْفَقَاتُ العَامَّةُ", accept_multiple_files=True)

with t3:
    if not final_df.empty:
        st.subheader("⏱️ إِضَافَةُ مَوَاعِيدِ الدَّفَعَاتِ (تَوْزِيعٌ تِلْقَائِيٌّ)")
        st.markdown("""
        <div class="info-box">
        💡 <b>كَيْفَ تَعْمَلُ؟</b> أَضِفْ أَيَّ عَدَدٍ مِنَ المَوَاعِيدِ. سَيَقُومُ النِّظَامُ بِتَقْسِيمِ الـ {total} إِيمِيل تِلْقَائِيّاً عَلَى هَذِهِ المَوَاعِيدِ بِالتَّسَاوِي.
        </div>
        """.format(total=len(final_df)), unsafe_allow_html=True)
        
        # إضافة مواعيد جديدة
        if st.button("➕ إِضَافَةُ مَوْعِدِ دَفْعَةٍ جَدِيدٍ"):
            st.session_state.auto_times.append(datetime.now().time())
        
        updated_times = []
        for idx, t_val in enumerate(st.session_state.auto_times):
            with st.container():
                st.markdown(f'<div class="auto-dist-card">🕒 <b>مَوْعِدُ الدَّفْعَةِ {idx+1} (عَدَدٌ تِلْقَائِيٌّ)</b></div>', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1])
                new_t = c1.time_input(f"الوَقْتُ", t_val, key=f"at_{idx}")
                if c2.button("🗑️ حَذْفٌ", key=f"ad_{idx}"):
                    st.session_state.auto_times.pop(idx)
                    st.rerun()
                updated_times.append(new_t)
        
        st.session_state.auto_times = updated_times
        
        # حساب التوزيع التلقائي للعرض فقط
        num_slots = len(st.session_state.auto_times)
        if num_slots > 0:
            avg = len(final_df) // num_slots
            rem = len(final_df) % num_slots
            st.info(f"📊 السِّرَاعَةُ الحَالِيَّةُ: **{num_slots}** دَفْعَةٍ | كُلُّ دَفْعَةٍ سَتُرْسِلُ حَوَالَيْ **{avg}** إِيمِيل.")

        inter_delay = st.slider("التَّأْخِيرُ بَيْنَ الرَّسَائِلِ دَاخِلَ الدَّفْعَةِ (ثَوَانٍ):", 0, 20, 2)

        if st.button("🚀 بَدْءُ جَدْوَلَةِ الإِرْسَالِ", type="primary", use_container_width=True):
            st.session_state.is_running = True
            
            # تجهيز المرفقات الذكية
            custom_map = {}
            if zip_file:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    for n in z.namelist(): custom_map[n.split('.')[0]] = {"name": n, "content": z.read(n)}

            current_row = 0
            p_bar = st.progress(0.0)
            status_placeholder = st.empty()

            try:
                # التنفيذ بناءً على المواعيد المضافة
                for b_idx, target_time_val in enumerate(st.session_state.auto_times):
                    # حساب حجم الدفعة الحالية
                    current_batch_size = avg + (1 if b_idx < rem else 0)
                    
                    target_dt = datetime.combine(datetime.today(), target_time_val)
                    
                    # انتظار موعد الدفعة
                    while datetime.now() < target_dt:
                        remaining = int((target_dt - datetime.now()).total_seconds())
                        status_placeholder.markdown(f'<div class="batch-config-card">🕒 <b>الدَّفْعَةُ {b_idx+1}:</b> فِي حَالَةِ انْتِظَارٍ... <span class="timer-active">{remaining}</span> ثَانِيَة لِلانْطِلَاقِ.</div>', unsafe_allow_html=True)
                        time.sleep(1)
                        if not st.session_state.is_running: break
                    
                    if not st.session_state.is_running: break

                    status_placeholder.info(f"🚀 جَارِي تَنْفِيذُ الدَّفْعَةِ {b_idx+1} ({current_batch_size} رِسَالَة)...")
                    
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(u_mail, u_pass)

                    end_point = min(current_row + current_batch_size, len(final_df))
                    for i in range(current_row, end_point):
                        row = final_df.iloc[i]
                        addr = str(row[e_col]).strip()
                        nm = str(row[n_col]) if n_col else "عَمِيلَنَا العَزِيزُ"
                        f_body = msg_body.replace("{name}", nm)
                        
                        atts = []
                        for ga in general_atts:
                            atts.append({"name": ga.name, "content": ga.read()})
                            ga.seek(0)
                        
                        if addr in custom_map: atts.append(custom_map[addr])
                        elif addr.split('@')[0] in custom_map: atts.append(custom_map[addr.split('@')[0]])

                        ok, info = send_mail(server, u_mail, addr, subj, f_body, atts, (m_mode=="HTML"))
                        st.session_state.logs.append({"مَوْعِدُ الدَّفْعَةِ": target_time_val.strftime('%H:%M'), "المُسْتَلِمُ": addr, "الحَالَةُ": "✅" if ok else "❌", "التَّفَاصِيلُ": info})
                        
                        current_row += 1
                        p_bar.progress(current_row / len(final_df))
                        time.sleep(inter_delay)
                    
                    server.quit()
                
                st.success("✨ تَمَّ الِانْتِهَاءُ مِنْ كَافَّةِ الدَّفَعَاتِ المَجْدُولَةِ بِنَجَاحٍ.")
            except Exception as e:
                st.error(f"❌ خَطَأٌ تَقْنِيٌّ: {str(e)}")

        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تَقْرِيرُ الإِرْسَالِ المُرَتَّبِ")
            st.table(pd.DataFrame(st.session_state.logs).tail(20))
