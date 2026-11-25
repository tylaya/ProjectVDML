import unittest

from location_analysis import (
    haversine_km,
    is_in_north_sulawesi,
    parse_google_maps_coordinates,
)


class LocationAnalysisTests(unittest.TestCase):
    def test_extracts_coordinates_from_supported_google_maps_urls(self):
        self.assertEqual(
            parse_google_maps_coordinates(
                "https://www.google.com/maps/@1.45,124.97,16z"
            ),
            (1.45, 124.97),
        )
        self.assertEqual(
            parse_google_maps_coordinates(
                "https://www.google.com/maps/dir/?api=1&destination=1.45%2C124.97"
            ),
            (1.45, 124.97),
        )
        self.assertEqual(
            parse_google_maps_coordinates(
                "https://www.google.com/maps/place/test/data=!3d1.45!4d124.97"
            ),
            (1.45, 124.97),
        )

    def test_rejects_short_links_without_coordinates_and_non_google_hosts(self):
        with self.assertRaisesRegex(ValueError, "harus memuat koordinat"):
            parse_google_maps_coordinates("https://maps.app.goo.gl/example")
        with self.assertRaisesRegex(ValueError, "Google Maps"):
            parse_google_maps_coordinates("https://maps.example.com/@1.45,124.97")

    def test_distance_and_province_geofence(self):
        self.assertAlmostEqual(
            haversine_km((0, 0), (0, 1)),
            111.195,
            places=2,
        )
        self.assertTrue(is_in_north_sulawesi(1.45, 124.97))
        self.assertFalse(is_in_north_sulawesi(-2.0, 120.0))


if __name__ == "__main__":
    unittest.main()
