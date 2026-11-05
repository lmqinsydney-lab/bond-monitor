import unittest

from correlation import correlation_strength, pearson_result


class CorrelationTest(unittest.TestCase):
    def test_perfect_positive_and_negative(self) -> None:
        positive = pearson_result([(value, value * 2) for value in range(20)])
        negative = pearson_result([(value, -value) for value in range(20)])
        self.assertEqual(positive["r"], 1.0)
        self.assertEqual(positive["strength"], "very_strong")
        self.assertEqual(negative["r"], -1.0)
        self.assertEqual(negative["direction"], "negative")

    def test_insufficient_and_constant(self) -> None:
        self.assertEqual(pearson_result([(1, 2)] * 19)["strength"], "insufficient")
        self.assertEqual(pearson_result([(1, value) for value in range(20)])["strength"], "constant")

    def test_strength_boundaries(self) -> None:
        self.assertEqual(correlation_strength(0.19), "very_weak")
        self.assertEqual(correlation_strength(-0.2), "weak")
        self.assertEqual(correlation_strength(0.4), "moderate")
        self.assertEqual(correlation_strength(-0.6), "strong")
        self.assertEqual(correlation_strength(0.8), "very_strong")


if __name__ == "__main__":
    unittest.main()
