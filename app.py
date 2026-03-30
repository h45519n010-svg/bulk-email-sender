import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="نظام الارسال الذكي", layout="wide", page_icon="🚀")

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
    .status-card {
        padding: 20px;
        background-color: #f8f9fa;
        border-radius: 10px;
        border-right: 5px solid #1a73e8;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'is_paused' not in st.session_state: st.session_state.is_paused = False
if 'current_index' not in st.session_state: st.session_state.current_index = 0

def reset_process():
    st.session_state.logs = []
    st.session_state.is_running = False
    st.session_state.is_paused = False
    st.session_state.current_index = 0

# --- CORE FUNCTIONS ---
def extract_emails(text):
    return re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)

def smart_detect_columns(columns):
    detected = {"email": None, "name": None, "phone": None}
    keys = {
        "email": ['email', 'mail', 'البريد', 'ايميل'],
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
        return True, "تم الارسال"
    except Exception as e:
        return False, str(e)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔐 الاعدادات")
    u_mail = st.text_input("ايميل Gmail", placeholder="example@gmail.com")
    u_pass = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    if st.button("🗑️ مسح السجلات والبيانات"):
        reset_process()
        st.rerun()

# --- MAIN ---
st.title("🚀 نظام الارسال الفوري")

t1, t2 = st.tabs(["📂 مصادر البيانات", "📝 تصميم الرسالة والتحكم"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        file = st.file_uploader("رفع ملف المستلمين (Excel/CSV)", type=['xlsx', 'csv'])
        manual_text = st.text_area("او اضافة ايميلات يدويا", height=100)
    with c2:
        zip_file = st.file_uploader("مرفقات مخصصة (ZIP)", type=['zip'])

    df = pd.DataFrame()
    if file:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    if manual_text:
        found = extract_emails(manual_text)
        if found:
            m_df = pd.DataFrame(found, columns=['البريد'])
            m_df['الاسم'] = "عميلنا العزيز"
            df = pd.concat([df, m_df], ignore_index=True)

    if not df.empty:
        det = smart_detect_columns(df.columns)
        sc1, sc2, sc3 = st.columns(3)
        e_col = sc1.selectbox("عمود البريد", df.columns, index=list(df.columns).index(det["email"]) if det["email"] else 0)
        n_col = sc2.selectbox("عمود الاسم", [None] + list(df.columns), index=list(df.columns).index(det["name"]) + 1 if det["name"] else 0)
        p_col = sc3.selectbox("عمود الجوال", [None] + list(df.columns), index=list(df.columns).index(det["phone"]) + 1 if det["phone"] else 0)

with t2:
    subj = st.text_input("موضوع الرسالة")
    m_mode = st.radio("تنسيق الرسالة", ["نص عادي", "HTML"], horizontal=True)
    msg_body = st.text_area("نص الرسالة (استخدم {name} للاسم و {phone} للجوال)", height=150)
    gen_atts = st.file_uploader("مرفقات عامة لجميع الرسائل", accept_multiple_files=True)
    
    st.divider()
    
    if not df.empty:
        delay = st.slider("التاخير بين كل رسالة (ثانية)", 0, 20, 2)
        
        # --- CONTROL BUTTONS ---
        col_start, col_pause, col_stop = st.columns(3)
        
        start_btn = col_start.button("▶️ بدء / استئناف الارسال", use_container_width=True, type="primary")
        pause_btn = col_pause.button("⏸️ توقف مؤقت", use_container_width=True)
        stop_btn = col_stop.button("⏹️ ايقاف نهائي", use_container_width=True)

        if pause_btn:
            st.session_state.is_paused = True
            st.warning("تم تعليق العملية مؤقتا")
        
        if stop_btn:
            st.session_state.is_running = False
            st.session_state.is_paused = False
            st.error("تم ايقاف العملية نهائيا")
            st.rerun()

        if start_btn:
            st.session_state.is_running = True
            st.session_state.is_paused = False
            
            # تجهيز المرفقات المخصصة
            custom_map = {}
            if zip_file:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    for n in z.namelist(): custom_map[n.split('.')[0]] = {"name": n, "content": z.read(n)}

            p_bar = st.progress(st.session_state.current_index / len(df))
            status_txt = st.empty()

            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(u_mail, u_pass)

                # حلقة الارسال التي تدعم الاستئناف والتوقف
                while st.session_state.current_index < len(df) and st.session_state.is_running:
                    if st.session_state.is_paused:
                        status_txt.info(f"تم التوقف عند الرقم: {st.session_state.current_index}")
                        break
                    
                    row = df.iloc[st.session_state.current_index]
                    addr = str(row[e_col]).strip()
                    nm = str(row[n_col]) if n_col else "عميلنا"
                    ph = str(row[p_col]) if p_col else ""
                    
                    # تخصيص الرسالة
                    f_body = msg_body.replace("{name}", nm).replace("{phone}", ph)
                    
                    # المرفقات
                    atts = []
                    for ga in gen_atts:
                        atts.append({"name": ga.name, "content": ga.read()})
                        ga.seek(0)
                    
                    if addr in custom_map: atts.append(custom_map[addr])
                    elif addr.split('@')[0] in custom_map: atts.append(custom_map[addr.split('@')[0]])

                    # الارسال الفعلي
                    ok, info = send_mail(server, u_mail, addr, subj, f_body, atts, (m_mode=="HTML"))
                    
                    st.session_state.logs.append({
                        "الرقم": st.session_state.current_index + 1,
                        "المستلم": addr,
                        "الحالة": "✅" if ok else "❌",
                        "التفاصيل": info
                    })
                    
                    st.session_state.current_index += 1
                    p_bar.progress(st.session_state.current_index / len(df))
                    status_txt.text(f"جاري الارسال: {st.session_state.current_index} / {len(df)}")
                    
                    time.sleep(delay)
                
                server.quit()
                if st.session_state.current_index >= len(df):
                    st.success("تم الانتهاء من كامل القائمة بنجاح")
                    st.session_state.is_running = False
            
            except Exception as e:
                st.error(f"خطا في الاتصال: {e}")

        # عرض النتائج
        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تقرير الارسال المباشر")
            st.dataframe(pd.DataFrame(st.session_state.logs).tail(50), use_container_width=True)
