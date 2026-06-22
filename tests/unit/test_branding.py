import unittest

from src.aso_platform.ui.branding import APP_TAGLINE, KITE_ASCII_LOGO, render_kite_logo


class BrandingTests(unittest.TestCase):
    def test_ascii_logo_contains_expected_block_art(self):
        self.assertIn("████████", KITE_ASCII_LOGO)

    def test_render_kite_logo_returns_ascii_logo_in_default_mode(self):
        rendered = render_kite_logo(compact=False, with_tagline=False)
        self.assertTrue("██╗" in rendered or "KITE" in rendered)

    def test_render_kite_logo_compact_fallback(self):
        rendered = render_kite_logo(compact=True, with_tagline=True)
        self.assertIn("KITE", rendered)
        self.assertIn(APP_TAGLINE, rendered)


if __name__ == "__main__":
    unittest.main()
