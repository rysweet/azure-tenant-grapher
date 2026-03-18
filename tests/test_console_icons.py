"""
Comprehensive tests for console_icons utility (TDD red phase).

Tests platform detection, icon constants, and function API.
All tests should FAIL initially until console_icons.py is implemented.
"""

import importlib
import sys
import unittest
from unittest.mock import patch


class TestPlatformDetection(unittest.TestCase):
    """Test platform detection and PLATFORM_IS_WINDOWS constant."""

    def test_windows_platform_detection(self):
        """Test Windows platform is correctly detected."""
        with patch.object(sys, 'platform', 'win32'):
            # Force reload to pick up mocked platform
            import src.utils.console_icons
            importlib.reload(src.utils.console_icons)

            self.assertTrue(
                src.utils.console_icons.PLATFORM_IS_WINDOWS,
                "PLATFORM_IS_WINDOWS should be True on Windows"
            )

    def test_linux_platform_detection(self):
        """Test Linux platform is correctly detected."""
        with patch.object(sys, 'platform', 'linux'):
            import src.utils.console_icons
            importlib.reload(src.utils.console_icons)

            self.assertFalse(
                src.utils.console_icons.PLATFORM_IS_WINDOWS,
                "PLATFORM_IS_WINDOWS should be False on Linux"
            )

    def test_macos_platform_detection(self):
        """Test macOS platform is correctly detected."""
        with patch.object(sys, 'platform', 'darwin'):
            import src.utils.console_icons
            importlib.reload(src.utils.console_icons)

            self.assertFalse(
                src.utils.console_icons.PLATFORM_IS_WINDOWS,
                "PLATFORM_IS_WINDOWS should be False on macOS"
            )


