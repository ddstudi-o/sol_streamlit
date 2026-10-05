import streamlit as st
from openai import OpenAI
import logging
import requests
import re
import time
from urllib.parse import urlparse

# ==========================================
# 0. PYTHON-КАЛЬКУЛЯТОР
# ==========================================
def calculate_solar_investment(user_text: str) -> dict | None:
    pattern = r'(\d[\d\s]*)\s*(?:руб|рублей|руб\.|р\.|р\b)'
    match = re.search(pattern, user_text, re.IGNORECASE)
    if match:
        bill_amount = float(match.group(1).replace(" ", ""))
        COMMERCIAL_TARIFF = 9.0
        PRICE_PER_KWT = 85000
        estimated_kwh = round(bill_amount / COMMERCIAL_TARIFF)
        required_power_kw = round(estimated_kwh / 300, 1) 
        required_power_kw = max(3.0, min(required_power_kw, 50.0))
        estimated_cost = round(required_power_kw * PRICE_PER_KWT)
        return {
            "bill_amount": int(bill_amount),
            "estimated_kwh": estimated_kwh,
            "required_power_kw": required_power_kw,
            "estimated_cost": estimated_cost
        }
    return None

# ==========================================
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ И БЕЗОПАСНОСТИ
# ==========================================
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class TokenFilter(logging.Filter):
    def filter(self, record):
        msg = str(record.msg)
        msg = re.sub(r'bot\d+:[A-Za-z0-9_-]+', 'bot***:***', msg)
        msg = re.sub(r'sk-[A-Za-z0-9_-]{10,}', 'sk-***', msg)
        msg = re.sub(r'ghp_[A-Za-z0-9_-]{10,}', 'ghp_***', msg)
        record.msg = msg
        return True

logger.addFilter(TokenFilter())

def escape_html(text: str) -> str:
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def validate_lead(name: str, phone: str) -> tuple:
    name = name.strip()
    phone = phone.strip()
    if not name or len(name) < 2:
        return False, "Имя слишком короткое"
    if len(name) > 50:
        return False, "Имя слишком длинное"
    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s\-\.']+$", name):
        return False, "Недопустимые символы"
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
    if not re.match(r'^(\+?7|8)\d{10}$', phone_clean):
        return False, "Некорректный формат телефона"
    return True, phone_clean

