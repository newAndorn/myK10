#!/usr/bin/env python3
"""
Example usage of the gauge, ampere arc, and loading animation functionality in the Screen class.

This demonstrates how to create and use LVGL gauges with the K10 Micropython library.
The gauges now display the current value as text inside the bar.

Includes an ampere arc widget centered at 0A with red for negative values (left) and green for positive values (right).

Also includes a Fallout-inspired loading animation with a spinning wheel and text.
"""

# Example usage (this would be in your main script):

def example_gauge_usage():
    """
    Example of how to use the gauge functionality with value text display
    """
    # Initialize screen (assuming you have this setup)
    screen = Screen()
    screen.init()

    # Create a gauge at position (20, 50) with size 200x20, range 0-100
    # The gauge will display custom text inside the bar
    my_gauge = screen.create_gauge(x=20, y=50, width=200, height=20, min_val=0, max_val=100)

    # Set the gauge to 75% with custom text (shows "HIGH" instead of "75")
    screen.set_gauge_value(my_gauge, 75, text="HIGH")

    # Create another gauge with different range (temperature: 0-50°C)
    temp_gauge = screen.create_gauge(x=20, y=100, width=200, height=20, min_val=0, max_val=50)

    # Set temperature to 32°C with custom status text
    screen.set_gauge_value(temp_gauge, 32, text="OK")

    # Update with different text based on value
    screen.set_gauge_value(my_gauge, 90, text="MAX")  # Shows "MAX" instead of "90"

    # You can still show the numerical value by not providing text
    screen.set_gauge_value(temp_gauge, 45, text="")  # Shows "45"

    # Show the updated display
    screen.show_draw()

def animated_gauge_demo():
    """
    Demo showing animated gauge changes with custom text display (bigger font)
    """
    import time

    screen = Screen()
    screen.init()

    # Create a large gauge for demo - now with bigger, more visible text
    demo_gauge = screen.create_gauge(x=10, y=60, width=300, height=40, min_val=0, max_val=100)
    screen.show_draw()

    # Animate from 0 to 100 with status text in BIG FONT
    status_levels = [
        (0, "EMPTY"), (10, "LOW"), (30, "OK"), (60, "GOOD"),
        (80, "HIGH"), (95, "FULL"), (100, "MAX")
    ]

    for value, text in status_levels:
        screen.set_gauge_value(demo_gauge, value, text=text, animated=False)
        screen.show_draw()
        time.sleep(0.5)

    # Animate back down showing numerical values in BIG FONT
    for value in range(100, -1, -5):
        screen.set_gauge_value(demo_gauge, value, text="", animated=False)  # Show numbers
        screen.show_draw()
        time.sleep(0.1)

def version_info_demo():
    """
    Demo showing how to print LVGL version information
    """
    screen = Screen()
    screen.init()

    # Print LVGL version information
    version = screen.print_lvgl_version()
    print(f"Version function returned: {version}")

    # You can also access version components directly if needed
    try:
        major = lv.version_major()
        minor = lv.version_minor()
        patch = lv.version_patch()
        print(f"LVGL Version Components: {major}.{minor}.{patch}")
    except Exception as e:
        print(f"Error accessing version components: {e}")

def loading_animation_demo():
    """
    Demo showing the Fallout-inspired loading animation
    """
    import time

    screen = Screen()
    screen.init()

    print("Showing loading animation for 5 seconds...")

    # Show the loading animation (inspired by Fallout's vault dweller waiting)
    loading_anim = screen.show_loading_animation(x=100, y=100, text="WORKING", color=0xFFFF00)

    # Simulate some work
    time.sleep(5)

    # Hide the animation
    screen.hide_loading_animation(loading_anim)

    print("Loading animation hidden.")