class TestIconConstantsExistence(unittest.TestCase):
    """Test that all 30 icon constants exist."""

    def setUp(self):
        """Import module for testing."""
        import src.utils.console_icons
        self.icons = src.utils.console_icons

    def test_status_icons_exist(self):
        """Test status-related icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_SUCCESS'))
        self.assertTrue(hasattr(self.icons, 'ICON_ERROR'))
        self.assertTrue(hasattr(self.icons, 'ICON_WARNING'))
        self.assertTrue(hasattr(self.icons, 'ICON_INFO'))
        self.assertTrue(hasattr(self.icons, 'ICON_QUESTION'))

    def test_action_icons_exist(self):
        """Test action-related icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_ROCKET'))
        self.assertTrue(hasattr(self.icons, 'ICON_SEARCH'))
        self.assertTrue(hasattr(self.icons, 'ICON_DOWNLOAD'))
        self.assertTrue(hasattr(self.icons, 'ICON_UPLOAD'))
        self.assertTrue(hasattr(self.icons, 'ICON_REFRESH'))

    def test_symbol_icons_exist(self):
        """Test symbol-related icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_ARROW_RIGHT'))
        self.assertTrue(hasattr(self.icons, 'ICON_ARROW_DOWN'))
        self.assertTrue(hasattr(self.icons, 'ICON_BULLET'))
        self.assertTrue(hasattr(self.icons, 'ICON_CHECKMARK'))
        self.assertTrue(hasattr(self.icons, 'ICON_CROSS'))

    def test_object_icons_exist(self):
        """Test object-related icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_FILE'))
        self.assertTrue(hasattr(self.icons, 'ICON_FOLDER'))
        self.assertTrue(hasattr(self.icons, 'ICON_PACKAGE'))
        self.assertTrue(hasattr(self.icons, 'ICON_GEAR'))
        self.assertTrue(hasattr(self.icons, 'ICON_LOCK'))

    def test_progress_icons_exist(self):
        """Test progress-related icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_HOURGLASS'))
        self.assertTrue(hasattr(self.icons, 'ICON_SPINNER'))
        self.assertTrue(hasattr(self.icons, 'ICON_CLOCK'))
        self.assertTrue(hasattr(self.icons, 'ICON_CALENDAR'))
        self.assertTrue(hasattr(self.icons, 'ICON_BELL'))

    def test_misc_icons_exist(self):
        """Test miscellaneous icon constants exist."""
        self.assertTrue(hasattr(self.icons, 'ICON_STAR'))
        self.assertTrue(hasattr(self.icons, 'ICON_HEART'))
        self.assertTrue(hasattr(self.icons, 'ICON_FIRE'))
        self.assertTrue(hasattr(self.icons, 'ICON_LIGHTNING'))
        self.assertTrue(hasattr(self.icons, 'ICON_GLOBE'))


class TestWindowsIconMapping(unittest.TestCase):
    """Test Windows platform uses ASCII fallbacks."""

    def setUp(self):
        """Force Windows platform for all tests."""
        self.platform_patcher = patch.object(sys, 'platform', 'win32')
        self.platform_patcher.start()

        import src.utils.console_icons
        importlib.reload(src.utils.console_icons)
        self.icons = src.utils.console_icons

    def tearDown(self):
        """Restore original platform."""
        self.platform_patcher.stop()

    def test_windows_status_icons_are_ascii(self):
        """Test status icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_SUCCESS, '[OK]')
        self.assertEqual(self.icons.ICON_ERROR, '[X]')
        self.assertEqual(self.icons.ICON_WARNING, '[!]')
        self.assertEqual(self.icons.ICON_INFO, '[i]')
        self.assertEqual(self.icons.ICON_QUESTION, '[?]')

    def test_windows_action_icons_are_ascii(self):
        """Test action icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_ROCKET, '[^]')
        self.assertEqual(self.icons.ICON_SEARCH, '[?]')
        self.assertEqual(self.icons.ICON_DOWNLOAD, '[v]')
        self.assertEqual(self.icons.ICON_UPLOAD, '[^]')
        self.assertEqual(self.icons.ICON_REFRESH, '[R]')

    def test_windows_symbol_icons_are_ascii(self):
        """Test symbol icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_ARROW_RIGHT, '->')
        self.assertEqual(self.icons.ICON_ARROW_DOWN, 'v')
        self.assertEqual(self.icons.ICON_BULLET, '*')
        self.assertEqual(self.icons.ICON_CHECKMARK, '[OK]')
        self.assertEqual(self.icons.ICON_CROSS, '[X]')

    def test_windows_object_icons_are_ascii(self):
        """Test object icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_FILE, '[F]')
        self.assertEqual(self.icons.ICON_FOLDER, '[D]')
        self.assertEqual(self.icons.ICON_PACKAGE, '[P]')
        self.assertEqual(self.icons.ICON_GEAR, '[*]')
        self.assertEqual(self.icons.ICON_LOCK, '[#]')

    def test_windows_progress_icons_are_ascii(self):
        """Test progress icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_HOURGLASS, '[:]')
        self.assertEqual(self.icons.ICON_SPINNER, '[o]')
        self.assertEqual(self.icons.ICON_CLOCK, '[T]')
        self.assertEqual(self.icons.ICON_CALENDAR, '[C]')
        self.assertEqual(self.icons.ICON_BELL, '[B]')

    def test_windows_misc_icons_are_ascii(self):
        """Test miscellaneous icons on Windows are ASCII."""
        self.assertEqual(self.icons.ICON_STAR, '[*]')
        self.assertEqual(self.icons.ICON_HEART, '[<3]')
        self.assertEqual(self.icons.ICON_FIRE, '[~]')
        self.assertEqual(self.icons.ICON_LIGHTNING, '[!]')
        self.assertEqual(self.icons.ICON_GLOBE, '[@]')


