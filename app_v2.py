import streamlit as st
from openai import OpenAI
import logging
import requests
import re
import time
from urllib.parse import urlparse

# ==========================================
# 0. PYTHON-КАЛЬКУЛЯТОР (Оставлен как фолбэк для чата)
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
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ И БЕЗОПАСНОСТИ (Из старого кода)
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
# 2. КАСТОМНЫЙ CSS (Адаптирован под 2 колонки + сайдбар)
# ==========================================
st.markdown("""
<style>
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

.section-title-chat { background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); color: #333; padding: 12px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
.section-title-lead { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 12px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 1.2em; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }

div[data-testid="column"]:nth-of-type(2) .stButton > button { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important; color: white !important; font-weight: bold; border: none !important; border-radius: 8px; width: 100%; padding: 12px; }

@keyframes slideUpFade { 0% { opacity: 0; transform: translateY(30px); } 100% { opacity: 1; transform: translateY(0); } }
div[data-testid="stChatMessage"] { animation: slideUpFade 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards; margin-bottom: 15px; }

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
        {"role": "assistant", "content": "Здравствуйте! ☀️ Я ИИ-консультант Sol. Выберите параметры вашей будущей станции в меню слева, чтобы мгновенно увидеть расчет. Затем нажмите кнопку «Передать расчет ИИ», и я проанализирую вашу конфигурацию!"}
    ]

if "trigger_ai_analysis" not in st.session_state:
    st.session_state.trigger_ai_analysis = False

# ==========================================
# 4. ЛЕВАЯ ПАНЕЛЬ (ИНТЕРАКТИВНЫЙ КАЛЬКУЛЯТОР)
# ==========================================
with st.sidebar:
    st.markdown("### 📋 Параметры для расчета")
    
    app_type = st.selectbox(
        "Какая главная задача СЭС?",
        ["Просто задать вопрос", "Экономия бюджета (Сетевая СЭС)", "Защита от отключений (Гибридная СЭС)"]
    )
    
    calc_summary = "Клиент пока не выбрал параметры для расчета."
    user_data = {}
    
    if app_type == "Экономия бюджета (Сетевая СЭС)":
        st.markdown("---")
        user_data['region'] = st.text_input("📍 Ваш город / регион:", "Краснодарский край")
        user_data['phases'] = st.radio("⚡ Фазность сети:", ["1 фаза", "3 фазы"], index=1)
        user_data['monthly_bill'] = st.number_input("💰 Чек за свет в месяц (руб):", min_value=0, value=13000, step=1000)
        user_data['tariff'] = st.number_input("📈 Тариф за 1 кВт·ч (руб):", min_value=1.0, value=9.0, step=0.5)
        user_data['peak_time'] = st.radio("🕒 Когда пик потребления?", ["Днем (Бизнес / Станки)", "Вечером / Ночью (Дом)"])
        user_data['microgen'] = st.checkbox("🔌 Планирую продавать излишки в сеть")
        
        PRICE_PER_KWT = 85000
        estimated_kwh = round(user_data['monthly_bill'] / user_data['tariff'])
        user_data['power'] = max(3.0, min(round(estimated_kwh / 300, 1), 50.0))
        user_data['cost'] = round(user_data['power'] * PRICE_PER_KWT)
        user_data['roi'] = 5 if user_data['peak_time'].startswith("Днем") else 9
        
        calc_summary = (
            f"РЕЖИМ: Экономия (Сетевая). Регион: {user_data['region']}. Сеть: {user_data['phases']}. "
            f"Чек: {user_data['monthly_bill']} руб. Тариф: {user_data['tariff']} руб/кВт·ч. "
            f"Расчетная мощность СЭС: {user_data['power']} кВт. Стоимость: {user_data['cost']} руб. "
            f"Окупаемость: {user_data['roi']} лет. Пик потребления: {user_data['peak_time']}."
        )
        
    elif app_type == "Защита от отключений (Гибридная СЭС)":
        st.markdown("---")
        user_data['region'] = st.text_input("📍 Ваш город / регион:", "Московская обл.")
        user_data['phases'] = st.radio("⚡ Фазность сети:", ["1 фаза", "3 фазы"], index=1)
        user_data['duration'] = st.select_slider("⏱️ Длительность отключений:", options=["1-3 часа", "До 6 часов", "Сутки и более"])
        
        st.write("🔋 Что должно работать обязательно:")
        appliances = []
        if st.checkbox("Холодильник и свет", value=True): appliances.append("Холодильник/Свет")
        if st.checkbox("Котел отопления и насосы", value=True): appliances.append("Котел/Насосы")
        if st.checkbox("Мощные приборы (Плита, Стиралка)"): appliances.append("Тяжелая техника")
        
        user_data['power'] = 5.0 if "Тяжелая техника" not in appliances else 10.0
        PRICE_PER_KWT_HYBRID = 140000
        user_data['cost'] = round(user_data['power'] * PRICE_PER_KWT_HYBRID)
        
        calc_summary = (
            f"РЕЖИМ: Резерв/Автономия (Гибридная). Регион: {user_data['region']}. Сеть: {user_data['phases']}. "
            f"Отключения: {user_data['duration']}. Резервные приборы: {', '.join(appliances)}. "
            f"Мощность инвертора: {user_data['power']} кВт. Стоимость системы с АКБ: {user_data['cost']} руб."
        )

# ==========================================
# 5. БАЗА ЗНАНИЙ (Из старого кода)
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
            else:
                logger.error(f"Gist fetch error: {response.status_code}")
        except Exception as e:
            logger.error(f"Gist error: {type(e).__name__}")

full_knowledge_base = f"ОТКРЫТАЯ БАЗА ЗНАНИЙ:\n{public_knowledge}\n\nЭКСПЕРТНЫЕ ДАННЫЕ:\n{exclusive_knowledge}"

# ==========================================
# 6. ЦЕНТРАЛЬНАЯ ПАНЕЛЬ И ОКНО ДИАЛОГА
# ==========================================
col_chat, col_lead = st.columns([2.5, 1.0])

with col_chat:
    # «ЖИВАЯ КАРТОЧКА»
    if app_type != "Просто задать вопрос":
        roi_html = f"<tr style='border-bottom: 1px solid #eee;'><td style='padding: 8px 0;'>Ожидаемый срок окупаемости:</td><td style='text-align: right; padding: 8px 0;'><b>{user_data['roi']} лет</b></td></tr>" if 'roi' in user_data else ""
        st.markdown(f"""
        <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #ffe58f; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <h4 style="margin: 0 0 15px 0; color: #d46b08; text-align: center;">📊 Экспресс-конфигурация оборудования</h4>
            <table style="width:100%; border:none; font-size: 1.1em; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;">Рекомендуемая мощность СЭС:</td><td style="text-align: right; padding: 8px 0;"><b>{user_data['power']} кВт</b></td></tr>
                <tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px 0;">Ориентировочная стоимость «под ключ»:</td><td style="text-align: right; padding: 8px 0;"><b>{user_data['cost']:,} руб.</b></td></tr>
                {roi_html}
            </table>
            <p style="color: #8c8c8c; font-size: 0.85em; margin-top: 15px; margin-bottom: 0; text-align: center;">
                💡 Параметры пересчитываются автоматически при изменении данных в левом меню.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("💬 Передать эти цифры ИИ-консультанту Sol для анализа", use_container_width=True, type="primary"):
            st.session_state.messages.append({
                "role": "user", 
                "content": f"Я настроил параметры в калькуляторе. Проанализируй мою конфигурацию: {calc_summary}. Всё ли верно? Что можешь посоветовать?"
            })
            st.session_state.trigger_ai_analysis = True
            st.rerun()

    st.markdown('<div class="section-title-chat">💬 Диалог с экспертом Sol</div>', unsafe_allow_html=True)
    
    MAX_HISTORY = 10
    if len(st.session_state.messages) > MAX_HISTORY:
        st.session_state.messages = [st.session_state.messages[0]] + st.session_state.messages[-(MAX_HISTORY-1):]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_query = st.chat_input("Задайте вопрос инженеру или уточните детали...")
    
    if user_query or st.session_state.trigger_ai_analysis:
        if user_query:
            if is_injection_attempt(user_query):
                st.warning("⚠️ Я отвечаю только на вопросы о солнечных станциях ☀️")
                st.session_state.trigger_ai_analysis = False
            else:
                st.session_state.messages.append({"role": "user", "content": user_query})
                with st.chat_message("user"):
                    st.write(user_query)
                
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    message_placeholder.markdown('<div class="thinking-indicator">Sol анализирует конфигурацию... ⏳</div>', unsafe_allow_html=True)

                    # Формируем контекст из сайдбара
                    ai_context = ""
                    if app_type != "Просто задать вопрос":
                        ai_context = f"""
[СИСТЕМНЫЙ СВЕРХВАЖНЫЙ КОНТЕКСТ - РАСЧЕТ ВЫПОЛНЕН PYTHON]:
Клиент использовал интерактивный калькулятор. Вот точные данные:
{calc_summary}
ЖЕСТКИЕ ПРАВИЛА:
1. Используй ТОЛЬКО эти цифры. ЗАПРЕЩЕНО их критиковать, называть "ошибкой" или пересчитывать.
2. Подтверди правильность выбора клиента.
3. Задай 1-2 уточняющих вопроса из соответствующего блока (Экономия или Резерв), если данных не хватает.
"""
                    else:
                        # Фолбэк, если клиент просто пишет в чат без сайдбара
                        calc_results = calculate_solar_investment(user_query)
                        if calc_results:
                            ai_context = f"""
[СИСТЕМНЫЙ КОНТЕКСТ - РАСЧЕТ ИЗ ТЕКСТА]:
- Расходы: {calc_results['bill_amount']} руб/мес.
- Мощность: {calc_results['required_power_kw']} кВт.
- Стоимость: {calc_results['estimated_cost']} руб.
Используй эти цифры.
"""
                        else:
                            ai_context = "[КОНТЕКСТ]: Клиент задал общий вопрос без использования калькулятора."

                    api_messages = [
                        {"role": "system", "content": f"""Ты — ИИ-консультант Sol ☀️, строгий и честный инженер.
БАЗА ЗНАНИЙ: {full_knowledge_base}
ПРАВИЛА: Не выдумывай цифры. Минимальный срок окупаемости — 6 лет. В конце диалога предлагай заполнить форму справа."""},
                        {"role": "system", "content": ai_context}
                    ] + st.session_state.messages[-10:]

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
                        message_placeholder.error("Техническая ошибка. Попробуйте позже.")
                
                st.session_state.trigger_ai_analysis = False
                st.rerun()

# ==========================================
# 7. ПРАВАЯ ПАНЕЛЬ: ФОРМА ЗАЯВКИ (Из старого кода, адаптированная)
# ==========================================
with col_lead:
    st.markdown('<div class="section-title-lead">📞 Бесплатный расчет станции</div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 14px; margin-top: -10px;'>Инженер свяжется с вами за 15 минут</p>", unsafe_allow_html=True)

    with st.form(key="lead_form", clear_on_submit=True):
        client_name = st.text_input("👤 Ваше имя:", key="form_name")
        client_phone = st.text_input("📱 Телефон (WhatsApp/Telegram):", key="form_phone")
        consent = st.checkbox("✅ Я даю согласие на обработку моих персональных данных", key="form_consent")
        submit_lead = st.form_submit_button("🚀 Записаться на замер")

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

                    # Берем данные из сайдбара, если они есть
                    safe_region = escape_html(user_data.get('region', 'Не указан'))
                    safe_power = user_data.get('power', 'Не рассчитано')
                    safe_cost = user_data.get('cost', 'Не рассчитано')

                    lead_message = (
                        f"📥 <b>Новая заявка на замер!</b>\n\n"
                        f"👤 <b>Имя:</b> {escape_html(client_name.strip())}\n"
                        f"📞 <b>Телефон:</b> {escape_html(clean_phone)}\n"
                        f"🎯 <b>Цель:</b> {app_type}\n\n"
                        f"📊 <b>Данные из калькулятора:</b>\n"
                        f"• Регион: {safe_region}\n"
                        f"• Мощность: {safe_power} кВт\n"
                        f"• Стоимость: {safe_cost:,} руб." if isinstance(safe_cost, (int, float)) else ""
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
