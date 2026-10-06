import streamlit as st
from openai import OpenAI
import logging
import requests
import re
import time
from urllib.parse import urlparse

# ==========================================
# 0. PYTHON-КАЛЬКУЛЯТОР (Единственный источник числовой истины)
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
logging.basicConfig(level=logging.INFO)
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
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h3 {
    color: white !important;
    font-weight: 500;
}

section[data-testid="stSidebar"] .stButton > button {
    background-color: #222222 !important;
    color: #FFFFFF !important;
    border: 1px solid #555555 !important;
    font-weight: 600 !important;
    text-align: left !important;
    padding: 12px !important;
    border-radius: 8px !important;
    transition: background-color 0.2s !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #444444 !important;
    color: #FFFFFF !important;
}

div[data-baseweb="popover"] *, 
div[data-baseweb="select"] * {
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

API_KEY = st.secrets.get("OPENAI_API_KEY", "")
BASE_URL = st.secrets.get("BASE_URL", "")
AI_MODEL = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Здравствуйте! ☀️ Я ИИ-консультант Sol. Выберите задачу слева, настройте параметры и нажмите кнопку «Готово». Я рассчитаю предварительный вариант и объясню его простым языком. Вы также можете сразу задать вопрос, например: «Какая станция подойдет для дома 150 м²?»"}
    ]

if "app_type" not in st.session_state:
    st.session_state.app_type = None

# ==========================================
# 4. ЛЕВАЯ ПАНЕЛЬ (PYTHON-КАЛЬКУЛЯТОР)
# ==========================================
with st.sidebar:
    st.markdown("### Что вы хотите решить?")
    
    if st.button("☀️ Экономия бюджета\n(Сетевая СЭС)", use_container_width=True, key="btn_economy"):
        st.session_state.app_type = "Экономия бюджета (Сетевая СЭС)"
        
    if st.button("🔋 Защита от отключений\n(Резерв / Гибридная СЭС)", use_container_width=True, key="btn_backup"):
        st.session_state.app_type = "Защита от отключений / Резерв (Гибридная СЭС)"

    app_type = st.session_state.app_type
    
    calc_summary = "Параметры не выбраны"
    recommended_power = 0.0
    estimated_cost = 0
    roi_years = 0.0
    selected_region = "Не указан"
    
    monthly_bill = 0.0
    tariff_rate = 0.0
    phases = "Не выбрано"
    consumption_time = "Не выбрано"
    
    if app_type == "Экономия бюджета (Сетевая СЭС)":
        st.write("---")
        region_coefs = {"Краснодарский край (Юг)": 1.35, "Москва и МО (Центр)": 1.0, "Новосибирск (Сибирь)": 1.15}
        selected_region = st.selectbox("📍 Ваш город / регион:", list(region_coefs.keys()), key="sidebar_region")
        insolation = region_coefs[selected_region]
        
        phases = st.radio("⚡ Фазность сети:", ["(1 фаза)", "(3 фазы)"], index=1, key="sidebar_phases")
        monthly_bill = st.number_input("💰 Чек за свет в месяц (руб):", min_value=0, value=12000, step=1000, key="sidebar_bill")
        tariff_rate = st.number_input("📈 Тариф за 1 кВт·ч (руб):", min_value=1.0, value=13.5, step=0.5, key="sidebar_tariff")
        consumption_time = st.radio("🕒 Когда пик потребления?", ["Днем (Бизнес / Станки)", "Вечером / Ночью (Дом)"], key="sidebar_time")
        
        PRICE_PER_KWT = 85000 if "1 фаза" in phases else 95000
        
        monthly_consumption_kwh = monthly_bill / tariff_rate if tariff_rate > 0 else 0
        recommended_power = max(3.0, min(round(monthly_consumption_kwh / 300, 1), 50.0))
        estimated_cost = round(recommended_power * PRICE_PER_KWT)
        
        annual_consumption_kwh = monthly_consumption_kwh * 12
        annual_generation_kwh = recommended_power * 1000 * insolation 
        
        self_consumption_ratio = 0.8 if consumption_time.startswith("Днем") else 0.4
        used_generation_kwh = annual_generation_kwh * self_consumption_ratio
        actual_offset_kwh = min(used_generation_kwh, annual_consumption_kwh)
        annual_savings_rub = actual_offset_kwh * tariff_rate
        
        roi_years = round(estimated_cost / annual_savings_rub, 1) if annual_savings_rub > 0 else 99.0
        
        calc_summary = (
            f"Режим: Экономия. Регион: {selected_region}. Сеть: {phases}. "
            f"Чек: {monthly_bill} руб. Тариф: {tariff_rate} руб. Пик: {consumption_time}. "
            f"Мощность СЭС: {recommended_power} кВт. Стоимость: {estimated_cost} руб. Окупаемость: {roi_years} лет."
        )
        
    elif app_type == "Защита от отключений / Резерв (Гибридная СЭС)":
        st.write("---")
        selected_region = st.text_input("📍 Ваш город / регион:", "Московская обл.", key="sidebar_region_res")
        phases = st.radio("⚡ Фазность сети:", ["(1 фаза)", "(3 фазы)"], key="sidebar_phases_res")
        blackout_duration = st.selectbox("⏱️ Длительность отключений:", ["1-3 часа", "До 6 часов", "Сутки и более"], key="sidebar_blackout")
        
        recommended_power = 5.0 if "1 фаза" in phases else 15.0
        duration_mult = {"1-3 часа": 1.0, "До 6 часов": 1.35, "Сутки и более": 1.85}
        estimated_cost = round(recommended_power * 140000 * duration_mult[blackout_duration])
        roi_years = 0.0
        
        calc_summary = (
            f"Режим: Резерв. Регион: {selected_region}. Сеть: {phases}. Отключения: {blackout_duration}. "
            f"Мощность инвертора: {recommended_power} кВт. Стоимость системы с АКБ: {estimated_cost} руб."
        )

    # КНОПКА "ГОТОВО" (Заменяет автоматический вызов LLM)
    if app_type in ["Экономия бюджета (Сетевая СЭС)", "Защита от отключений / Резерв (Гибридная СЭС)"]:
        st.markdown("---")
        st.markdown("Настройте параметры и нажмите:")
        if st.button("✅ Готово. Показать предварительный расчет", use_container_width=True, key="btn_ready"):
            st.session_state.pending_ai_query = "auto_analysis"
            st.session_state.last_calc_summary = calc_summary
            st.rerun()

