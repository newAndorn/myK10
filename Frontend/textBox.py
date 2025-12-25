class TextBox:
    """
    A widget class for displaying centered text with background and border.
    """
    
    def __init__(self, screen, x, y, width, height, text="", 
                 font_size=24, text_color=0xFFFFFF, 
                 bg_color=0x827E7C, border_color=0x071A3D, 
                 border_width=1):
        """
        Initialize TextBox widget.
        
        Args:
            screen: Screen object with draw methods
            x, y: Position coordinates
            width, height: Dimensions of the box
            text: Text to display
            font_size: Font size for text
            text_color: Color of the text (hex)
            bg_color: Background color (hex)
            border_color: Border color (hex)
            border_width: Width of border in pixels
        """
        self.screen = screen
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.font_size = font_size
        self.text_color = text_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
    
    def draw(self):
        """Draw the text box with centered text."""
        # Draw background rectangle
        self.screen.draw_rect(
            self.x, self.y, self.width, self.height,
            bcolor=self.bg_color, fcolor=self.border_color
        )
        
        # Calculate text position for centering
        text_x, text_y = self._calculate_text_position()
                
        # Draw the text
        self.screen.draw_text(
            text=self.text,
            x=text_x,
            y=text_y,
            font_size=self.font_size,
            color=self.text_color
        )
    
    def _calculate_text_position(self):
        """
        Calculate x, y position to center text in the box.
        This is an approximation - actual text dimensions depend on font metrics.
        """
        # Approximate character width and height based on font size
        char_width = self.font_size * 0.35  # Rough approximation
        char_height = self.font_size
                        
        # Calculate text width (approximate)
        text_width = len(self.text) * char_width
        
        # Center horizontally
        text_x = self.x + (self.width - text_width) // 2
        
        # Center vertically
        text_y = self.y + (self.height - char_height) // 2 + char_height * 0.1
        
        return int(text_x), int(text_y)
    
    def set_text(self, text):
        """Update the text content."""
        self.text = text
    
    def update_text(self, text):
        """Alias for set_text for convenience."""
        self.set_text(text)
    
    def set_colors(self, text_color=None, bg_color=None, border_color=None):
        """Update colors."""
        if text_color is not None:
            self.text_color = text_color
        if bg_color is not None:
            self.bg_color = bg_color
        if border_color is not None:
            self.border_color = border_color
    
    def set_position(self, x, y):
        """Update position."""
        self.x = x
        self.y = y
    
    def set_size(self, width, height):
        """Update dimensions."""
        self.width = width
        self.height = height


# Example usage:
def example_usage():
    """
    Example showing how to use the TextBox widget.
    Replace 'screen' with your actual screen object.
    """
    # Create a text box widget
    textbox = TextBox(
        screen=screen,  # Your screen object
        x=0, y=40, width=130, height=30,
        text="Hum: 45 %",
        font_size=24,
        text_color=0xFFFFFF,
        bg_color=0x827E7C,
        border_color=0x071A3D
    )
    
    # Draw the widget
    textbox.draw()
    
    # Update and redraw
    textbox.set_text("Hum: 50 %")
    textbox.draw()
    
    # Show the result
    screen.show_draw()


# Alternative TextBox with better text centering
class ImprovedTextBox(TextBox):
    """
    Improved TextBox with better text centering using font metrics.
    """
    
    def _calculate_text_position(self):
        """
        Better text centering calculation.
        This version tries to account for font metrics more accurately.
        """
        # More accurate character dimensions
        char_width = self.font_size * 0.55  # Slightly narrower
        char_height = self.font_size * 0.8  # Accounts for font baseline
        
        # Calculate text dimensions
        text_width = len(self.text) * char_width
        text_height = char_height
        
        # Center horizontally
        text_x = self.x + (self.width - text_width) // 2
        
        # Center vertically (account for font baseline)
        text_y = self.y + (self.height - text_height) // 2 + text_height
        
        # Ensure text doesn't go outside bounds
        text_x = max(self.x + 2, min(text_x, self.x + self.width - text_width - 2))
        text_y = max(self.y + self.font_size, min(text_y, self.y + self.height - 2))
        
        return int(text_x), int(text_y)
