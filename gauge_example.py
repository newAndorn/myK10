#!/usr/bin/env python3
"""
Example usage of the gauge functionality in the Screen class.

This demonstrates how to create and use LVGL gauges with the K10 Micropython library.
The gauges now display the current value as text inside the bar.
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
    Demo showing animated gauge changes with custom text display
    """
    import time

    screen = Screen()
    screen.init()

    # Create a large gauge for demo
    demo_gauge = screen.create_gauge(x=10, y=60, width=300, height=30, min_val=0, max_val=100)
    screen.show_draw()

    # Animate from 0 to 100 with status text
    status_levels = [
        (0, "EMPTY"), (10, "LOW"), (30, "OK"), (60, "GOOD"),
        (80, "HIGH"), (95, "FULL"), (100, "MAX")
    ]

    for value, text in status_levels:
        screen.set_gauge_value(demo_gauge, value, text=text, animated=False)
        screen.show_draw()
        time.sleep(0.5)

    # Animate back down showing numerical values
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
    print()
    print("Features:")
    print("- Label text dynamically repositions based on gauge fill level")
    print("- Display custom text instead of numerical values")
    print("- Text stays within gauge bounds and is always visible")
    print("- Smooth animations when changing values")
    print("- White text on dark background for good contrast")
    print()
    print("Example code:")
    print("my_gauge = screen.create_gauge(x=20, y=50, width=200, height=20, min_val=0, max_val=100)")
    print("screen.set_gauge_value(my_gauge, 75, text='HIGH')  # Shows 'HIGH' positioned along the bar")
    print("screen.set_gauge_value(my_gauge, 90)  # Shows '90' (default numerical display)")
    print()
    print("Version info:")
    print("screen.print_lvgl_version()  # Prints LVGL version information")
    print("version_info_demo()          # Demo of version functions")