# ==========================================
# СТРУКТУРИРОВАННЫЙ CURRENT_CALCULATION
# ==========================================
current_calculation = {
    "mode": app_type,
    "region": selected_region,
    "phases": phases,
    "monthly_bill_rub": monthly_bill if app_type == "Экономия бюджета (Сетевая СЭС)" else 0,
    "tariff_rub_per_kwh": tariff_rate if app_type == "Экономия бюджета (Сетевая СЭС)" else 0,
    "consumption_time": consumption_time if app_type == "Экономия бюджета (Сетевая СЭС)" else "N/A",
    "recommended_power_kw": recommended_power,
    "estimated_cost_rub": estimated_cost,
    "payback_years": roi_years if isinstance(roi_years, float) and roi_years < 50 else "Не применимо",
    "calculation_source": "python_calculator"
}

current_calculation_text = (
    "CURRENT_CALCULATION:\n"
    f"- Режим: {current_calculation['mode']}\n"
    f"- Регион: {current_calculation['region']}\n"
    f"- Сеть: {current_calculation['phases']}\n"
)
if current_calculation['mode'] == "Экономия бюджета (Сетевая СЭС)":
    current_calculation_text += (
        f"- Чек за электроэнергию: {current_calculation['monthly_bill_rub']} руб./месяц\n"
        f"- Тариф: {current_calculation['tariff_rub_per_kwh']} руб./кВт·ч\n"
        f"- Пик потребления: {current_calculation['consumption_time']}\n"
    )
current_calculation_text += (
    f"- Рекомендуемая мощность: {current_calculation['recommended_power_kw']} кВт\n"
    f"- Стоимость: {current_calculation['estimated_cost_rub']} руб.\n"
    f"- Расчетная окупаемость: {current_calculation['payback_years']}\n"
    f"- Источник числовых данных: Python-калькулятор"
)

