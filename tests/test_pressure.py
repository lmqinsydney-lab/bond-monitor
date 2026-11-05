import unittest

from pressure import pressure_band, standard_pressure, weighted_pressure


class PressureTest(unittest.TestCase):
    def test_standard_pressure_center_and_clamp(self) -> None:
        self.assertEqual(standard_pressure(0, 0), 50)
        self.assertEqual(standard_pressure(100, 100), 100)
        self.assertEqual(standard_pressure(-100, -100), 0)

    def test_bands(self) -> None:
        self.assertEqual(pressure_band(35), "low")
        self.assertEqual(pressure_band(36), "watch")
        self.assertEqual(pressure_band(65), "high")
        self.assertEqual(pressure_band(None), "insufficient")

    def test_missing_weight_threshold(self) -> None:
        result = weighted_pressure({"a": 40, "b": None}, {"a": 0.8, "b": 0.2})
        self.assertEqual(result.score, 40)
        self.assertEqual(result.confidence_adjustment, "lowered")
        blocked = weighted_pressure({"a": 40, "b": None}, {"a": 0.79, "b": 0.21})
        self.assertIsNone(blocked.score)


if __name__ == "__main__":
    unittest.main()