def is_injection_attempt(text: str) -> bool:
    patterns = [
        r"(?i)игнорируй\s+(все\s+)?(предыдущие|выше)?\s*инструкци",
        r"(?i)покажи\s+(системный\s+)?промпт",
        r"(?i)repeat\s+(the\s+)?(system|initial)\s+(prompt|message)",
        r"(?i)(разкрой|расскажи|выведи)\s+(секрет|инструкци|промпт)",
        r"(?i)забудь\s+(все\s+)?(инструкци|правила)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in ["gist.githubusercontent.com", "api.github.com"]
    except:
        return False

# ==========================================
# 2. КАСТОМНЫЙ CSS
# ==========================================
st.markdown("""
<style>
section[data-testid="stSidebar"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color: white !important;
    font-weight: 500;
}
div[data-baseweb="popover"] *, 
div[data-baseweb="select"] *,
section[data-testid="stSidebar"] .stButton > button {
    color: #333333 !important;
    font-weight: 600 !important;
}

div[data-testid="column"]:nth-of-type(1),
div[data-testid="column"]:nth-of-type(2) {
    min-height: 650px; max-height: 650px; overflow-y: auto; overflow-x: hidden;
    border-radius: 15px; padding: 20px; position: relative;
}
div[data-testid="column"]:nth-of-type(1) { background-color: #fff9e6; border: 2px solid #ffe58f; }
div[data-testid="column"]:nth-of-type(2) { background-color: #e6fffa; border: 2px solid #b2f5ea; }

div[data-testid="column"]::-webkit-scrollbar { width: 8px; }
div[data-testid="column"]::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); border-radius: 10px; }
div[data-testid="column"]::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.3); border-radius: 10px; }

.section-title-lead { 
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
    color: white; padding: 12px; border-radius: 8px; text-align: center; 
    font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
}

div[data-testid="stChatMessage"]:has(div[role="presentation"]) {
    border-radius: 15px; padding: 15px; margin-bottom: 15px;
}
div[data-testid="stChatMessage"]:nth-child(odd) {
    background-color: #fff3cd !important; border: 2px solid #ffc107 !important;
}
div[data-testid="stChatMessage"]:nth-child(even) {
    background-color: #d4edda !important; border: 2px solid #28a745 !important;
}

@keyframes slideUpFade { 0% { opacity: 0; transform: translateY(30px); } 100% { opacity: 1; transform: translateY(0); } }
div[data-testid="stChatMessage"] { animation: slideUpFade 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.thinking-indicator { display: inline-block; animation: pulse 1.5s ease-in-out infinite; color: #666; font-style: italic; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. НАСТРОЙКА СТРАНИЦЫ И ИНИЦИАЛИЗАЦИЯ
# ==========================================
st.set_page_config(page_title="Sol — ИИ Консультант v2", page_icon="☀️", layout="wide")
st.title("☀️ Интеллектуальный расчет солнечных станций")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Здравствуйте! ☀️ Я ИИ-консультант Sol. Для быстрого уточнения деталей по расчету вашей станции ответьте на вопросы в левом блоке. Выберите задачу (Экономия или Отключения) и заполните параметры — я автоматически проанализирую вашу конфигурацию и дам рекомендации!"}
    ]

if "last_calc_sent" not in st.session_state:
    st.session_state.last_calc_sent = None

if "app_type" not in st.session_state:
    st.session_state.app_type = None

# ==========================================
# 4. ЛЕВАЯ ПАНЕЛЬ (ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР)
# ==========================================
with st.sidebar:
    st.markdown("### 📋 Параметры для расчета")
    
    app_type = st.selectbox(
        "Какая главная задача?",
        ["Просто задать вопрос", "Экономия бюджета (Сетевая СЭС)", "Защита от отключений / Резерв (Гибридная СЭС)"]
    )
    
    calc_summary = "Параметры не выбраны"
    recommended_power = 0
    estimated_cost = 0
    roi_years = 0
    selected_region = "Не указан"
    
    if app_type == "Экономия бюджета (Сетевая СЭС)":
        st.write("---")
        region_coefs = {"Краснодарский край (Юг)": 1.35, "Москва и МО (Центр)": 1.0, "Новосибирск (Сибирь)": 1.15}
        selected_region = st.selectbox("📍 Ваш город / регион:", list(region_coefs.keys()))
        insolation = region_coefs[selected_region]
        
        phases = st.radio("⚡ Фазность сети:", ["1 фаза", "3 фазы"], index=1)
        monthly_bill = st.number_input("💰 Чек за свет в месяц (руб):", min_value=0, value=13000, step=1000)
        tariff_rate = st.number_input("📈 Тариф за 1 кВт·ч (руб):", min_value=1.0, value=9.0, step=0.5)
        consumption_time = st.radio("🕒 Когда пик потребления?", ["Днем (Бизнес / Станки)", "Вечером / Ночью (Дом)"])
        
        PRICE_PER_KWT = 85000 if phases == "1 фаза" else 95000
        estimated_kwh_month = round(monthly_bill / (tariff_rate if tariff_rate > 0 else 9.0))
        recommended_power = max(3.0, min(round(estimated_kwh_month / 300, 1), 50.0))
        estimated_cost = round(recommended_power * PRICE_PER_KWT)
        
        annual_generation = recommended_power * 1000 * insolation
        annual_savings = annual_generation * tariff_rate
        
        if consumption_time.startswith("Вечером"):
            annual_savings = annual_savings * 0.4
            
        roi_years = max(3, round(estimated_cost / (annual_savings if annual_savings > 0 else 1)))
        
        calc_summary = (
            f"Режим: Экономия. Регион: {selected_region}. Сеть: {phases}. "
            f"Чек: {monthly_bill} руб. Тариф: {tariff_rate} руб. Пик: {consumption_time}. "
            f"Мощность СЭС: {recommended_power} кВт. Стоимость: {estimated_cost} руб. Окупаемость: {roi_years} лет."
        )
        
    elif app_type == "Защита от отключений / Резерв (Гибридная СЭС)":
        st.write("---")
        selected_region = st.text_input("📍 Ваш город / регион:", "Московская обл.")
        phases = st.radio("⚡ Фазность сети:", ["5 кВт (1 фаза)", "15 кВт (3 фазы)"])
        blackout_duration = st.selectbox("⏱️ Длительность отключений:", ["1-3 часа", "До 6 часов", "Сутки и более"])
        
        recommended_power = 5.0 if "1 фаза" in phases else 15.0
        duration_mult = {"1-3 часа": 1.0, "До 6 часов": 1.35, "Сутки и более": 1.85}
        estimated_cost = round(recommended_power * 140000 * duration_mult[blackout_duration])
        roi_years = "Не применимо (инвестиция в безопасность)"
        
        calc_summary = (
            f"Режим: Резерв. Регион: {selected_region}. Сеть: {phases}. Отключения: {blackout_duration}. "
            f"Мощность инвертора: {recommended_power} кВт. Стоимость системы с АКБ: {estimated_cost} руб."
        )

# ==========================================
# 5. БАЗА ЗНАНИЙ
# ==========================================
try:
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        public_knowledge = f.read()
except FileNotFoundError:
    public_knowledge = "Общая база знаний временно недоступна."

gist_url = st.secrets.get("GIST_RAW_URL", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")
exclusive_knowledge = ""

if gist_url and github_token:
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
        response = requests.get(gist_url, headers=headers, timeout=10)
        if response.status_code == 200:
            exclusive_knowledge = response.text
    except Exception:
        pass

full_knowledge_base = f"ОТКРЫТАЯ БАЗА ЗНАНИЙ:\n{public_knowledge}\n\nЭКСПЕРТНЫЕ ДАННЫЕ:\n{exclusive_knowledge}"

# ==========================================
# 6. ОСНОВНЫЕ КОЛОНКИ И ЧАТ С ИИ
# ==========================================
col1, col2 = st.columns([1.2, 2.5])

with col1:
    st.markdown('<div class="section-title-lead">📊 Экспресс-конфигурация</div>', unsafe_allow_html=True)
    if app_type != "Просто задать вопрос":
        roi_text = f"{roi_years} лет" if isinstance(roi_years, int) else str(roi_years)
        st.markdown(f"""
        <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #ffe58f; margin-bottom: 20px;">
            <table style="width:100%; border:none; font-size: 1.05em; color: #333333;">
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;"><b>Рекомендуемая мощность:</b></td><td style="text-align: right;"><b>{recommended_power} кВт</b></td></tr>
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;"><b>Стоимость «под ключ»:</b></td><td style="text-align: right;"><b>{estimated_cost:,} руб.</b></td></tr>
                <tr><td style="padding: 8px 0;"><b>Ожидаемая окупаемость:</b></td><td style="text-align: right;"><b>{roi_text}</b></td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("👇 Если что-то нужно исправить в расчете, напишите здесь", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": f"Проанализируй мои параметры: {calc_summary}. Всё ли верно? Что можешь посоветовать?"})
            st.rerun()
    else:
        st.info("👈 Заполните параметры в левом меню, чтобы здесь появился мгновенный расчет.")

with col2:
    st.markdown('<div class="section-title-lead">💬 Чат с ИИ-консультантом Sol</div>', unsafe_allow_html=True)
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
    if user_query := st.chat_input("Задайте ваш вопрос по солнечным станциям здесь..."):
        if is_injection_attempt(user_query):
            st.warning("⚠️ Я отвечаю только на вопросы о солнечных станциях ☀️")
        else:
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.write(user_query)
                
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown('<div class="thinking-indicator">Sol изучает технические параметры... ⏳</div>', unsafe_allow_html=True)
                
                ai_context = f"\n[ТЕКУЩИЙ РАСЧЕТ КЛИЕНТА]: {calc_summary}\nИспользуй эти цифры как факт. Не пересчитывай их." if app_type != "Просто задать вопрос" else ""
                
                SYSTEM_PROMPT = f"""Ты — ИИ-консультант Sol ☀️, строгий и честный инженер.
БАЗА ЗНАНИЙ: {full_knowledge_base}
ПРАВИЛА: 
1. Не выдумывай цифры. Используй данные из [ТЕКУЩИЙ РАСЧЕТ КЛИЕНТА], если он есть.
2. Минимальный срок окупаемости — 3 года.
3. В конце ответа ОБЯЗАТЕЛЬНО предложи: "Это предварительный расчет. Точную смету даст инженер после замера. Заполните форму «Бесплатный расчет станции» ниже — свяжемся за 15 минут!"
"""
                api_messages = [{"role": "system", "content": SYSTEM_PROMPT + ai_context}] + st.session_state.messages[-10:]

                try:
                    API_KEY = st.secrets.get("OPENAI_API_KEY")
                    BASE_URL = st.secrets.get("BASE_URL")
                    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
                    
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=api_messages,
                        temperature=0.1,
                        timeout=30
                    )
                    ai_response = response.choices[0].message.content
                    message_placeholder.write(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                except Exception as e:
                    logger.error(f"AI error: {type(e).__name__}")
                    message_placeholder.error("Техническая ошибка API. Проверьте ключи в secrets.")
            
            st.rerun()

# ==========================================
# 7. ФОРМА ЗАЯВКИ (ИСПРАВЛЕНА ИНДЕНТАЦИЯ)
# ==========================================
st.markdown("---")
st.markdown('<div class="section-title-lead">📞 Бесплатный расчет станции</div>', unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 14px; margin-top: -10px;'>Инженер свяжется с вами за 15 минут</p>", unsafe_allow_html=True)

with st.form(key="lead_form", clear_on_submit=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        client_name = st.text_input("👤 Ваше имя:", key="form_name")
    with col_f2:
        client_phone = st.text_input("📱 Телефон (WhatsApp/Telegram):", key="form_phone")
    consent = st.checkbox("✅ Я даю согласие на обработку моих персональных данных", key="form_consent")
    submit_lead = st.form_submit_button("🚀 Записаться на замер", use_container_width=True)

if submit_lead:
    if not consent:
        st.error("⚠️ Для отправки заявки необходимо поставить галочку согласия на обработку данных.")
    else:
        if "last_lead_time" not in st.session_state:
            st.session_state.last_lead_time = 0
        if "lead_count" not in st.session_state:
            st.session_state.lead_count = 0

        now = time.time()
        if now - st.session_state.last_lead_time < 600:
            st.session_state.lead_count += 1
        else:
            st.session_state.lead_count = 1
        st.session_state.last_lead_time = now

        if st.session_state.lead_count > 3:
            st.warning("⏳ Слишком много заявок. Попробуйте через 10 минут.")
        else:
            valid, result = validate_lead(client_name, client_phone)
            if not valid:
                st.warning(f"⚠️ {result}")
            else:
                clean_phone = result
                telegram_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
                chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")

                # Получаем данные из текущего расчета (теперь с правильными отступами)
                safe_region = selected_region if 'selected_region' in locals() else "Не указан"
                safe_power = recommended_power if 'recommended_power' in locals() else "Не рассчитано"
                safe_cost = estimated_cost if 'estimated_cost' in locals() else "Не рассчитано"

                # Определяем тип
                if app_type == "Экономия бюджета (Сетевая СЭС)":
                    safe_type = "Экономия"
                elif app_type == "Защита от отключений / Резерв (Гибридная СЭС)":
                    safe_type = "Защита от отключений"
                else:
                    safe_type = "Не выбрано"

                # Формируем сообщение корректно
                cost_str = f"{safe_cost:,} руб." if isinstance(safe_cost, (int, float)) else "Не рассчитано"
                
                lead_message = (
                    f"📥 <b>Новая заявка на замер!</b>\n\n"
                    f"👤 <b>Имя:</b> {escape_html(client_name.strip())}\n"
                    f"📞 <b>Телефон:</b> {escape_html(clean_phone)}\n"
                    f"🎯 <b>Цель:</b> {safe_type}\n\n"
                    f"📊 <b>Данные из калькулятора:</b>\n"
                    f"• Регион: {safe_region}\n"
                    f"• Мощность: {safe_power} кВт\n"
                    f"• Стоимость: {cost_str}"
                )

                if telegram_token and chat_id:
                    try:
                        tg_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                        payload = {"chat_id": chat_id, "text": lead_message, "parse_mode": "HTML"}
                        res = requests.post(tg_url, json=payload, timeout=10)
                        if res.status_code == 200:
                            st.success("✅ Спасибо! Инженер свяжется с вами.")
                            st.balloons()
                        else:
                            logger.error(f"Telegram API error: {res.status_code}")
                            st.error("Ошибка при отправке. Попробуйте позже.")
                    except requests.exceptions.Timeout:
                        logger.error("Telegram API timeout")
                        st.error("Сервис временно недоступен.")
                    except Exception as e:
                        logger.error(f"Telegram error: {type(e).__name__}")
                        st.error("Не удалось отправить заявку.")
                else:
                    st.warning("Параметры Telegram не настроены в секретах.")
