import unittest

from src.fases_temporais import cue_matches, mask, rule_phase


def phase_of(sentence, term):
    start = sentence.index(term)
    phase, _ = rule_phase(start, start + len(term), cue_matches(sentence))
    return phase


class FasesTemporaisTest(unittest.TestCase):
    def test_short_history_is_presentation(self):
        sentence = "A 44-year-old woman presented with a 3-day history of abdominal pain."
        self.assertEqual(phase_of(sentence, "abdominal pain"), "APRESENTACAO")

    def test_history_of_is_antecedent(self):
        sentence = "She had a history of hypertension."
        self.assertEqual(phase_of(sentence, "hypertension"), "ANTECEDENTE")

    def test_years_ago_beats_underwent(self):
        sentence = "She underwent appendectomy five years ago."
        self.assertEqual(phase_of(sentence, "appendectomy"), "ANTECEDENTE")

    def test_postoperative_day_is_course(self):
        sentence = "On POD 3 a CT was performed."
        self.assertEqual(phase_of(sentence, "CT"), "CURSO")

    def test_months_later_is_follow_up(self):
        sentence = "Six months later, the patient complained of dyspnea."
        self.assertEqual(phase_of(sentence, "dyspnea"), "SEGUIMENTO")

    def test_without_cue_returns_none(self):
        sentence = "Laboratory findings showed anemia."
        self.assertIsNone(phase_of(sentence, "anemia"))

    def test_mask_removes_cues_and_keeps_offsets(self):
        sentence = "She had a history of hypertension."
        masked = mask(sentence, cue_matches(sentence))
        self.assertEqual(len(masked), len(sentence))
        self.assertNotIn("history", masked)
        self.assertIn("hypertension", masked)


if __name__ == "__main__":
    unittest.main()