class TestUnixIconMapping(unittest.TestCase):
    """Test Unix platforms use Unicode emojis."""

    def setUp(self):
        """Force Linux platform for all tests."""
        self.platform_patcher = patch.object(sys, 'platform', 'linux')
        self.platform_patcher.start()

        import src.utils.console_icons
        importlib.reload(src.utils.console_icons)
        self.icons = src.utils.console_icons

    def tearDown(self):
        """Restore original platform."""
        self.platform_patcher.stop()

    def test_unix_status_icons_are_unicode(self):
        """Test status icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_SUCCESS, '✅')
        self.assertEqual(self.icons.ICON_ERROR, '❌')
        self.assertEqual(self.icons.ICON_WARNING, '⚠️')
        self.assertEqual(self.icons.ICON_INFO, 'ℹ️')
        self.assertEqual(self.icons.ICON_QUESTION, '❓')

    def test_unix_action_icons_are_unicode(self):
        """Test action icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_ROCKET, '🚀')
        self.assertEqual(self.icons.ICON_SEARCH, '🔍')
        self.assertEqual(self.icons.ICON_DOWNLOAD, '⬇️')
        self.assertEqual(self.icons.ICON_UPLOAD, '⬆️')
        self.assertEqual(self.icons.ICON_REFRESH, '🔄')

    def test_unix_symbol_icons_are_unicode(self):
        """Test symbol icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_ARROW_RIGHT, '→')
        self.assertEqual(self.icons.ICON_ARROW_DOWN, '↓')
        self.assertEqual(self.icons.ICON_BULLET, '•')
        self.assertEqual(self.icons.ICON_CHECKMARK, '✓')
        self.assertEqual(self.icons.ICON_CROSS, '✗')

    def test_unix_object_icons_are_unicode(self):
        """Test object icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_FILE, '📄')
        self.assertEqual(self.icons.ICON_FOLDER, '📁')
        self.assertEqual(self.icons.ICON_PACKAGE, '📦')
        self.assertEqual(self.icons.ICON_GEAR, '⚙️')
        self.assertEqual(self.icons.ICON_LOCK, '🔒')

    def test_unix_progress_icons_are_unicode(self):
        """Test progress icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_HOURGLASS, '⏳')
        self.assertEqual(self.icons.ICON_SPINNER, '⌛')
        self.assertEqual(self.icons.ICON_CLOCK, '🕐')
        self.assertEqual(self.icons.ICON_CALENDAR, '📅')
        self.assertEqual(self.icons.ICON_BELL, '🔔')

    def test_unix_misc_icons_are_unicode(self):
        """Test miscellaneous icons on Unix are Unicode emojis."""
        self.assertEqual(self.icons.ICON_STAR, '⭐')
        self.assertEqual(self.icons.ICON_HEART, '❤️')
        self.assertEqual(self.icons.ICON_FIRE, '🔥')
        self.assertEqual(self.icons.ICON_LIGHTNING, '⚡')
        self.assertEqual(self.icons.ICON_GLOBE, '🌐')


class TestGetIconFunction(unittest.TestCase):
    """Test get_icon() function API."""

    def setUp(self):
        """Import module for testing."""
        import src.utils.console_icons
        self.icons = src.utils.console_icons

    def test_get_icon_success_lowercase(self):
        """Test get_icon('success') returns ICON_SUCCESS."""
        result = self.icons.get_icon('success')
        self.assertEqual(result, self.icons.ICON_SUCCESS)

    def test_get_icon_success_uppercase(self):
        """Test get_icon('SUCCESS') is case-insensitive."""
        result = self.icons.get_icon('SUCCESS')
        self.assertEqual(result, self.icons.ICON_SUCCESS)

    def test_get_icon_success_mixed_case(self):
        """Test get_icon('SuCcEsS') is case-insensitive."""
        result = self.icons.get_icon('SuCcEsS')
        self.assertEqual(result, self.icons.ICON_SUCCESS)

    def test_get_icon_with_icon_prefix(self):
        """Test get_icon('icon_success') strips prefix."""
        result = self.icons.get_icon('icon_success')
        self.assertEqual(result, self.icons.ICON_SUCCESS)

    def test_get_icon_unknown_returns_default(self):
        """Test get_icon('unknown') returns default '?'."""
        result = self.icons.get_icon('nonexistent_icon')
        self.assertEqual(result, '?')

    def test_get_icon_unknown_custom_default(self):
        """Test get_icon('unknown', default='X') returns 'X'."""
        result = self.icons.get_icon('nonexistent_icon', default='X')
        self.assertEqual(result, 'X')

    def test_get_icon_empty_string_returns_default(self):
        """Test get_icon('') returns default."""
        result = self.icons.get_icon('')
        self.assertEqual(result, '?')

    def test_get_icon_all_30_icons_accessible(self):
        """Test all 30 icons are accessible via get_icon()."""
        icon_names = [
            'success', 'error', 'warning', 'info', 'question',
            'rocket', 'search', 'download', 'upload', 'refresh',
            'arrow_right', 'arrow_down', 'bullet', 'checkmark', 'cross',
            'file', 'folder', 'package', 'gear', 'lock',
            'hourglass', 'spinner', 'clock', 'calendar', 'bell',
            'star', 'heart', 'fire', 'lightning', 'globe'
        ]

        for name in icon_names:
            result = self.icons.get_icon(name)
            self.assertNotEqual(
                result, '?',
                f"Icon '{name}' should be accessible via get_icon()"
            )


class TestWindowsIntegration(unittest.TestCase):
    """Test Windows-specific integration scenarios."""

    def setUp(self):
        """Force Windows platform."""
        self.platform_patcher = patch.object(sys, 'platform', 'win32')
        self.platform_patcher.start()

        import src.utils.console_icons
        importlib.reload(src.utils.console_icons)
        self.icons = src.utils.console_icons

    def tearDown(self):
        """Restore original platform."""
        self.platform_patcher.stop()

    def test_no_unicode_encode_error_on_windows(self):
        """Test all icons can be encoded on Windows console."""
        icon_names = [
            'success', 'error', 'warning', 'info', 'question',
            'rocket', 'search', 'download', 'upload', 'refresh',
            'arrow_right', 'arrow_down', 'bullet', 'checkmark', 'cross',
            'file', 'folder', 'package', 'gear', 'lock',
            'hourglass', 'spinner', 'clock', 'calendar', 'bell',
            'star', 'heart', 'fire', 'lightning', 'globe'
        ]

        # Windows console typically uses cp1252 or cp437
        for name in icon_names:
            icon = self.icons.get_icon(name)
            try:
                icon.encode('cp1252')
                icon.encode('cp437')
            except UnicodeEncodeError:
                self.fail(
                    f"Icon '{name}' ('{icon}') cannot be encoded "
                    "on Windows console"
                )

    def test_windows_icons_are_ascii_only(self):
        """Test Windows icons contain only ASCII characters."""
        icon_names = [
            'success', 'error', 'warning', 'info', 'question',
            'rocket', 'search', 'download', 'upload', 'refresh',
            'arrow_right', 'arrow_down', 'bullet', 'checkmark', 'cross',
            'file', 'folder', 'package', 'gear', 'lock',
            'hourglass', 'spinner', 'clock', 'calendar', 'bell',
            'star', 'heart', 'fire', 'lightning', 'globe'
        ]

        for name in icon_names:
            icon = self.icons.get_icon(name)
            self.assertTrue(
                all(ord(c) < 128 for c in icon),
                f"Icon '{name}' ('{icon}') contains non-ASCII characters"
            )


class TestUnixIntegration(unittest.TestCase):
    """Test Unix-specific integration scenarios."""

    def setUp(self):
        """Force Linux platform."""
        self.platform_patcher = patch.object(sys, 'platform', 'linux')
        self.platform_patcher.start()

        import src.utils.console_icons
        importlib.reload(src.utils.console_icons)
        self.icons = src.utils.console_icons

    def tearDown(self):
        """Restore original platform."""
        self.platform_patcher.stop()

    def test_unix_icons_contain_unicode(self):
        """Test Unix icons contain Unicode characters."""
        icon_names = [
            'success', 'error', 'warning', 'info', 'question',
            'rocket', 'search', 'fire', 'lightning', 'globe'
        ]

        for name in icon_names:
            icon = self.icons.get_icon(name)
            self.assertTrue(
                any(ord(c) > 127 for c in icon),
                f"Icon '{name}' ('{icon}') should contain Unicode characters"
            )

    def test_unix_icons_can_be_encoded_utf8(self):
        """Test all Unix icons can be encoded as UTF-8."""
        icon_names = [
            'success', 'error', 'warning', 'info', 'question',
            'rocket', 'search', 'download', 'upload', 'refresh',
            'arrow_right', 'arrow_down', 'bullet', 'checkmark', 'cross',
            'file', 'folder', 'package', 'gear', 'lock',
            'hourglass', 'spinner', 'clock', 'calendar', 'bell',
            'star', 'heart', 'fire', 'lightning', 'globe'
        ]

        for name in icon_names:
            icon = self.icons.get_icon(name)
            try:
                icon.encode('utf-8')
            except UnicodeEncodeError:
                self.fail(
                    f"Icon '{name}' ('{icon}') cannot be encoded as UTF-8"
                )


if __name__ == '__main__':
    unittest.main()
