from unihiker_k10 import screen

class VerticalGauge:
    def __init__(self, x, y, width=40, height=160, label="Gauge", min_value=-100, max_value=100):
        self.x = x
        self.y = y
        self.w = width
        self.h = height
        self.label = label
        self.min_value = min_value
        self.max_value = max_value
        self.value = 0

    def set_value(self, v):
        if v < self.min_value:
            v = self.min_value
        if v > self.max_value:
            v = self.max_value
        self.value = v

    def draw(self):
        # Frame: dark grey rectangle outline, no filled background
        frame_color = 0x303030
        screen.draw_rect(x=self.x, y=self.y, w=self.w, h=self.h, color=frame_color)
        screen.draw_rect(x=self.x + 1, y=self.y + 1, w=self.w - 2, h=self.h - 2, color=frame_color)

        # Zero line (center)
        mid_y = self.y + self.h // 2
        screen.fill_rect(x=self.x + 4, y=mid_y, w=self.w - 8, h=1, color=0x888888)

        # Map value (-100..100) to -1..1
        span = float(self.max_value - self.min_value)
        if span <= 0:
            return
        # Normalize around 0 with symmetric range
        max_abs = max(abs(self.min_value), abs(self.max_value))
        n = self.value / max_abs  # -1..1

        # Draw bar: positive (green) up, negative (red) down
        padding = 6
        if n > 0:
            bar_h = int((self.h // 2) * n)
            if bar_h > 0:
                screen.fill_rect(
                    x=self.x + padding,
                    y=mid_y - bar_h,
                    w=self.w - 2 * padding,
                    h=bar_h,
                    color=0x00CC44
                )
        elif n < 0:
            bar_h = int((self.h // 2) * (-n))
            if bar_h > 0:
                screen.fill_rect(
                    x=self.x + padding,
                    y=mid_y,
                    w=self.w - 2 * padding,
                    h=bar_h,
                    color=0xCC2244
                )

        # Value above gauge, centered if supported; fallback to left-aligned
        value_text = "{}%".format(int(self.value))
        value_y = self.y - 24
        drawn = False
        try:
            screen.draw_text(text=value_text, x=self.x + self.w // 2, y=value_y, font_size=18, color=0xCCCCCC, align='center')
            drawn = True
        except Exception:
            pass
        if not drawn:
            try:
                screen.draw_text(text=value_text, x=self.x + self.w // 2, y=value_y, font_size=18, color=0xCCCCCC, anchor='center')
                drawn = True
            except Exception:
                pass
        if not drawn:
            screen.draw_text(text=value_text, x=self.x, y=value_y, font_size=18, color=0xCCCCCC)

        # Label below gauge (try centered)
        label_y = self.y + self.h + 4
        drawn = False
        try:
            screen.draw_text(text=self.label, x=self.x + self.w // 2, y=label_y, font_size=18, color=0xFFFFFF, align='center')
            drawn = True
        except Exception:
            pass
        if not drawn:
            try:
                screen.draw_text(text=self.label, x=self.x + self.w // 2, y=label_y, font_size=18, color=0xFFFFFF, anchor='center')
                drawn = True
            except Exception:
                pass
        if not drawn:
            screen.draw_text(text=self.label, x=self.x, y=label_y, font_size=18, color=0xFFFFFF)