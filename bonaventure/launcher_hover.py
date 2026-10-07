"""Debounce hover activation and allow time to move into the launcher."""


class HoverIntent:
    def __init__(self, open_delay=0.2, close_delay=0.5):
        self.open_delay, self.close_delay = open_delay, close_delay
        self.entered_at = self.left_at = None

    def update(self, now, *, hotspot, inside, visible, pinned=False, processing=False):
        if not visible:
            self.left_at = None
            if not hotspot:
                self.entered_at = None
            elif self.entered_at is None:
                self.entered_at = now
            elif now - self.entered_at >= self.open_delay:
                self.entered_at = None
                return "open"
        else:
            self.entered_at = None
            if hotspot or inside or pinned or processing:
                self.left_at = None
            elif self.left_at is None:
                self.left_at = now
            elif now - self.left_at >= self.close_delay:
                self.left_at = None
                return "close"
        return None
