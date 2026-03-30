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
# التأكد من بقاء المؤشر محفوظا بين عمليات التحديث
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
    if st.button("🗑️ مسح السجلات والبدء من جديد"):
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
        # عرض حالة التقدم الحالية
        st.info(f"الوضعية الحالية: تم إرسال {st.session_state.current_index} من أصل {len(df)}")
        
        delay = st.slider("التاخير بين كل رسالة (ثانية)", 0, 20, 2)
        
        # --- CONTROL BUTTONS ---
        col_start, col_pause, col_stop = st.columns(3)
        
        # تسمية الزر تتغير بناء على الحالة
        btn_label = "▶️ بدء الارسال" if st.session_state.current_index == 0 else "⏯️ استئناف الارسال"
        start_btn = col_start.button(btn_label, use_container_width=True, type="primary")
        pause_btn = col_pause.button("⏸️ توقف مؤقت", use_container_width=True)
        stop_btn = col_stop.button("⏹️ ايقاف نهائي", use_container_width=True)

        if pause_btn:
            st.session_state.is_paused = True
            st.session_state.is_running = False
            st.warning(f"تم تعليق العملية مؤقتا عند الرقم {st.session_state.current_index}")
        
        if stop_btn:
            reset_process()
            st.error("تم ايقاف العملية وتصفير العداد")
            st.rerun()

        if start_btn:
            if not u_mail or not u_pass:
                st.error("الرجاء ادخال بيانات الحساب في القائمة الجانبية")
            else:
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

                    # البدء من current_index يضمن عدم التكرار
                    for i in range(st.session_state.current_index, len(df)):
                        # التحقق من الضغط على توقف مؤقت داخل الحلقة
                        if not st.session_state.is_running or st.session_state.is_paused:
                            break
                        
                        row = df.iloc[i]
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
                            "الرقم": i + 1,
                            "المستلم": addr,
                            "الحالة": "✅" if ok else "❌",
                            "التفاصيل": info
                        })
                        
                        # تحديث المؤشر فوراً بعد كل عملية إرسال ناجحة أو فاشلة
                        st.session_state.current_index = i + 1
                        
                        # تحديث واجهة المستخدم
                        p_bar.progress(st.session_state.current_index / len(df))
                        status_txt.text(f"جاري الارسال: {st.session_state.current_index} / {len(df)}")
                        
                        time.sleep(delay)
                    
                    server.quit()
                    
                    if st.session_state.current_index >= len(df):
                        st.success("تم الانتهاء من كامل القائمة بنجاح")
                        st.session_state.is_running = False
                        st.balloons()
                    else:
                        st.warning(f"تم التوقف مؤقتاً. يمكنك الاستئناف من الرقم {st.session_state.current_index}")

                except Exception as e:
                    st.error(f"حدث خطأ أثناء الارسال: {e}")
                    st.session_state.is_running = False

        # عرض النتائج
        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تقرير الارسال المباشر")
            st.dataframe(pd.DataFrame(st.session_state.logs).tail(50), use_container_width=True)
