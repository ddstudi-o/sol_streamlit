import streamlit as st
from openai import OpenAI
import logging
import requests
import re
import time
from urllib.parse import urlparse

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
        return False, "Недопустимые символы в имени"
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
[data-testid="stHorizontalBlock"] { gap: 15px; }

[data-testid="stHorizontalBlock"] > div:nth-child(1) {
    background: linear-gradient(180deg, #f3f0ff 0%, #e8e4ff 100%);
    border-radius: 15px; padding: 20px; border: 2px solid #d4c5f9;
    min-height: 700px; max-height: 700px; overflow-y: auto; overflow-x: hidden;
}

[data-testid="stHorizontalBlock"] > div:nth-child(2) {
    background: linear-gradient(180deg, #fff9e6 0%, #fff3cc 100%);
    border-radius: 15px; padding: 20px; border: 2px solid #ffe58f;
    min-height: 700px; max-height: 700px;
    display: flex; flex-direction: column;
    overflow-y: auto; 
    mask-image: linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%);
}

[data-testid="stHorizontalBlock"] > div:nth-child(3) {
    background: linear-gradient(180deg, #e6fffa 0%, #ccffef 100%);
    border-radius: 15px; padding: 20px; border: 2px solid #b2f5ea;
    min-height: 700px; max-height: 700px; overflow-y: auto; overflow-x: hidden;
}

div[data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"]) {
    max-height: 520px; overflow-y: auto; overflow-x: hidden;
    padding-right: 5px; flex-grow: 1;
}
div[data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"])::-webkit-scrollbar { width: 8px; }
div[data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"])::-webkit-scrollbar-track {
    background: rgba(0,0,0,0.05); border-radius: 10px;
}
div[data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"])::-webkit-scrollbar-thumb {
    background-color: rgba(0,0,0,0.2); border-radius: 10px;
}

[data-testid="stChatInput"] { margin-top: 10px; flex-shrink: 0; }

.section-title-1 {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; padding: 12px; border-radius: 8px; text-align: center;
    font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.section-title-2 {
    background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
    color: #333; padding: 12px; border-radius: 8px; text-align: center;
    font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.section-title-3 {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white; padding: 12px; border-radius: 8px; text-align: center;
    font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important;
    color: white !important; font-weight: bold; border: none !important;
    border-radius: 8px; width: 100%; padding: 12px;
}

@keyframes slideUpFade {
    0% { opacity: 0; transform: translateY(25px); }
    100% { opacity: 1; transform: translateY(0); }
}
div[data-testid="stChatMessage"] {
    animation: slideUpFade 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}
.thinking-indicator {
    display: inline-block; animation: pulse 1.5s ease-in-out infinite;
    color: #666; font-style: italic; font-size: 1.1em;
}

@media (max-width: 900px) {
    [data-testid="stHorizontalBlock"] > div {
        min-height: 500px; max-height: 500px; margin-bottom: 20px;
    }
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. НАСТРОЙКА СТРАНИЦЫ
# ==========================================
st.set_page_config(page_title="Sol — ИИ Консультант", page_icon="☀️", layout="wide")
st.title("☀️ ИИ-консультант 'Sol' по солнечным и ветряным электростанциям")

col1, col2, col3 = st.columns([1, 1, 1])

# ==========================================
# СЕКЦИЯ 1: КАЛЬКУЛЯТОР (С ПРАВИЛОМ МИНИМУМА)
# ==========================================
with col1:
    st.markdown('<div class="section-title-1">📊 Первичный расчет</div>', unsafe_allow_html=True)

    region = st.selectbox(
        "🌍 Выберите регион:",
        ["Краснодарский край", "Ростовская область", "Крым", "Московская область", "Другой регион"],
        key="calc_region"
    )

    client_type = st.radio(
        "👤 Тип объекта:",
        ["Физлицо", "Бизнес"],
        index=0,
        key="calc_type",
        help="💡 Для физлиц расчет включает рост тарифов (7-8%/год) и 'умное потребление'"
    )

    monthly_bill = st.number_input(
        "💰 Счет за электричество в месяц (руб):",
        min_value=500, value=5000, step=500,
        key="calc_bill"
    )

    roof_area = st.slider("📐 Площадь крыши (кв.м):", 10, 200, 50, key="calc_area")

    INSOLATION_COEFFICIENTS = {
        "Краснодарский край": 1150, "Ростовская область": 1100,
        "Крым": 1150, "Московская область": 850, "Другой регион": 900
    }

    # === ПРАВИЛО МИНИМУМА ===
    tariff = 8.0 if client_type == "Бизнес" else 6.5
    monthly_consumption_kwh = monthly_bill / tariff
    power_by_consumption = monthly_consumption_kwh / 115.0
    power_by_roof = roof_area / 5.5
    
    # Берем МИНИМУМ из двух значений, округляем до 0.5, минимум 3.0 кВт
    raw_recommended_power = min(power_by_consumption, power_by_roof)
    recommended_power = max(3.0, round(raw_recommended_power * 2) / 2.0)
    
    estimated_cost = int(recommended_power * 120000)
    solar_efficiency = INSOLATION_COEFFICIENTS.get(region, 900)
    yearly_production_kwh = recommended_power * solar_efficiency

    smart_usage_coef = 0.75 if client_type == "Физлицо" else 0.95
    inflation_boost = 1.25 if client_type == "Физлицо" else 1.15

    yearly_savings = yearly_production_kwh * tariff * smart_usage_coef * inflation_boost
    roi_years = round(estimated_cost / yearly_savings, 1) if yearly_savings > 0 else 0

    if 0 < roi_years < 6.0:
        roi_years = 6.0

    st.markdown("#### 📋 Предварительный результат:")
    st.write(f"• ⚡ Мощность: **{recommended_power} кВт**")
    st.write(f"• 💵 Стоимость: **{estimated_cost:,} руб.**")
    st.write(f"• 📈 Окупаемость: **{roi_years} лет**")
    st.write(f"• 🌞 Выработка: **{yearly_production_kwh:,} кВт·ч/год**")
    
    st.info(f"🔍 Логика: Потребление требует {power_by_consumption:.1f} кВт, крыша вмещает {power_by_roof:.1f} кВт. Выбрано: {recommended_power} кВт.")

    calc_summary = (
        f"Тип объекта: {client_type}; Регион: {region}; Счет: {monthly_bill} руб/мес; "
        f"Площадь крыши: {roof_area} кв.м; Мощность: {recommended_power} кВт; "
        f"Ориентировочная стоимость: {estimated_cost} руб; Окупаемость: {roi_years} лет."
    )

# ==========================================
# 4. БАЗА ЗНАНИЙ
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
    if not is_safe_url(gist_url):
        logger.error("Blocked unsafe Gist URL")
    else:
        try:
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
            response = requests.get(gist_url, headers=headers, timeout=10)
            if response.status_code == 200:
                exclusive_knowledge = response.text
        except Exception as e:
            logger.error(f"Gist error: {type(e).__name__}")

full_knowledge_base = f"ОТКРЫТАЯ БАЗА ЗНАНИЙ:\n{public_knowledge}\n\nЭКСПЕРТНЫЕ ДАННЫЕ:\n{exclusive_knowledge}"

# ==========================================
# СЕКЦИЯ 2: ЧАТ
# ==========================================
with col2:
    st.markdown('<div class="section-title-2">💬 Чат с ИИ-агентом</div>', unsafe_allow_html=True)

    API_KEY = st.secrets.get("OPENAI_API_KEY")
    BASE_URL = st.secrets.get("BASE_URL")

    if not API_KEY or not BASE_URL:
        st.warning("⚠️ API не настроен.")
    else:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

        SYSTEM_PROMPT = f"""Ты — ИИ-консультант Sol ☀️, строгий и честный инженер по солнечным электростанциям.
Твоя цель: дать технически грамотный, физически возможный и честный предварительный расчет.

ДАННЫЕ ИЗ КАЛЬКУЛЯТОРА (используй ТОЛЬКО если клиент заполнил калькулятор слева): {calc_summary}
БАЗА ЗНАНИЙ: {full_knowledge_base}

ЖЕСТКИЕ ПРАВИЛА (СТРОГО СОБЛЮДАТЬ):

1. **ПРИОРИТЕТ ДАННЫХ:**
   - Если клиент в чате назвал конкретные цифры — ИСПОЛЬЗУЙ ИХ.
   - Если НЕ назвал — используй данные из калькулятора слева.
   - НИКОГДА не выдумывай параметры. Если данных нет — ЗАПРОСИ их.

2. **РАСЧЕТ МОЩНОСТИ СЭС (ПРАВИЛО МИНИМУМА):**
   - Сначала считаем мощность по потреблению: (Месячный счет / Тариф) / 115. (Тариф по умолчанию: 6.5 руб для физлиц, 8.0 руб для бизнеса).
   - Затем считаем максимум по крыше: Площадь крыши / 5.5.
   - Итоговая рекомендуемая мощность = МИНИМУМ из этих двух значений. НИКОГДА не предлагай мощность, превышающую потребности клиента, даже если на крыше много места.
   - Округляй до стандартных значений: 3, 5, 7.5, 10, 12, 15 кВт.

3. **ЧЕСТНАЯ ЭКОНОМИКА:**
   - Стоимость = Мощность (кВт) × 120 000 руб.
   - Годовая экономия = (Месячный счет × 12) × Коэффициент (0.75 для физлиц, 0.95 для бизнеса).
   - Окупаемость = Стоимость / Годовая экономия. НЕ округляй в лучшую сторону!

4. **СТРУКТУРА ОТВЕТА:**
   - Шаг 1: Назови тип станции.
   - Шаг 2: Покажи расчет: "Ваш счет 4000 руб -> потребление ~615 кВт·ч/мес -> оптимальная мощность ~5.5 кВт".
   - Шаг 3: Проверь по площади: "На вашей крыше 80 кв.м поместится до 14 кВт, но вам нужно только 5.5 кВт, чтобы не переплачивать".
   - Шаг 4: Назови цену и честную окупаемость.
   - Шаг 5: Пригласи заполнить форму справа для точной сметы со скидками.

5. **ЗАПРЕЩЕНО:**
   - Выдумывать площадь крыши или счет.
   - Предлагать избыточную мощность, забивая всю крышу панелями.
   - Раскрывать закупочные цены."""

        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "Здравствуйте! ☀️ Я ИИ-консультант Sol. **Расскажите о вашем объекте** — сколько вы платите за свет, какая площадь крыши. Я рассчитаю оптимальную мощность без переплат и навязывания лишнего оборудования!"}
            ]

        MAX_HISTORY = 10
        if len(st.session_state.messages) > MAX_HISTORY:
            st.session_state.messages = [st.session_state.messages[0]] + st.session_state.messages[-(MAX_HISTORY-1):]

        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        if user_input := st.chat_input("Задайте вопрос о солнечных станциях..."):
            if is_injection_attempt(user_input):
                st.warning("⚠️ Я отвечаю только на вопросы о солнечных станциях ☀️")
            else:
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.write(user_input)

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    message_placeholder.markdown('<div class="thinking-indicator">Sol думает... ⏳</div>', unsafe_allow_html=True)

                    recent_messages = st.session_state.messages[-10:]
                    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + recent_messages

                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=api_messages,
                            temperature=0.3,
                            timeout=30
                        )

                        if response.choices and response.choices[0].message.content:
                            ai_response = response.choices[0].message.content
                            message_placeholder.write(ai_response)
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})
                            st.rerun()
                        else:
                            message_placeholder.write("Извините, попробуйте задать вопрос ещё раз.")

                    except Exception as e:
                        logger.error(f"AI error: {type(e).__name__}")
                        message_placeholder.error("Техническая ошибка. Попробуйте позже.")

# ==========================================
# СЕКЦИЯ 3: ФОРМА
# ==========================================
with col3:
    st.markdown('<div class="section-title-3">📞 Бесплатный расчет станции</div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 14px; margin-top: -10px;'>Инженер свяжется с вами за 15 минут</p>", unsafe_allow_html=True)

    with st.form(key="lead_form", clear_on_submit=True):
        client_name = st.text_input("👤 Ваше имя:", key="form_name")
        client_phone = st.text_input("📱 Телефон (WhatsApp/Telegram):", key="form_phone")

        consent = st.checkbox(
            "✅ Я даю согласие на обработку моих персональных данных",
            key="form_consent"
        )

        submit_lead = st.form_submit_button("🚀 Записаться на замер")

    if submit_lead:
        if not consent:
            st.error("⚠️ Для отправки заявки необходимо поставить галочку согласия.")
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

                    safe_name = escape_html(client_name.strip())
                    safe_phone = escape_html(clean_phone)
                    safe_region = escape_html(region)
                    safe_type = escape_html(client_type)

                    lead_message = (
                        f"📥 <b>Новая заявка на замер!</b>\n\n"
                        f"👤 <b>Имя:</b> {safe_name}\n"
                        f"📞 <b>Телефон:</b> {safe_phone}\n"
                        f"🏢 <b>Тип объекта:</b> {safe_type}\n\n"
                        f"📊 <b>Расчет клиента:</b>\n"
                        f"• Регион: {safe_region}\n"
                        f"• Счет: {monthly_bill} руб/мес\n"
                        f"• Площадь: {roof_area} кв.м\n"
                        f"• Мощность: {recommended_power} кВт\n"
                        f"• Стоимость: {estimated_cost:,} руб.\n"
                        f"• Окупаемость: {roi_years} лет"
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
                                st.error(f"Ошибка Telegram: {res.status_code} — {res.text}")
                                logger.error(f"Telegram API error: {res.status_code} - {res.text}")

                        except Exception as e:
                            logger.error(f"Telegram request failed: {str(e)}")
                            st.error(f"Сетевая ошибка при отправке: {str(e)}")
                    else:
                        st.error("⚠️ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не найдены в Secrets!")