# ==========================================
# 5. БАЗА ЗНАНИЙ
# ==========================================
try:
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        public_knowledge = f.read()
    logger.info(f"✅ knowledge.txt загружен ({len(public_knowledge)} символов)")
except FileNotFoundError:
    public_knowledge = "Общая база знаний временно недоступна."
    logger.warning("⚠️ knowledge.txt не найден!")

gist_url = st.secrets.get("GIST_RAW_URL", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")
exclusive_knowledge = ""

if gist_url and github_token:
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
        response = requests.get(gist_url, headers=headers, timeout=10)
        if response.status_code == 200:
            exclusive_knowledge = response.text
            logger.info(f"✅ Gist загружен ({len(exclusive_knowledge)} символов)")
        else:
            logger.warning(f"⚠️ Gist вернул статус {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка загрузки Gist: {type(e).__name__}: {str(e)}")

full_knowledge_base = f"ОТКРЫТАЯ БАЗА ЗНАНИЙ:\n{public_knowledge}\n\nЭКСПЕРТНЫЕ ДАННЫЕ:\n{exclusive_knowledge}"

# ==========================================
# 6. ОСНОВНЫЕ КОЛОНКИ И ЕДИНАЯ ЛОГИКА ЧАТА С ИИ
# ==========================================
col1, col2 = st.columns([1.2, 2.5])

with col1:
    st.markdown('<div style="position: sticky; top: 20px; z-index: 10;">', unsafe_allow_html=True)
    st.markdown('<div class="section-title-lead">📊 Экспресс-конфигурация</div>', unsafe_allow_html=True)
    
    if app_type in ["Экономия бюджета (Сетевая СЭС)", "Защита от отключений / Резерв (Гибридная СЭС)"]:
        roi_text = f"{roi_years} лет" if isinstance(roi_years, float) and roi_years < 50 else str(roi_years)
        st.markdown(f"""
        <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #ffe58f; margin-bottom: 20px;">
            <table style="width:100%; border:none; font-size: 1.05em; color: #333333;">
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;"><b>Рекомендуемая мощность:</b></td><td style="text-align: right;"><b>{recommended_power} кВт</b></td></tr>
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;"><b>Стоимость «под ключ»:</b></td><td style="text-align: right;"><b>{estimated_cost:,} руб.</b></td></tr>
                <tr><td style="padding: 8px 0;"><b>Ожидаемая окупаемость:</b></td><td style="text-align: right;"><b>{roi_text}</b></td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("👈 Выберите задачу в левом меню, чтобы здесь появился расчет.")
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="section-title-lead">💬 Чат с ИИ-консультантом Sol</div>', unsafe_allow_html=True)
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
    new_query = None
    is_auto_analysis = False
    
    # Поле ввода вынесено в конец блока col2, чтобы Streamlit закрепил его внизу viewport
    if user_query := st.chat_input("Задайте вопрос — помогу подобрать решение для вашего дома или бизнеса"):
        if is_injection_attempt(user_query):
            st.warning("⚠️ Я отвечаю только на вопросы о солнечных станциях ☀️")
        else:
            new_query = user_query
    elif st.session_state.get("pending_ai_query") == "auto_analysis":
        new_query = "auto_analysis"
        is_auto_analysis = True
        st.session_state.pending_ai_query = None

    if new_query:
        if not is_auto_analysis:
            st.session_state.messages.append({"role": "user", "content": new_query})
            with st.chat_message("user"):
                st.write(new_query)
        
        if is_auto_analysis:
            st.session_state.messages = [
                msg for msg in st.session_state.messages 
                if msg.get("message_type") != "calculator_analysis"
            ]
            
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            if not API_KEY or not BASE_URL:
                error_msg = "⚠️ API не настроен. Проверьте OPENAI_API_KEY и BASE_URL в secrets."
                message_placeholder.error(error_msg)
                logger.error("API не настроен")
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            else:
                message_placeholder.markdown('<div class="thinking-indicator">Sol изучает технические параметры... ⏳</div>', unsafe_allow_html=True)
                
                SYSTEM_PROMPT = f"""Ты — ИИ-консультант Sol ☀️, первичный консультант по солнечным электростанциям.

ТВОЯ ГЛАВНАЯ ЗАДАЧА:
НЕ ПРОСТО ОТВЕЧАТЬ НА ВОПРОСЫ, а помогать клиенту принять решение и перевести его к форме заявки.

CURRENT_CALCULATION (АКТУАЛЬНЫЕ ДАННЫЕ КАЛЬКУЛЯТОРА):
{current_calculation_text}

ЖЁСТКИЕ ПРАВИЛА:
1. СТИЛЬ ОБЩЕНИЯ: Коротко, понятно, конкретно. Без канцелярита (НЕ пиши "Клиенту был проведен расчет"). Обращайся непосредственно к клиенту: "По вашим параметрам предварительно получается...". Сначала полезная информация, затем следующий шаг.
2. ИСПОЛЬЗУЙ ДАННЫЕ КАЛЬКУЛЯТОРА: Если клиент спрашивает о стоимости или мощности, бери цифры ИСКЛЮЧИТЕЛЬНО из CURRENT_CALCULATION. Не пересчитывай и не выдумывай.
3. НЕ ЗАДАВАЙ ЛИШНИХ ВОПРОСОВ: Если данные уже есть в CURRENT_CALCULATION, не спрашивай их снова.
4. ПРЕДВАРИТЕЛЬНЫЙ ХАРАКТЕР: Никогда не выдавай предварительный расчет за финальный инженерный проект.
5. СЦЕНАРИЙ "РЕЗЕРВНОЕ ПИТАНИЕ": Если клиент хочет резерв для котла, насоса и холодильника, кратко подтверди, что гибридная СЭС для этого подходит. Объясни, что при отключениях до суток ключевой вопрос — пусковые мощности и точная емкость АКБ, которые зависят от конкретных моделей оборудования. Поэтому нельзя назвать емкость автоматически. Веди к форме.
6. СЦЕНАРИЙ "МАЙНИНГ": Если спрашивают про майнинг, назови текущую мощность из CURRENT_CALCULATION (например, {current_calculation['recommended_power_kw']} кВт). Объясни, что для майнинга критически важно знать модель ASIC и режим работы (круглосуточно). Не обещай, что текущей мощности точно хватит. Веди к форме.
7. ФИНАЛЬНЫЙ CTA: В коммерчески важных ответах или после предварительного расчета обязательно добавляй: "Оставьте контакты в форме «Бесплатный расчет станции» — специалист проверит параметры объекта и подготовит точный вариант с учетом СКИДОК!" (Слово СКИДОК пиши заглавными).

БАЗА ЗНАНИЙ (ДЛЯ СПРАВОК):
{full_knowledge_base}
Используй её только для кратких технических пояснений, но НЕ для замены цифр из CURRENT_CALCULATION.
"""
                api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages[-10:]

                try:
                    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
                    logger.info(f"📤 Отправка запроса: модель={AI_MODEL}, сообщений={len(api_messages)}")
                    
                    response = client.chat.completions.create(
                        model=AI_MODEL,
                        messages=api_messages,
                        temperature=0.1,
                        timeout=30
                    )
                    ai_response = response.choices[0].message.content
                    message_placeholder.write(ai_response)
                    
                    if is_auto_analysis:
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": ai_response,
                            "message_type": "calculator_analysis"
                        })
                    else:
                        st.session_state.messages.append({"role": "assistant", "content": ai_response})
                        
                    logger.info("✅ Ответ получен успешно")
                    
                except Exception as e:
                    error_type = type(e).__name__
                    logger.exception(f"AI API Error: {error_type}")
                    error_display = f"🔧 Ошибка AI API: **{error_type}**\n\nПроверьте настройки подключения или попробуйте позже."
                    message_placeholder.error(error_display)
                    st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Техническая ошибка: {error_type}."})

# ==========================================
# 7. ФОРМА ЗАЯВКИ (Без изменений в логике)
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

                safe_region = current_calculation["region"]
                safe_power = current_calculation["recommended_power_kw"]
                safe_cost = current_calculation["estimated_cost_rub"]
                safe_type = "Экономия" if app_type == "Экономия бюджета (Сетевая СЭС)" else "Защита от отключений" if app_type == "Защита от отключений / Резерв (Гибридная СЭС)" else "Не выбрано"

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
