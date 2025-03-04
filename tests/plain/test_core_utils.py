import unittest

from apps.core.utils import split_value_among_segments


def get_segment_value_setter(segment_values):
    def set_segment_value(i, v):
        segment_values[i] = segment_values[i] + (v if v else 0)
    return set_segment_value


class FillStackedChartDatasetsTests(unittest.TestCase):
    def test_throws_on_invalid_arguments(self):
        with self.assertRaises(ValueError):
            split_value_among_segments(0, [], None)

    def test_lower_than_first_segment(self):
        # ARRANGE
        segment_values = [0, 0]
        # ACT
        split_value_among_segments(3, [5, 10], get_segment_value_setter(segment_values))
        # ASSERT
        self.assertEqual(3, segment_values[0])
        self.assertEqual(0, segment_values[1])

    def test_higher_than_first_segment(self):
        # ARRANGE
        segment_values = [0, 0]
        # ACT
        split_value_among_segments(8, [5, 10], get_segment_value_setter(segment_values))
        # ASSERT
        self.assertEqual(5, segment_values[0])
        self.assertEqual(3, segment_values[1])

    def test_higher_than_last_segment_with_clipping(self):
        # ARRANGE
        segment_values = [0, 0]
        # ACT
        split_value_among_segments(12, [5, 10], get_segment_value_setter(segment_values))
        # ASSERT
        self.assertEqual(5, segment_values[0])
        self.assertEqual(5, segment_values[1])

    def test_higher_than_last_segment_without_clipping(self):
        # ARRANGE
        segment_values = [0, 0]
        # ACT
        split_value_among_segments(12, [5, 10], get_segment_value_setter(segment_values), clip_peak=False)
        # ASSERT
        self.assertEqual(5, segment_values[0])
        self.assertEqual(7, segment_values[1])
