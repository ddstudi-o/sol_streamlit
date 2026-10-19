"""Helpers that keep model replies tied to the active Python calculation."""

import math
import re

ECONOMY_MODE = "Экономия бюджета (Сетевая СЭС)"
BACKUP_MODE = "Защита от отключений / Резерв (Гибридная СЭС)"


def calculate_economy_values(monthly_bill, tariff, phases, insolation, consumption_time):
    """Current sidebar economy calculation, kept unchanged for reuse and tests."""
    price_per_kw = 85000 if "1 фаза" in phases else 95000
    monthly_consumption_kwh = monthly_bill / tariff if tariff > 0 else 0
    power = max(3.0, min(round(monthly_consumption_kwh / 300, 1), 50.0))
    cost = round(power * price_per_kw)
    annual_consumption_kwh = monthly_consumption_kwh * 12
    annual_generation_kwh = power * 1000 * insolation
    self_consumption_ratio = 0.8 if consumption_time.startswith("Днем") else 0.4
    used_generation_kwh = annual_generation_kwh * self_consumption_ratio
    actual_offset_kwh = min(used_generation_kwh, annual_consumption_kwh)
    annual_savings_rub = actual_offset_kwh * tariff
    payback = round(cost / annual_savings_rub, 1) if annual_savings_rub > 0 else 99.0
    return power, cost, payback


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
    return float(raw.replace(" ", "").replace("\u00a0", "").replace(",", "."))


def answer_has_calculation_conflict(answer, calc):
    """Check numeric claims only when paired with a relevant unit/label."""
    number = r"(\d[\d\s\u00a0]*(?:[,.]\d+)?)"
    checks = [
        ("recommended_power_kw", rf"{number}\s*(?:квт|киловат(?:т|та|тов)?)\b"),
        ("estimated_cost_rub", rf"{number}\s*(?:руб(?:\.|лей|ля|лям)?|₽)(?![а-я])"),
        ("payback_years", rf"{number}\s*(?:лет|года|год|годах)\b"),
    ]
    if not calculation_is_valid(calc):
        return any(re.search(pattern, answer or "", re.IGNORECASE) for _, pattern in checks)
    for key, pattern in checks:
        expected = calc.get(key)
        if expected is None or not isinstance(expected, (int, float)):
            continue
        for match in re.finditer(pattern, answer or "", re.IGNORECASE):
            try:
                actual = _normalize_number(match.group(1))
            except ValueError:
                continue
            if not math.isclose(actual, float(expected), rel_tol=0, abs_tol=0.051):
                return True
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
    if calc.get("payback_years") is not None:
        lines.append(f'Расчётная окупаемость — {calc["payback_years"]} года. Это оценка, не гарантия; точные параметры проверит специалист.')
    else:
        lines.append("Расчётная окупаемость для этого режима не применяется.")
    return " ".join(lines)
# ==========================================
# РАСЧЁТ ГИБРИДНОЙ СЭС (РЕЗЕРВ)
# ==========================================
def calculate_backup_values(phases: str, blackout_duration: str) -> tuple:
    """
    Расчёт рекомендуемой мощности и стоимости для гибридной СЭС (резерв).
    Окупаемость не применяется для резервных систем.
    """
    # Рекомендуемая мощность: 5 кВт для 1 фазы, 15 кВт для 3 фаз
    recommended_power = 5.0 if "1 фаза" in phases else 15.0
    
    # Коэффициенты длительности отключений
    duration_mult = {
        "1-3 часа": 1.0,
        "До 6 часов": 1.35,
        "Сутки и более": 1.85
    }
    mult = duration_mult.get(blackout_duration, 1.0)
    
    # Стоимость: мощность * 140000 руб/кВт * коэффициент
    estimated_cost = round(recommended_power * 140000 * mult)
    
    # Окупаемость не применяется для резервных систем
    payback_years = None
    
    return recommended_power, estimated_cost, payback_years


# ==========================================
# УЛУЧШЕННЫЙ ДЕТЕКТОР ПРОТИВОРЕЧИЙ
# ==========================================
def answer_has_calculation_conflict(answer: str, calc: dict) -> bool:
    """
    Проверяет, содержит ли ответ модели числовые противоречия с CURRENT_CALCULATION.
    Улучшенная версия: распознаёт "тыс.", "млн", различает кВт и кВт·ч.
    """
    if not answer or not calc:
        return False
    
    # Нормализация чисел: "285 тыс." → 285000, "2,835 млн" → 2835000
    def normalize_number(text: str) -> float:
        text = text.replace(" ", "").replace(",", ".")
        if "тыс" in text.lower():
            return float(text.replace("тыс", "").replace(".", "")) * 1000
        if "млн" in text.lower():
            return float(text.replace("млн", "").replace(".", "")) * 1000000
        return float(text.replace(".", "").replace(",", "."))
    
    # Паттерны для поиска чисел с единицами
    number_pattern = r"(\d[\d\s,.]*\d)"
    
    checks = [
        ("recommended_power_kw", rf"{number_pattern}\s*(?:квт|киловат(?:т|та|тов)?)\b(?!\s*·\s*ч)"),
        ("estimated_cost_rub", rf"{number_pattern}\s*(?:тыс\.?\s*)?(?:руб(?:\.|лей|ля|лям)?|₽)(?![а-я])"),
        ("estimated_cost_rub", rf"{number_pattern}\s*(?:млн\.?\s*)?(?:руб(?:\.|лей|ля|лям)?|₽)(?![а-я])"),
        ("payback_years", rf"{number_pattern}\s*(?:лет|года|год|годах)\b"),
    ]
    
    for key, pattern in checks:
        expected = calc.get(key)
        if expected is None:
            continue
        
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            try:
                actual = normalize_number(match.group(1))
                # Допуск 5% для округлений
                if not math.isclose(actual, float(expected), rel_tol=0.05, abs_tol=1):
                    return True
            except (ValueError, TypeError):
                continue
    
    return False
