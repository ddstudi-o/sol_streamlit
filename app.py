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
# 2. КАСТОМНЫЙ CSS (ИСПРАВЛЕНО ПОЛЕ ВВОДА)
# ==========================================
st.markdown("""
<style>
[data-testid="stHorizontalBlock"] { gap: 15px; }

[data-testid="stHorizontalBlock"] > div:nth-child(1) {
    background: linear-gradient(180deg, #f3f0ff 0%, #e8e4ff 100%);
    border-radius: 15px; padding: 20px; border: 2px solid #d4c5f9;
    min-height: 700px; max-height: 700px; overflow-y: auto; overflow-x: hidden;
}

/* ИСПРАВЛЕНО: overflow-y: auto вместо hidden, чтобы не обрезать поле ввода */
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

    # Коэффициенты для честной экономики
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
    
    # Прозрачная логика для клиента (можно убрать позже)
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
    st.markdown('<div class="section-title-2">💬 Чат с ИИ-агентом</div>', unsafe_allow_html=True
