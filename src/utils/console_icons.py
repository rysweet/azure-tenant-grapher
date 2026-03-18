"""
Console icon utility for cross-platform emoji support.

Provides platform-aware icons that use ASCII fallbacks on Windows
to prevent UnicodeEncodeError, while preserving emoji behavior on Unix-like systems.

Platform Detection:
    PLATFORM_IS_WINDOWS: bool - True on Windows, False on Unix-like systems

Icon Constants (33 total):
    Status: ICON_SUCCESS, ICON_ERROR, ICON_WARNING, ICON_INFO, ICON_QUESTION
    Actions: ICON_ROCKET, ICON_SEARCH, ICON_DOWNLOAD, ICON_UPLOAD, ICON_REFRESH
    Symbols: ICON_ARROW_RIGHT, ICON_ARROW_DOWN, ICON_BULLET, ICON_CHECKMARK, ICON_CROSS
    Objects: ICON_FILE, ICON_FOLDER, ICON_PACKAGE, ICON_GEAR, ICON_LOCK
    Progress: ICON_HOURGLASS, ICON_SPINNER, ICON_CLOCK, ICON_CALENDAR, ICON_BELL
    Misc: ICON_STAR, ICON_HEART, ICON_FIRE, ICON_LIGHTNING, ICON_GLOBE, ICON_TRASH, ICON_LIGHTBULB, ICON_ITERATION

Function API:
    get_icon(name, default='?') - Get icon by name (case-insensitive)

Example:
    >>> from src.utils.console_icons import ICON_SUCCESS, get_icon
    >>> print(f"{ICON_SUCCESS} Operation completed")
    >>> print(f"{get_icon('error')} Operation failed")
"""

import sys

# Platform detection at module import
PLATFORM_IS_WINDOWS = sys.platform.startswith('win')

# Status Icons
if PLATFORM_IS_WINDOWS:
    ICON_SUCCESS = '[OK]'
    ICON_ERROR = '[X]'
    ICON_WARNING = '[!]'
    ICON_INFO = '[i]'
    ICON_QUESTION = '[?]'
else:
    ICON_SUCCESS = '✅'
    ICON_ERROR = '❌'
    ICON_WARNING = '⚠️'
    ICON_INFO = 'ℹ️'
    ICON_QUESTION = '❓'

# Action Icons
if PLATFORM_IS_WINDOWS:
    ICON_ROCKET = '[^]'
    ICON_SEARCH = '[?]'
    ICON_DOWNLOAD = '[v]'
    ICON_UPLOAD = '[^]'
    ICON_REFRESH = '[R]'
else:
    ICON_ROCKET = '🚀'
    ICON_SEARCH = '🔍'
    ICON_DOWNLOAD = '⬇️'
    ICON_UPLOAD = '⬆️'
    ICON_REFRESH = '🔄'

# Symbol Icons
if PLATFORM_IS_WINDOWS:
    ICON_ARROW_RIGHT = '->'
    ICON_ARROW_DOWN = 'v'
    ICON_BULLET = '*'
    ICON_CHECKMARK = '[OK]'
    ICON_CROSS = '[X]'
else:
    ICON_ARROW_RIGHT = '→'
    ICON_ARROW_DOWN = '↓'
    ICON_BULLET = '•'
    ICON_CHECKMARK = '✓'
    ICON_CROSS = '✗'

# Object Icons
if PLATFORM_IS_WINDOWS:
    ICON_FILE = '[F]'
    ICON_FOLDER = '[D]'
    ICON_PACKAGE = '[P]'
    ICON_GEAR = '[*]'
    ICON_LOCK = '[#]'
else:
    ICON_FILE = '📄'
    ICON_FOLDER = '📁'
    ICON_PACKAGE = '📦'
    ICON_GEAR = '⚙️'
    ICON_LOCK = '🔒'

# Progress Icons
if PLATFORM_IS_WINDOWS:
    ICON_HOURGLASS = '[:]'
    ICON_SPINNER = '[o]'
    ICON_CLOCK = '[T]'
    ICON_CALENDAR = '[C]'
    ICON_BELL = '[B]'
else:
    ICON_HOURGLASS = '⏳'
    ICON_SPINNER = '⌛'
    ICON_CLOCK = '🕐'
    ICON_CALENDAR = '📅'
    ICON_BELL = '🔔'

# Miscellaneous Icons
if PLATFORM_IS_WINDOWS:
    ICON_STAR = '[*]'
    ICON_HEART = '[<3]'
    ICON_FIRE = '[~]'
    ICON_LIGHTNING = '[!]'
    ICON_GLOBE = '[@]'
    ICON_TRASH = '[T]'
    ICON_LIGHTBULB = '[i]'
    ICON_ITERATION = '[R]'
else:
    ICON_STAR = '⭐'
    ICON_HEART = '❤️'
    ICON_FIRE = '🔥'
    ICON_LIGHTNING = '⚡'
    ICON_GLOBE = '🌐'
    ICON_TRASH = '🧹'
    ICON_LIGHTBULB = '💡'
    ICON_ITERATION = '🔄'

# Icon mapping dictionary for function API
ICON_MAP = {
    'success': ICON_SUCCESS,
    'error': ICON_ERROR,
    'warning': ICON_WARNING,
    'info': ICON_INFO,
    'question': ICON_QUESTION,
    'rocket': ICON_ROCKET,
    'search': ICON_SEARCH,
    'download': ICON_DOWNLOAD,
    'upload': ICON_UPLOAD,
    'refresh': ICON_REFRESH,
    'arrow_right': ICON_ARROW_RIGHT,
    'arrow_down': ICON_ARROW_DOWN,
    'bullet': ICON_BULLET,
    'checkmark': ICON_CHECKMARK,
    'cross': ICON_CROSS,
    'file': ICON_FILE,
    'folder': ICON_FOLDER,
    'package': ICON_PACKAGE,
    'gear': ICON_GEAR,
    'lock': ICON_LOCK,
    'hourglass': ICON_HOURGLASS,
    'spinner': ICON_SPINNER,
    'clock': ICON_CLOCK,
    'calendar': ICON_CALENDAR,
    'bell': ICON_BELL,
    'star': ICON_STAR,
    'heart': ICON_HEART,
    'fire': ICON_FIRE,
    'lightning': ICON_LIGHTNING,
    'globe': ICON_GLOBE,
    'trash': ICON_TRASH,
    'lightbulb': ICON_LIGHTBULB,
    'iteration': ICON_ITERATION,
}


def get_icon(name: str, default: str = '?') -> str:
    """
    Get icon by name with case-insensitive lookup.

    Args:
        name: Icon name (e.g., 'success', 'error', 'ROCKET')
              Optionally with 'icon_' prefix (e.g., 'icon_success')
        default: Default value if icon not found (default: '?')

    Returns:
        Icon string appropriate for current platform

    Examples:
        >>> get_icon('success')  # Returns ✅ on Unix, [OK] on Windows
        >>> get_icon('ERROR')    # Case-insensitive
        >>> get_icon('icon_rocket')  # Strips 'icon_' prefix
        >>> get_icon('unknown', default='X')  # Returns 'X'
    """
    # Normalize: lowercase and strip 'icon_' prefix
    normalized = name.lower().strip()
    if normalized.startswith('icon_'):
        normalized = normalized[5:]  # Remove 'icon_' prefix

    return ICON_MAP.get(normalized, default)
