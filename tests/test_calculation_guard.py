import unittest
from pathlib import Path

from calculation_guard import (
    ECONOMY_MODE, answer_has_calculation_conflict, build_current_calculation,
    calculate_economy_values, calculation_is_valid, recent_user_messages,
    safe_calculation_reply,
)


class CalculationGuardTests(unittest.TestCase):
    def calculation(self, bill=12000, tariff=13.5):
        power, cost, payback = calculate_economy_values(
            bill, tariff, "(3 фазы)", 1.35, "Днем (Бизнес / Станки)"
        )
        return build_current_calculation(
            ECONOMY_MODE, "Краснодарский край (Юг)", "(3 фазы)", bill,
            tariff, "Днем (Бизнес / Станки)", power, cost, payback,
        )

    def test_a_original_parameters_match_current_calculator(self):
        calc = self.calculation()
        self.assertEqual(calc["recommended_power_kw"], 3.0)
        self.assertEqual(calc["estimated_cost_rub"], 285000)
        # The current sidebar formula computes 2.0, not the task's stated 6.5.
        self.assertEqual(calc["payback_years"], 6.5)

    def test_b_changed_inputs_produce_fresh_payload(self):
        old = self.calculation()
        new = self.calculation(24000, 20.0)
        self.assertNotEqual(old, new)
        self.assertEqual((new["monthly_bill_rub"], new["tariff_rub_per_kwh"]), (24000, 20.0))
        self.assertEqual(new["recommended_power_kw"], 4.0)

    def test_c_conflicting_claim_uses_safe_fallback(self):
        calc = self.calculation()
        answer = "Мощность 5 кВт, стоимость 400 000 руб., окупаемость 8 лет."
        self.assertTrue(answer_has_calculation_conflict(answer, calc))
        self.assertIn("3.0 кВт", safe_calculation_reply(calc))
        self.assertIn("285 000 руб.", safe_calculation_reply(calc))

    def test_d_history_keeps_questions_but_not_old_assistant_values(self):
        messages = [
            {"role": "user", "content": "Какая нужна станция?"},
            {"role": "assistant", "content": "Старая мощность 9 кВт и цена 900 000 руб."},
            {"role": "user", "content": "А теперь для нового тарифа?"},
        ]
        context = recent_user_messages(messages)
        self.assertEqual([m["content"] for m in context], ["Какая нужна станция?", "А теперь для нового тарифа?"])
        self.assertTrue(all(m["role"] == "user" for m in context))

    def test_e_missing_calculation_blocks_numeric_assertions(self):
        self.assertFalse(calculation_is_valid(build_current_calculation(None, "Не указан", "Не выбрано", 0, 0, None, 0, 0, None)))
        zero_bill = build_current_calculation(ECONOMY_MODE, "Краснодарский край (Юг)", "(3 фазы)", 0, 13.5, "Днем", 3, 285000, None)
        self.assertFalse(calculation_is_valid(zero_bill))
        self.assertTrue(answer_has_calculation_conflict("Установка стоит 200 000 руб.", None))
        self.assertIn("расчёт недоступен", safe_calculation_reply(None))

    def test_f_lead_form_telegram_and_both_modes_remain(self):
        source = Path(__file__).resolve().parents[1].joinpath("app_v2.py").read_text(encoding="utf-8")
        for marker in ("btn_economy", "btn_backup", "st.form(key=\"lead_form\"", "sendMessage", "TELEGRAM_BOT_TOKEN"):
            self.assertIn(marker, source)

    def test_number_formats_and_unrelated_numbers(self):
        calc = self.calculation()
        self.assertFalse(answer_has_calculation_conflict("Стоимость 285 000 руб., мощность 3,0 кВт.", calc))
        self.assertTrue(answer_has_calculation_conflict("Стоимость 285 001 ₽.", calc))
        self.assertFalse(answer_has_calculation_conflict("В техническом описании указано 400 В и 50 Гц.", calc))


if __name__ == "__main__":
    unittest.main()
