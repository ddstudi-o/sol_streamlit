"""Helpers that keep model replies tied to the active Python calculation."""

import math
import re
from typing import Optional, Tuple

ECONOMY_MODE = "Экономия бюджета (Сетевая СЭС)"
BACKUP_MODE = "Защита от отключений / Резерв (Гибридная СЭС)"


def calculate_economy_values(monthly_bill: float, tariff: float, phases: str, insolation: float, consumption_time: str) -> Tuple[float, int, float]:
    """
    Расчет параметров для сетевой СЭС с учетом региональной инсоляции.
    Возвращает: (recommended_power_kw, estimated_cost_rub, payback_years)
    """
    price_per_kw = 85000 if "1 фаза" in phases else 95000
    
    # 1. Реальное потребление в кВт*ч
    monthly_consumption_kwh = monthly_bill / tariff if tariff > 0 else 0
    
    # 2. Расчет необходимой мощности с учетом инсоляции региона
    base_monthly_production_per_kw = 100.0 * insolation
    required_power_kw = round(monthly_consumption_kwh / base_monthly_production_per_kw, 1)
    
    # Ограничения на размер СЭС для частного дома/бизнеса
    required_power_kw = max(3.0, min(required_power_kw, 50.0))
    
    # 3. Расчет стоимости
    estimated_cost = round(required_power_kw * price_per_kw)
    
    # 4. Расчет окупаемости (ROI)
    annual_consumption_kwh = monthly_consumption_kwh * 12
    annual_generation_kwh = required_power_kw * 1000 * insolation
    self_consumption_ratio = 0.8 if consumption_time.startswith("Днем") else 0.4
    used_generation_kwh = annual_generation_kwh * self_consumption_ratio
    actual_offset_kwh = min(used_generation_kwh, annual_consumption_kwh)
    annual_savings_rub = actual_offset_kwh * tariff
    
    payback = round(estimated_cost / annual_savings_rub, 1) if annual_savings_rub > 0 else 99.0
    
    return required_power_kw, estimated_cost, payback


def calculate_backup_values(phases: str, blackout_duration: str) -> Tuple[float, int, Optional[float]]:
    """
    Расчёт рекомендуемой мощности и стоимости для гибридной СЭС (резерв).
    Окупаемость не применяется для резервных систем.
    """
    recommended_power = 5.0 if "1 фаза" in phases else 15.0
    
    duration_mult = {
        "1-3 часа": 1.0,
        "До 6 часов": 1.35,
        "Сутки и более": 1.85
    }
    mult = duration_mult.get(blackout_duration, 1.0)
    
    estimated_cost = round(recommended_power * 140000 * mult)
    payback_years = None
    
    return recommended_power, estimated_cost, payback_years


def build_current_calculation(mode, region, phases, monthly_bill, tariff,
                              consumption_time, power, cost, payback,
                              extra=None):
    is_economy = mode == ECONOMY_MODE
    result = {
        "mode": mode,
        "region": region,
        "phases": phases,
        "monthly_bill_rub": monthly_bill if is_economy else None,
        "tariff_rub_per_kwh": tariff if is_economy else None,
        "consumption_time": consumption_time if is_economy else None,
        "recommended_power_kw": power,
        "estimated_cost_rub": cost,
        "payback_years": payback,
        "calculation_source": "python_calculator",
    }
    if extra:
        result.update(extra)
    return result


def calculation_is_valid(calc):
    if not isinstance(calc, dict) or calc.get("mode") not in (ECONOMY_MODE, BACKUP_MODE):
        return False
    for key in ("recommended_power_kw", "estimated_cost_rub"):
        value = calc.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            return False
    payback = calc.get("payback_years")
    if calc.get("mode") == ECONOMY_MODE:
        for key in ("monthly_bill_rub", "tariff_rub_per_kwh"):
            value = calc.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                return False
        if not isinstance(payback, (int, float)):
            return False
    return payback is None or (isinstance(payback, (int, float)) and math.isfinite(payback) and payback >= 0)


def _normalize_number(raw):
    return float(str(raw).replace(" ", "").replace("\u00a0", "").replace(",", "."))


def answer_has_calculation_conflict(answer: str, calc: dict) -> bool:
    """
    Проверяет, содержит ли ответ модели числовые противоречия с CURRENT_CALCULATION.
    Улучшенная версия: распознаёт "тыс.", "млн", различает кВт и кВт·ч.
    """
    if not answer or not calc:
        return False
    
    def normalize_number(text: str) -> float:
        text = str(text).replace(" ", "").replace(",", ".")
        if "тыс" in text.lower():
            return float(text.replace("тыс", "").replace(".", "")) * 1000
        if "млн" in text.lower():
            return float(text.replace("млн", "").replace(".", "")) * 1000000
        return float(text.replace(".", "").replace(",", "."))
    
    number_pattern = r"(\d[\d\s,.]*\d)"
    
    checks = [
        ("recommended_power_kw", rf"{number_pattern}\s*(?:квт|киловатт)\b(?!\s*·\s*ч)"),
        ("estimated_cost_rub", rf"{number_pattern}\s*(?:тыс\.?\s*)?(?:руб|₽)"),
        ("estimated_cost_rub", rf"{number_pattern}\s*(?:млн\.?\s*)?(?:руб|₽)"),
        ("payback_years", rf"{number_pattern}\s*(?:лет|года|год)\b"),
    ]
    
    for key, pattern in checks:
        expected = calc.get(key)
        if expected is None:
            continue
        
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            try:
                actual = normalize_number(match.group(1))
                if not math.isclose(actual, float(expected), rel_tol=0.05, abs_tol=1):
                    return True
            except (ValueError, TypeError):
                continue
    
    return False


def recent_user_messages(messages, limit=10):
    """Keep customer context while excluding assistant claims from prior turns."""
    return [
        {"role": "user", "content": item["content"]}
        for item in messages[-limit:]
        if item.get("role") == "user"
    ]


def safe_calculation_reply(calc):
    if not calculation_is_valid(calc):
        return "Для предварительного расчёта выберите режим и проверьте параметры. Сейчас корректный расчёт недоступен."
    
    power = calc["recommended_power_kw"]
    cost = f'{calc["estimated_cost_rub"]:,.0f}'.replace(",", " ")
    lines = [f"По выбранным параметрам предварительно получается мощность {power} кВт, стоимость — {cost} руб."]
    
    # ИСПРАВЛЕНО: убран лишний отступ и дублирующийся блок else
    payback = calc.get("payback_years")
    if payback is not None and payback > 0:
        lines.append(f'Расчётная окупаемость — {payback} года. Это оценка, не гарантия; точные параметры проверит специалист.')
    else:
        lines.append("Срок окупаемости: не применяется — это резервная система для надёжности, а не для экономии. Однако гибридная СЭС также снижает ваши счета на 30-50% летом, что частично компенсирует стоимость.")
    
    lines.append("\n\n🚀 Это предварительный расчет. Точную смету даст инженер после замера. Заполните форму «Бесплатный расчет станции» справа — свяжемся за 15 минут! 👇")
    
    return " ".join(lines)
