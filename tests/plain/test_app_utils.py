import unittest

from app.utils import convert_web_app_route_points


class ConvertWebAppRoutePointsTests(unittest.TestCase):
    def test_empty_array_retuned_if_no_points(self):
        # ARRANGE & ACT
        result = convert_web_app_route_points([], None)
        # ASSERT
        self.assertEqual(0, len(result))

    def test_throws_key_error_on_unexpected_input(self):
        # ARRANGE
        input = [{'foo': 'bar'}]
        # ACT & ASSERT
        with self.assertRaises(KeyError):
            convert_web_app_route_points(input, None)

    def test_converts_values_as_needed(self):
        # ARRANGE
        input = self._generate_valid_input(2)
        # ACT
        result = convert_web_app_route_points(input, 'foo')
        # ASSERT
        self.assertEqual(2, len(result))
        for i in range(1, 3):
            source_point = input[i - 1]
            result_point = result[i - 1]
            self.assertEqual(source_point['id'], result_point['id'])
            self.assertEqual(source_point['city']['title'], result_point['city'])
            self.assertEqual(source_point['fullness']['value'], result_point['fullness'])
            self.assertEqual(source_point['address'], result_point['address'])
            self.assertEqual(source_point['serial_number'], result_point['title'])
            self.assertEqual(source_point['location']['y'], result_point['latitude'])
            self.assertEqual(source_point['location']['x'], result_point['longitude'])
            self.assertEqual('foo', result_point['volume'])

    def test_point_volume_is_used_if_present(self):
        # ARRANGE
        input = self._generate_valid_input(1)
        input[0]['current_fullness_volume'] = 'bar'
        # ACT
        result = convert_web_app_route_points(input, 'foo')
        # ASSERT
        self.assertEqual(1, len(result))
        self.assertEqual('bar', result[0]['volume'])

    def _generate_valid_input(self, count):
        return [
            {
                'id': i,
                'city': {'title': 'city_title_{}'.format(i)},
                'fullness': {'value': i},
                'address': 'address_{}'.format(i),
                'serial_number': 'serial_{}'.format(i),
                'location': {'x': 10 + i, 'y': 20 + i},
            } for i in range(1, 1 + count)
        ]
