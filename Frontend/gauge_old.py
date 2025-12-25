from unihiker_k10 import screen

def fill_rect(x, y, w, h, color):
    # Draw h horizontal lines to emulate a filled rectangle
    y2 = y + h
    for yy in range(y, y2):
        screen.draw_line(x0=x, y0=yy, x1=x + w - 1, y1=yy, color=color)

class VerticalGauge:
    def __init__(self, x, y, width=40, height=160, label="Gauge", min_value=-200, max_value=200):
        self.x = x
        self.y = y
        self.w = width
        self.h = height
        self.label = label
        self.min_value = min_value
        self.max_value = max_value
        self.value = 0
        self.value_raw = 0

    def set_value(self, v):
        self.value_raw = v
        
        if v < self.min_value:
            v = self.min_value
        if v > self.max_value:
            v = self.max_value
        self.value = v
        
    def draw(self):
        # Background and frame
        screen.draw_rect(x=self.x, y=self.y, w=self.w, h=self.h, fcolor=0x071A3D, bcolor=0x827E7C)
        
        # Zero line (center)
        mid_y = self.y + self.h // 2

        # Map value (-100..100) to -1..1
        span = float(self.max_value - self.min_value)
        if span <= 0:
            return
        # Normalize around 0 with symmetric range
        max_abs = max(abs(self.min_value), abs(self.max_value))
        n = self.value / max_abs  # -1..1

        if n > 0:
            bar_h = int((self.h // 2) * n)
            if bar_h > 0:
                fill_rect(
                    x=self.x + 10,
                    y=mid_y - bar_h,
                    w=self.w - 20,
                    h=bar_h,
                    color=0xCC2244
                )
        elif n < 0:
            bar_h = int((self.h // 2) * (-n))
            if bar_h > 0:
                fill_rect(
                    x=self.x + 10,
                    y=mid_y,
                    w=self.w - 20,
                    h=bar_h,
                    color=0x00CC44
                )

        # center Text horizontaly
        char_width = 14 * 0.5  # Rough approximation
                        
        text = "{} W".format(int(self.value_raw))

        # Calculate text width (approximate)
        text_width = len(text) * char_width
        
        # Center horizontally
        text_x = self.x + (self.w - text_width) // 2
        
        screen.draw_text(
            text=text,
            x= int(text_x),
            y=self.y + 3,
            font_size=14,
            color=0xFFFFFF
        )