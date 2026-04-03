import sys
import logging

logger = logging.getLogger(__name__)

def get_active_window_title():
    """Returns the title of the active window. Windows only implementation for now."""
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # Get handle to active window
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            
            # Get length of title
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            
            # Create buffer and get title
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            
            title = buff.value
            
            # Clean up browser suffixes to return only the tab title
            browser_suffixes = [
                " - Google Chrome",
                " - Mozilla Firefox",
                " - Microsoft Edge",
                " - Brave",
                " - Vivaldi",
                " - Opera",
                " - Internet Explorer"
            ]
            
            for suffix in browser_suffixes:
                if title.endswith(suffix):
                    title = title[:-len(suffix)]
                    break
            
            return title
        except Exception as e:
            logger.error(f"Failed to get window title: {e}")
            return ""
    else:
        # TODO: Linux/macOS implementations
        return ""
