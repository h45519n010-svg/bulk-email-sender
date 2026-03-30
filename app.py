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

# --- تهيئة الصفحة ---
st.set_page_config(page_title="نظام الارسال الاحترافي", layout="wide", page_icon="📧")

# --- تنسيق واجهة البرنامج (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [data-testid="stSidebar"], .main {
        font-family: 'Tajawal', sans-serif;
        direction: RTL; text-align: right;
    }
    .stTextInput input, .stTextArea textarea, [data-testid="stSelectbox"] {
        direction: RTL; text-align: right;
    }
    </style>
    """, unsafe_allow_html=True)

# --- إدارة حالة الجلسة ---
if 'logs' not in st.session_state: st.session_state.logs = []
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'current_index' not in st.session_state: st.session_state.current_index = 0

def reset_process():
    st.session_state.logs = []
    st.session_state.is_running = False
    st.session_state.current_index = 0

# --- وظائف الجوهر ---
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

def wrap_html_rtl(content):
    """تغليف محتوى الرسالة بتنسيق HTML يضمن المحاذاة لليمين"""
    return f"""
    <div dir="rtl" style="text-align: right; font-family: 'Tahoma', 'Arial', sans-serif; line-height: 1.6; color: #333;">
        {content.replace('\n', '<br>')}
    </div>
    """

def send_mail(server, sender, to, subject, body, atts, is_html):
    try:
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = sender, to, subject
        
        formatted_body = wrap_html_rtl(body)
        msg.attach(MIMEText(formatted_body, 'html'))
        
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

# --- القائمة الجانبية ---
with st.sidebar:
    st.title("🔐 بيانات الحساب")
    u_mail = st.text_input("ايميل Gmail")
    u_pass = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    if st.button("🗑️ تصفير النظام والبدء من جديد"):
        reset_process()
        st.rerun()

# --- الواجهة الرئيسية ---
st.title("🚀 مرسل البريد المنسق")

t1, t2 = st.tabs(["📂 رفع البيانات", "📝 التحكم والارسال"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        file = st.file_uploader("رفع ملف Excel/CSV", type=['xlsx', 'csv'])
        manual_text = st.text_area("اضافة يدوية", height=100)
    with c2:
        zip_file = st.file_uploader("ملفات ZIP مخصصة", type=['zip'])

    df = pd.DataFrame()
    if file:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    if manual_text:
        found = extract_emails(manual_text)
        if found:
            df = pd.DataFrame(found, columns=['البريد'])
            df['الاسم'] = "عميلنا العزيز"

    if not df.empty:
        det = smart_detect_columns(df.columns)
        sc1, sc2, sc3 = st.columns(3)
        e_col = sc1.selectbox("عمود البريد", df.columns, index=list(df.columns).index(det["email"]) if det["email"] else 0)
        n_col = sc2.selectbox("عمود الاسم", [None] + list(df.columns), index=list(df.columns).index(det["name"]) + 1 if det["name"] else 0)
        p_col = sc3.selectbox("عمود الجوال", [None] + list(df.columns), index=list(df.columns).index(det["phone"]) + 1 if det["phone"] else 0)

with t2:
    subj = st.text_input("عنوان الرسالة")
    msg_body = st.text_area("محتوى الرسالة (يدعم {name} و {phone})", height=200)
    gen_atts = st.file_uploader("مرفقات عامة", accept_multiple_files=True)
    
    if not df.empty:
        # حساب نسبة التقدم بأمان لتجنب خطأ StreamlitAPIException
        progress_val = min(float(st.session_state.current_index) / len(df), 1.0)
        st.info(f"حالة الارسال: تم إرسال {st.session_state.current_index} من {len(df)}")
        
        delay = st.slider("فاصل زمني (ثانية)", 0, 10, 2)
        
        col_start, col_pause = st.columns(2)
        start_btn = col_start.button("▶️ بدء / استئناف الارسال", use_container_width=True, type="primary")
        pause_btn = col_pause.button("⏸️ توقف مؤقت", use_container_width=True)

        if pause_btn:
            st.session_state.is_running = False
            st.warning("تم إيقاف التشغيل.. سيتوقف النظام بعد الرسالة الحالية.")

        if start_btn:
            if not u_mail or not u_pass:
                st.error("لطفا أدخل بيانات الايميل في القائمة الجانبية")
            elif st.session_state.current_index >= len(df):
                st.warning("تم إرسال كافة الرسائل بالفعل. قم بتصفير النظام للبدء من جديد.")
            else:
                st.session_state.is_running = True
                
                custom_map = {}
                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        for n in z.namelist(): custom_map[n.split('.')[0]] = {"name": n, "content": z.read(n)}

                status_txt = st.empty()
                p_bar = st.progress(progress_val)

                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(u_mail, u_pass)

                    for i in range(st.session_state.current_index, len(df)):
                        if not st.session_state.is_running: 
                            break
                        
                        row = df.iloc[i]
                        addr = str(row[e_col]).strip()
                        nm = str(row[n_col]) if n_col else "عميلنا"
                        ph = str(row[p_col]) if p_col else ""
                        
                        f_body = msg_body.replace("{name}", nm).replace("{phone}", ph)
                        
                        atts = []
                        for ga in gen_atts:
                            atts.append({"name": ga.name, "content": ga.read()})
                            ga.seek(0)
                        
                        prefix = addr.split('@')[0]
                        if addr in custom_map: atts.append(custom_map[addr])
                        elif prefix in custom_map: atts.append(custom_map[prefix])

                        ok, info = send_mail(server, u_mail, addr, subj, f_body, atts, True)
                        
                        st.session_state.logs.append({
                            "م": i + 1, "المستلم": addr, "الحالة": "✅" if ok else "❌"
                        })
                        
                        st.session_state.current_index = i + 1
                        # تحديث شريط التقدم مع التأكد من عدم تجاوز القيمة 1.0
                        new_progress = min(float(st.session_state.current_index) / len(df), 1.0)
                        p_bar.progress(new_progress)
                        status_txt.text(f"جاري الارسال: {st.session_state.current_index} / {len(df)}")
                        
                        time.sleep(delay)
                    
                    server.quit()
                    if st.session_state.current_index >= len(df):
                        st.success("اكتمل الارسال لجميع القائمة")
                        st.session_state.is_running = False
                
                except Exception as e:
                    st.error(f"خطأ في الاتصال أو الإرسال: {e}")
                    st.session_state.is_running = False

        if st.session_state.logs:
            st.divider()
            st.dataframe(pd.DataFrame(st.session_state.logs).tail(20), use_container_width=True)
