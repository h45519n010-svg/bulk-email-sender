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
st.set_page_config(page_title="نِظَامُ الإِرْسَالِ المَالِيِّ الذَّكِيِّ", layout="wide", page_icon="🚀")

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
    .batch-card {
        padding: 12px;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        border-right: 5px solid #4285f4;
        margin-bottom: 8px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .timer-active {
        color: #d93025;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        background-color: #eee;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'scheduled_batches' not in st.session_state: st.session_state.scheduled_batches = []

def reset_all():
    st.session_state.logs = []
    st.session_state.is_running = False
    st.session_state.scheduled_batches = []

# --- CORE FUNCTIONS ---
def extract_emails(text):
    return re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)

def smart_detect_columns(columns):
    detected = {"email": None, "name": None, "phone": None}
    keys = {
        "email": ['email', 'mail', 'البريد', 'إيميل'],
        "name": ['name', 'الاسم', 'full name'],
        "phone": ['phone', 'mobile', 'جوال', 'الهاتف', 'whatsapp']
    }
    for col in columns:
        c_low = str(col).lower().strip()
        for k, words in keys.items():
            if any(w in c_low for w in words) and not detected[k]:
                detected[k] = col
    return detected

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
    st.title("🔐 الإِعْدَادَاتُ")
    u_mail = st.text_input("إِيمِيلُ Gmail", placeholder="example@gmail.com")
    u_pass = st.text_input("كَلِمَةُ مُرُورِ التَّطْبِيقِ", type="password")
    st.divider()
    if st.button("🗑️ مَسْحُ كُلِّ البَيَانَاتِ"):
        reset_all()
        st.rerun()

# --- MAIN ---
st.title("🚀 نِظَامُ الإِرْسَالِ المُطَوَّرُ")

t1, t2, t3 = st.tabs(["📂 المَصَادِرُ", "📝 التَّصْمِيمُ", "⏱️ الجَدْوَلَةُ الذَّكِيَّةُ"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        file = st.file_uploader("رَفْعُ مَلَفِّ المُسْتَلِمِينَ", type=['xlsx', 'csv'])
        manual_text = st.text_area("أَوْ إِضَافَةٌ يَدَوِيَّةٌ", height=100)
    with c2:
        zip_file = st.file_uploader("مُرْفَقَاتٌ مُخَصَّصَةٌ (ZIP)", type=['zip'])

    df = pd.DataFrame()
    if file:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    if manual_text:
        found = extract_emails(manual_text)
        if found:
            m_df = pd.DataFrame(found, columns=['البريد'])
            m_df['الاسم'] = "عَمِيلَنَا العَزِيزُ"
            df = pd.concat([df, m_df], ignore_index=True)

    if not df.empty:
        det = smart_detect_columns(df.columns)
        sc1, sc2, sc3 = st.columns(3)
        e_col = sc1.selectbox("عَمُودُ البَرِيدِ", df.columns, index=list(df.columns).index(det["email"]) if det["email"] else 0)
        n_col = sc2.selectbox("عَمُودُ الِاسْمِ", [None] + list(df.columns), index=list(df.columns).index(det["name"]) + 1 if det["name"] else 0)
        p_col = sc3.selectbox("عَمُودُ الجَوَّالِ", [None] + list(df.columns), index=list(df.columns).index(det["phone"]) + 1 if det["phone"] else 0)

with t2:
    subj = st.text_input("مَوْضُوعُ الرِّسَالَةِ")
    m_mode = st.radio("التَّنْسِيقُ", ["TEXT", "HTML"], horizontal=True)
    body = st.text_area("نَصُّ الرِّسَالَةِ ({name}, {phone})", height=200)
    gen_atts = st.file_uploader("مُرْفَقَاتٌ عَامَّةٌ", accept_multiple_files=True)

with t3:
    if not df.empty:
        st.subheader("🛠️ أَدَوَاتُ الجَدْوَلَةِ السَّرِيعَةِ")
        
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            st.markdown("**1. الجَدْوَلَةُ بِالفَاصِلِ الزَّمَنِيِّ (تِلْقَائِيٌّ)**")
            start_t = st.time_input("وَقْتُ بَدْءِ أَوَّلِ دُفْعَةٍ", datetime.now().time())
            interval = st.number_input("الفَاصِلُ الزَّمَنِيُّ بَيْنَ الدَّفَعَاتِ (بِالدَّقَائِقِ)", 1, 1440, 30)
            num_batches = st.number_input("عَدَدُ الدَّفَعَاتِ المُرَادُ تَوْلِيدُهَا", 1, 1000, 5)
            
            if st.button("🪄 تَوْلِيدُ الجَدْوَلِ تِلْقَائِيّاً", use_container_width=True):
                new_schedules = []
                base_dt = datetime.combine(datetime.today(), start_t)
                for i in range(num_batches):
                    target_time = (base_dt + timedelta(minutes=i * interval)).time()
                    new_schedules.append(target_time)
                st.session_state.scheduled_batches = new_schedules
                st.rerun()

        with g_col2:
            st.markdown("**2. إِضَافَةُ مَوَاعِيدَ خَاصَّةٍ (يَدَوِيٌّ)**")
            manual_time = st.time_input("اخْتَرْ وَقْتاً مُحَدَّداً", datetime.now().time())
            if st.button("➕ إِضَافَةُ هَذَا المَوْعِدِ", use_container_width=True):
                st.session_state.scheduled_batches.append(manual_time)
                st.rerun()

        st.divider()
        
        if st.session_state.scheduled_batches:
            st.subheader(f"📋 قَائِمَةُ الدَّفَعَاتِ المُرَتَّبَةِ ({len(st.session_state.scheduled_batches)})")
            
            # حساب الحجم التلقائي
            n_slots = len(st.session_state.scheduled_batches)
            avg = len(df) // n_slots
            rem = len(df) % n_slots

            cols = st.columns(3)
            for i, t_val in enumerate(st.session_state.scheduled_batches):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="batch-card">
                        <b>📦 دُفْعَة {i+1}</b><br>
                        ⏰ المَوْعِدُ: {t_val.strftime('%H:%M')}<br>
                        📧 العَدَدُ: {avg + (1 if i < rem else 0)}
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"❌ حَذْفُ {i+1}", key=f"del_{i}"):
                        st.session_state.scheduled_batches.pop(i)
                        st.rerun()

            st.divider()
            delay = st.slider("التَّأْخِيرُ بَيْنَ كُلِّ إِيمِيل (ثَانِيَة):", 0, 10, 2)

            if st.button("⚡ بَدْءُ التَّنْفِيذِ الكَامِلِ", type="primary", use_container_width=True):
                st.session_state.is_running = True
                
                custom_map = {}
                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        for n in z.namelist(): custom_map[n.split('.')[0]] = {"name": n, "content": z.read(n)}

                curr_row = 0
                p_bar = st.progress(0.0)
                status = st.empty()

                try:
                    for idx, t_val in enumerate(st.session_state.scheduled_batches):
                        batch_size = avg + (1 if idx < rem else 0)
                        target_dt = datetime.combine(datetime.today(), t_val)
                        
                        while datetime.now() < target_dt:
                            diff = int((target_dt - datetime.now()).total_seconds())
                            status.warning(f"⏳ الدَّفْعَةُ {idx+1}: جَارٍ الِانْتِظَارُ... بَقِيَ {diff} ثَانِيَة.")
                            time.sleep(1)
                            if not st.session_state.is_running: break
                        
                        if not st.session_state.is_running: break

                        status.info(f"🚀 جَارِي إِرْسَالُ الدَّفْعَةِ {idx+1}...")
                        server = smtplib.SMTP("smtp.gmail.com", 587)
                        server.starttls()
                        server.login(u_mail, u_pass)

                        for i in range(curr_row, curr_row + batch_size):
                            if i >= len(df): break
                            r = df.iloc[i]
                            to_addr = str(r[e_col]).strip()
                            f_body = body.replace("{name}", str(r[n_col]) if n_col else "عميلنا").replace("{phone}", str(r[p_col]) if p_col else "")
                            
                            atts = [{"name": a.name, "content": a.read()} for a in gen_atts]
                            for a in gen_atts: a.seek(0)
                            
                            prefix = to_addr.split('@')[0]
                            if to_addr in custom_map: atts.append(custom_map[to_addr])
                            elif prefix in custom_map: atts.append(custom_map[prefix])

                            ok, res = send_mail(server, u_mail, to_addr, subj, f_body, atts, m_mode=="HTML")
                            st.session_state.logs.append({"دُفْعَة": idx+1, "بَرِيد": to_addr, "حَالَة": "✅" if ok else "❌"})
                            
                            curr_row += 1
                            p_bar.progress(curr_row / len(df))
                            time.sleep(delay)
                        
                        server.quit()
                    st.success("✅ تَمَّ إِكْمَالُ كَافَّةِ الجَدْوَلَةِ.")
                except Exception as e:
                    st.error(f"❌ خَطَأٌ: {e}")

        if st.session_state.logs:
            st.subheader("📋 السِّجِلُّ")
            st.dataframe(pd.DataFrame(st.session_state.logs).tail(50), use_container_width=True)