def ampere_arc_demo():
    """
    Demo showing the ampere arc with positive and negative values
    """
    import time

    screen = Screen()
    screen.init()

    print("Creating ampere arc centered at 0A...")

    # Create an ampere arc centered at 0A with range -10A to +10A
    ampere_arc = screen.create_ampere_arc(x=120, y=120, radius=80, min_val=-10, max_val=10)

    print("Demonstrating different ampere values...")

    # Test positive values (green)
    positive_values = [0, 1.5, 3.2, 5.8, 8.1, 10]
    for value in positive_values:
        screen.set_ampere_arc_value(ampere_arc, value, animated=True)
        print(f"Set to {value}A (green)")
        time.sleep(1)

    # Test negative values (red)
    negative_values = [-1.2, -3.7, -6.4, -8.9, -10]
    for value in negative_values:
        screen.set_ampere_arc_value(ampere_arc, value, animated=True)
        print(f"Set to {value}A (red)")
        time.sleep(1)

    # Back to zero
    screen.set_ampere_arc_value(ampere_arc, 0, animated=True)
    print("Back to 0A")

    print("Ampere arc demo complete. Arc remains visible.")

if __name__ == "__main__":
    print("Gauge Example with Value Text Display")
    print("====================================")
    print()
    print("The Screen class now includes:")
    print("1. create_gauge(x, y, width, height, min_val, max_val) - Creates a gauge widget")
    print("   - Returns a dictionary with 'gauge', 'label', 'min_val', 'max_val'")
    print("   - Displays custom text that follows the gauge fill level")
    print("2. set_gauge_value(gauge_dict, value, text, animated) - Sets the gauge's current value")
    print("   - 'text' parameter controls what text is displayed (optional)")
    print("   - If text is empty, displays the numerical value")
    print("   - Automatically updates both the gauge bar and the text label position")
    print("3. create_ampere_arc(x, y, radius, min_val, max_val) - Creates ampere measurement arc")
    print("   - Center at 0A, negative values (red) left, positive values (green) right")
    print("   - Returns dictionary with 'arc', 'label', 'min_val', 'max_val'")
    print("4. set_ampere_arc_value(arc_dict, value, animated) - Sets ampere arc value")
    print("   - Updates arc position and color based on value sign")
    print("5. show_loading_animation(x, y, size, text, color) - Shows Fallout-inspired loading animation")
    print("   - Displays a spinning wheel with customizable text")
    print("   - Returns dictionary with 'spinner' and 'label' for later removal")
    print("6. hide_loading_animation(animation_dict) - Removes the loading animation")
    print()
    print("Features:")
    print("- Label text dynamically repositions based on gauge fill level")
    print("- Display custom text instead of numerical values")
    print("- Uses bigger font (font_big.bin) for better visibility")
    print("- Text stays within gauge bounds and is always visible")
    print("- Smooth animations when changing values")
    print("- White text on dark background for good contrast")
    print("- Ampere arc widget with center-zero design and color-coded values")
    print("- Fallout-inspired loading animation with spinning wheel")
    print()
    print("Example code:")
    print("my_gauge = screen.create_gauge(x=20, y=50, width=200, height=20, min_val=0, max_val=100)")
    print("screen.set_gauge_value(my_gauge, 75, text='HIGH')  # Shows 'HIGH' positioned along the bar")
    print("screen.set_gauge_value(my_gauge, 90)  # Shows '90' (default numerical display)")
    print()
    print("Loading Animation:")
    print("loading_anim = screen.show_loading_animation(x=100, y=100, text='WORKING')")
    print("screen.hide_loading_animation(loading_anim)  # Remove when done")
    print("loading_animation_demo()      # Demo of loading animation")
    print()
    print("Ampere Arc:")
    print("ampere_arc = screen.create_ampere_arc(x=120, y=120, radius=80, min_val=-10, max_val=10)")
    print("screen.set_ampere_arc_value(ampere_arc, 3.5)  # Shows 3.5A in green")
    print("screen.set_ampere_arc_value(ampere_arc, -2.1)  # Shows -2.1A in red")
    print("ampere_arc_demo()             # Demo of ampere arc")
    print()
    print("Version info:")
    print("screen.print_lvgl_version()  # Prints LVGL version information")
    print("version_info_demo()          # Demo of version functions")
