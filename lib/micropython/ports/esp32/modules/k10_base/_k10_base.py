import gc
import sys
import lvgl as lv
import lcd_bus
import ili9341
from machine import I2S,SPI,Timer,SDCard,I2C
import machine
from mpython import MPythonPin,PinMode,Pin, AHT20, Accelerometer,Light,Scan_Rfid_Edu,wifi,Button,button_a,button_b,i2c
from umqtt.robust import MQTTClient as MQTT
import ubinascii
import fs_driver, math

import time
import vfs

import camera
import _thread
gc.collect()

'''
50以上的使用的是扩展IO芯片
P0  = 1
P1  = 2
P2  = P07 = 57f
P3  = P16 = 66
P4  = P15 = 65
P5  = P14 = 64
P6  = P13 = 63
P7  = NC = -1
P8  = P10 = 60
P9  = P11 = 61
P10 = P12 = 62
P11 = P02 = 52
P12 = P03 = 53
P13 = P04 = 54
P14 = P05 = 55
P15 = P06 = 56
P16 = NC = -1
P17 = NC = -1
P18 = NC = -1
P19 = 48
P20 = 47
'''
pins_k10 = (1, 2, 57, 66, 65, 64, 63, -1, 60, 61, 62, 52, 53, 54, 55, 56, -1, -1, -1, 48, 47)
pins_state = [None] * len(pins_k10)
k10_i2c = I2C(0, scl=48, sda=47, freq=100000) 
'''
输入输出引脚控制 pin类
MPythonPin,PinMode,Pin
'''
class pin():
    def __init__(self, pin):
        self.pin_num = pin
        self.mode = PinMode.IN
        self.pull = None
        self._event_change = None
        self._event_rising = None
        self._event_falling = None
        self._pin = MPythonPin(self.pin_num, PinMode.IN)
        self._iqr_func = None

    def read_digital(self):
        # if(pins_state[self.pin_num]!=PinMode.IN):
        pins_state[self.pin_num]=PinMode.IN
        self._pin = MPythonPin(self.pin_num, PinMode.IN)
        return self._pin.read_digital()
        # else:
        #     return self._pin.read_digital()

    def write_digital(self, value):
        # if(pins_state[self.pin_num]!=PinMode.OUT):
        pins_state[self.pin_num]=PinMode.OUT
        self._pin = MPythonPin(self.pin_num, PinMode.OUT, Pin.PULL_UP)
        return self._pin.write_digital(value)
        # else:
        #     return self._pin.write_digital(value)

    def read_analog(self):
        if self.pin_num not in [0, 1, 2, 3, 4, 10]:
            tmp = self.read_digital()
            if(tmp==0):
                return 0
            elif(tmp==1):
                return 4095
            else:
                return None
        pins_state[self.pin_num]=PinMode.ANALOG
        self._pin = MPythonPin(self.pin_num, PinMode.ANALOG)
        return self._pin.read_analog()
        
    def write_analog(self, value=0, freq=5000):
        # if(pins_state[self.pin_num]!=PinMode.PWM):
        pins_state[self.pin_num]=PinMode.PWM
        self._pin = MPythonPin(self.pin_num, PinMode.PWM)
        return self._pin.write_analog(duty=value, freq=freq)
        # else:
        #     return self._pin.write_analog(duty=value, freq=freq)

    def irq(self, handler=None, trigger=Pin.IRQ_RISING):
        # if(pins_state[self.pin_num]!=PinMode.IN):
        pins_state[self.pin_num]=PinMode.IN
        self._pin = MPythonPin(self.pin_num, PinMode.IN)
        self._pin.irq(trigger=trigger, handler=handler)
        # else:
        #     self._pin.irq(trigger=trigger, handler=handler)
    
    @property
    def event_change(self):
        return self._event_change

    @event_change.setter
    def event_change(self, new_event_change):
        if new_event_change != self._event_change:
            self._event_change = new_event_change
            self._iqr_func = self._event_change
            self.irq(handler=self.func, trigger=Pin.IRQ_RISING|Pin.IRQ_FALLING)

    @property
    def event_rising(self):
        return self._event_rising

    @event_rising.setter
    def event_rising(self, new_event_rising):
        if new_event_rising != self._event_rising:
            self._event_rising = new_event_rising
            self._iqr_func = self._event_rising
            self.irq(handler=self.func, trigger=Pin.IRQ_RISING)

    @property
    def event_falling(self):
        return self._event_falling

    @event_falling.setter
    def event_falling(self, new_event_falling):
        if new_event_falling != self._event_falling:
            self._event_falling = new_event_falling
            self._iqr_func = self._event_falling
            self.irq(handler=self.func, trigger=Pin.IRQ_FALLING)
    
    def func(self,_):
        self._iqr_func()

class button:
    a = 'a'
    b = 'b'
    def __init__(self,_type='a'): 
        self.button_a = button_a
        self.button_b = button_b
        self.type = _type
        self.func_event_change = None
        self.func_event_released = None
        if(self.type not in ['a','b']):
            self.pin = pins_k10[self.type]
            self.button = Button(self.pin)

    def func(self,_):
        self.func_event_change()

    def func_released(self,_):
        self.func_event_released()

    @property
    def event_pressed(self):
        return self.func_event_change

    @event_pressed.setter
    def event_pressed(self, new_event_change):
        if new_event_change != self.func_event_change:
            self.func_event_change = new_event_change
            if(self.type=='a'):
                self.button_a.event_pressed = self.func
            elif(self.type=='b'):
                self.button_b.event_pressed = self.func
            else:
                # print('Not supported')
                self.button.event_pressed = self.func
    @property
    def event_released(self):
        return self.func_event_released

    @event_released.setter
    def event_released(self, new_event_released):
        if new_event_released != self.func_event_released:
            self.func_event_released = new_event_released
            if(self.type=='a'):
                self.button_a.event_released = self.func_released
            elif(self.type=='b'):
                self.button_b.event_released = self.func_released
            else:
                # print('Not supported')
                self.button.event_released = self.func_released

    def status(self):
        if(self.type=='a'):
            return self.button_a.status()
        elif(self.type=='b'):
            return self.button_b.status()
        else:
            return self.button.status()    

class aht20(object):
    def __init__(self):
        self.aht20 = AHT20()
        #self.tim = Timer(16)
        #self.tim.init(period=1000, mode=Timer.PERIODIC, callback=self.timer_tick)
        time.sleep(1.5)
        self.aht20.measure()
        pass

    def timer_tick(self,_):
        try: 
            self.aht20.measure()
        except: 
            pass
    def measure(self):
        try: 
            self.aht20.measure()
        except: 
            pass

    def read(self):
        return self.aht20.temperature(), self.aht20.humidity()
    
    def read_temp(self):
        return self.aht20.temperature()
    
    def read_temp_f(self):
        celsius = self.read_temp()
        fahrenheit = celsius * 9 / 5 + 32
        return round(fahrenheit,2)
    
    def read_humi(self):
        return self.aht20.humidity()

class Screen(object):
    def __init__(self,dir=2):
        self.spi_bus = SPI.Bus(host=2,mosi=21,miso=-1,sck=12)
        self.display_bus = lcd_bus.SPIBus(spi_bus = self.spi_bus, dc = 13, cs = 14, freq = 40000000)
        '''
        self.display = ili9341.ILI9341(data_bus = self.display_bus, display_width = 240, display_height = 320,
                                       reset_state = ili9341.STATE_LOW, color_byte_order = ili9341.BYTE_ORDER_BGR,
                                       color_space = lv.COLOR_FORMAT.RGB565, rgb565_byte_swap=True)
        '''
        self.display = ili9341.ILI9341(data_bus = self.display_bus, display_width = 240, display_height = 320,
                                       reset_state = ili9341.STATE_LOW, color_byte_order = ili9341.BYTE_ORDER_BGR,
                                       color_space = lv.COLOR_FORMAT.RGB565, rgb565_byte_swap=True)
        self.linewidth = 1
        self.fs_drv = lv.fs_drv_t()
        fs_driver.fs_register(self.fs_drv, 'S')
        #self.myfont_cn = lv.binfont_create("S:./font_big.bin")
        self.myfont_cn = lv.binfont_create("S:./roboto.bin")
        print(f"binfont_create successful: {self.myfont_cn is not None}")
        
    #初始化屏幕，设置方向为(0~3)
    def init(self,dir=2):
        #用来打开屏幕背光
        myi2c = I2C(0, scl=Pin(48), sda=Pin(47), freq=100000)
        temp = myi2c.readfrom_mem(0x20, 0x02, 1)
        myi2c.writeto(0x20,bytearray([0x02, (temp[0] | 0x01)]))
        temp = myi2c.readfrom_mem(0x20, 0x06, 1)
        myi2c.writeto(0x20,bytearray([0x06, (temp[0] & 0xFE)]))

        self.display.set_power(True)
        self.display.init(1)
        if dir == 0:
            self.display.set_rotation(lv.DISPLAY_ROTATION._0)
        elif dir == 1:
            self.display.set_rotation(lv.DISPLAY_ROTATION._90)
        elif dir == 2:
            self.display.set_rotation(lv.DISPLAY_ROTATION._180)
        elif dir == 3:
            self.display.set_rotation(lv.DISPLAY_ROTATION._270)
        else:
            self.display.set_rotation(lv.DISPLAY_ROTATION._180)

        #self.screen = lv.obj()
        self.screen = lv.screen_active()
        self.img = lv.image(self.screen)
        self.canvas = lv.canvas(self.screen)
        self.screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.img.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.canvas.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)


        self.canvas.set_size(240,320)
        self.canvas.align(lv.ALIGN.CENTER, 0, 0)
        self.canvas_buf = bytearray(240*320*4)
        self.canvas.set_buffer(self.canvas_buf, 240, 320, lv.COLOR_FORMAT.ARGB8888)
        self.canvas.fill_bg(lv.color_white(), lv.OPA.TRANSP)
        self.layer = lv.layer_t()
        self.canvas.init_layer(self.layer)
        self.area = lv.area_t()
        self.clear_rect = lv.draw_rect_dsc_t()
        
        self.img_dsc = lv.image_dsc_t(
            dict(
                header = dict(cf =lv.COLOR_FORMAT.RGB565, w=480, h=320),
                data_size = 480*320*2,
                data = None
            )
        )

    #显示指定颜色背景
    def show_bg(self,color=0xFFFFFF):
        self.screen.set_style_bg_color(lv.color_hex(color),0)

    #将缓存内容显示
    def show_draw(self):
        self.canvas.finish_layer(self.layer)
        self.canvas.invalidate()
        #lv.screen_load(self.screen)

    #清除全屏，颜色为指定颜色
    def clear(self,line=0,font=None,color=None):
        if font == None:
            # Delete user-created LVGL widgets from the screen, but preserve persistent objects
            child_count = self.screen.get_child_count()
            for i in range(child_count - 1, -1, -1):  # Delete in reverse order
                child = self.screen.get_child(i)
                # Don't delete persistent objects like canvas and img
                if child != self.canvas and child != self.img:
                    child.delete()

            #清除全屏，颜色为指定颜色
            if color == None:
                self.canvas.fill_bg(lv.color_white(), lv.OPA.TRANSP)
            else:
                self.canvas.fill_bg(lv.color_hex(color), lv.OPA.COVER)
        else:
            #清除第几行文字
            pass
        pass

    #显示文字xxx在第line行,字号font_size,颜色color
    def draw_text(self,text="",line=None, x=0,y=0,font_size=16,color=0x0000FF):
        #self.canvas.finish_layer(self.layer)
        #self.canvas.get_draw_buf().clear(self.area)
        self.desc = lv.draw_label_dsc_t()
        self.desc.init()
        self.desc.color = lv.color_hex(color)
        self.desc.text = text
        self.desc.font = self.myfont_cn
        '''
        if font_size == 16:
            self.desc.font = lv.font_montserrat_16
        elif font_size == 14:
            self.desc.font = lv.font_montserrat_14
        elif font_size == 12:
            self.desc.font = lv.font_montserrat_12
        else:
            font_size = 16'''

        #按坐标显示
        if line == None:
            self.area.x1 = x
            self.area.y1 = y
        #按行显示 
        else:
            self.area.x1 = 0
            self.area.y1 = line * (font_size + 2)
        self.area.set_width(240-self.area.x1)
        self.area.set_height(font_size + 2)

        #self.layer.draw_buf.clear(self.area)
        #self.canvas.fill_bg(lv.color_white(), lv.OPA.TRANSP)
        #self.canvas.get_draw_buf().clear(self.area)  # 强制清除画布缓冲区
        #bytearray(self.canvas.get_buf())[:] = b'\x00' * len(self.canvas_buf)
        self.layer.draw_buf.clear(self.area)  # 清除图层缓冲区
        #self.canvas_buf[:] = b'\x00' * len(self.canvas_buf)
        lv.draw_label(self.layer, self.desc, self.area)
        #self.layer.draw_buf.clear(self.area)

    #画点
    def draw_point(self,x=0,y=0,color=0x0000FF):
        #self.canvas.set_px(x=x, y=y, color = lv.color_hex(color))
        self.draw_line(x0=x,y0=y,x1=(x+self.linewidth),y1=y,color = color)

    #设置线宽/边框宽
    def set_width(self,width=1):
        self.linewidth = width

    #画线
    def draw_line(self,x0=0,y0=0,x1=0,y1=0,color=0x000000):
        self.desc = lv.draw_line_dsc_t()
        self.desc.init()
        self.desc.p1.x = x0
        self.desc.p1.y = y0
        self.desc.p2.x = x1
        self.desc.p2.y = y1
        self.desc.color = lv.color_hex(color)
        self.desc.width = self.linewidth
        self.desc.opa = 255
        self.desc.blend_mode = lv.BLEND_MODE.NORMAL
        self.desc.round_start = 0
        self.desc.round_end = 0
        lv.draw_line(self.layer, self.desc)

    #画圆,圆心(x,y),r半径,边框颜色bcolor,填充颜色fcolor
    def draw_circle(self, x=0,y=0,r=0,bcolor=0x000000,fcolor=None):
        self.desc = lv.draw_rect_dsc_t()
        self.desc.init()
        self.desc.radius = lv.RADIUS_CIRCLE
        if fcolor == None:
            #设置矩形背景透明度为透明色
            self.desc.bg_opa = lv.OPA.TRANSP
        else:
            #设置矩形背景透明度为不透明
            self.desc.bg_opa = lv.OPA.COVER
            #设置矩形背景色
            self.desc.bg_color = lv.color_hex(fcolor)
        #设置矩形边框宽度
        self.desc.border_width = self.linewidth
        #设置矩形边框颜色
        self.desc.border_color = lv.color_hex(bcolor)
        area = lv.area_t()
        area.x1 = x-r
        area.y1 = y-r
        area.set_width(2*r)
        area.set_height(2*r)
        lv.draw_rect(self.layer, self.desc, area)
        pass
    
    #显示矩形顶点(x,y),宽w、高h,边框颜色bcolor,填充颜色fcolor
    def draw_rect(self, x = 0, y = 0, w = 0, h = 0, bcolor = 0x000000, fcolor = None):
        self.desc = lv.draw_rect_dsc_t()
        self.desc.init()
        
        if fcolor == None:
            #设置矩形背景透明度为透明色
            self.desc.bg_opa = lv.OPA.TRANSP
        else:
            #设置矩形背景透明度为不透明
            self.desc.bg_opa = lv.OPA.COVER
            #设置矩形背景色
            self.desc.bg_color = lv.color_hex(fcolor)
        #设置矩形边框宽度
        self.desc.border_width = self.linewidth
        #设置矩形边框颜色
        self.desc.border_color = lv.color_hex(bcolor)
        area = lv.area_t()
        area.x1 = x
        area.y1 = y
        area.set_width(w)
        area.set_height(h)
        lv.draw_rect(self.layer, self.desc, area)
        pass

    def show_loading_animation(self, x=100, y=100, size=50, text="WORKING", color=0xFFFF00):
        """
        Show a Fallout-inspired loading animation with a spinning wheel and text.

        Args:
            x: X position on screen (default: 100)
            y: Y position on screen (default: 100)
            size: Size of the spinner (default: 50)
            text: Text to display below the spinner (default: "WORKING")
            color: Color of the spinner and text (default: yellow)

        Returns:
            Dictionary containing the spinner and label objects for later removal
        """
        # Create a spinner (rotating loading indicator)
        spinner = lv.spinner(self.screen)
        spinner.set_pos(x, y)
        spinner.set_size(size, size)
        spinner.set_anim_params(1000, 0)  # 1000ms rotation time, 0ms delay

        # Set spinner color
        spinner.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)
        spinner.set_style_arc_width(4, lv.PART.INDICATOR)

        # Create a label below the spinner
        label = lv.label(self.screen)
        label.set_text(text)
        label.set_style_text_color(lv.color_hex(color), 0)

        # Try to use the big font if available
        try:
            label.set_style_text_font(self.myfont_cn, 0)
        except Exception as e:
            print(f"Exception setting big font for loading text: {e}")
            # Fallback to larger montserrat font
            try:
                label.set_style_text_font(lv.font_montserrat_16, 0)
            except:
                pass  # Use default font

        # Position the label below the spinner
        label.set_pos(x - 40, y + size + 10)

        return {'spinner': spinner, 'label': label}

    def hide_loading_animation(self, animation_dict):
        """
        Hide and remove the loading animation.

        Args:
            animation_dict: Dictionary returned by show_loading_animation()
        """
        if 'spinner' in animation_dict:
            animation_dict['spinner'].delete()
        if 'label' in animation_dict:
            animation_dict['label'].delete()

    # -------------------------------------------------------------------------
    # Ampere arc widget (LVGL arc-based gauge for current measurement)
    # -------------------------------------------------------------------------

    def get_ampere_color(self, ampere):
        """
        Calculate color based on ampere value for arc display.
        Red for negative values (left side), green for positive values (right side).

        Args:
            ampere: Current in amperes

        Returns:
            Color value in hex format (0xRRGGBB)
        """
        if ampere < 0:
            # Red for negative values (left side)
            return 0xFF0000  # Pure red
        else:
            # Green for positive values (right side)
            return 0x00FF00  # Pure green

    def create_ampere_arc(self, x=60, y=100, radius=80, min_val=-10, max_val=10):
        """
        Create and display an LVGL arc widget for ampere measurement.
        Center at 0A, negative values (red) on left, positive values (green) on right.

        Args:
            x: X position of arc center on screen
            y: Y position of arc center on screen
            radius: Radius of the arc
            min_val: Minimum ampere value (default: -10)
            max_val: Maximum ampere value (default: 10)

        Returns:
            Dictionary containing the arc widget and range values
            {'arc': lv.arc, 'label': lv.label, 'min_val': int, 'max_val': int}
        """
        # Create an arc widget
        arc = lv.arc(self.screen)

        # Set position and size (arc is positioned by its center)
        arc.set_pos(x - radius, y - radius)
        arc.set_size(radius * 2, radius * 2)

        # Set the value range (min and max ampere values)
        arc.set_range(min_val, max_val)

        # Set initial value to 0 (center)
        arc.set_value(0)

        # Configure arc angles for a semicircle (180 degrees)
        # LVGL angles are in degrees, 0° is at 3 o'clock, increasing clockwise
        # For a semicircle centered at bottom, we want 0° to 180°
        arc.set_bg_angles(0, 180)  # Background arc from 0° to 180°

        # Set the arc to show the value range from min to current value
        arc.set_angles(0, 180)  # Initially show full range

        # Create a label to display the current ampere value
        label = lv.label(self.screen)
        label.set_text("0.0 A")
        label.set_style_text_color(lv.color_white(), 0)

        # Use the big font if available
        try:
            label.set_style_text_font(self.myfont_cn, 0)
            font_height = 24
        except Exception as e:
            print(f"Exception setting big font: {e}")
            # Fallback to larger montserrat font
            try:
                label.set_style_text_font(lv.font_montserrat_16, 0)
                font_height = 16
            except:
                font_height = 16  # Default fallback

        # Position label at the center bottom of the arc
        label.set_pos(x - 30, y + radius - font_height - 10)

        return {'arc': arc, 'label': label, 'min_val': min_val, 'max_val': max_val}

    def set_ampere_arc_value(self, arc_dict, value, animated=True):
        """
        Set the current ampere value of an arc and update the display.

        Args:
            arc_dict: The dictionary returned by create_ampere_arc containing 'arc', 'label', 'min_val', 'max_val'
            value: The numerical ampere value to set
            animated: Whether to animate the value change (default: True)
        """
        arc = arc_dict['arc']
        label = arc_dict['label']
        min_val = arc_dict['min_val']
        max_val = arc_dict['max_val']

        # Ensure value is within range
        value = max(min_val, min(max_val, value))

        # Update arc value
        anim_enable = lv.ANIM.ON if animated else lv.ANIM.OFF
        arc.set_value(value)

        # Set arc color based on value (red for negative, green for positive)
        color = self.get_ampere_color(value)
        arc.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)

        # Update label text with formatted ampere value
        if abs(value) < 10:
            label_text = f"{value:.1f} A"
        else:
            label_text = f"{value:.0f} A"
        label.set_text(label_text)

        # Set label color to match arc color
        label.set_style_text_color(lv.color_hex(color), 0)
    
    def create_gauge(self, x=0, y=0, width=200, height=20, min_val=0, max_val=100):
        """
        Create and display an LVGL gauge (bar widget) with value text display.

        Args:
            x: X position on screen
            y: Y position on screen
            width: Width of the gauge
            height: Height of the gauge
            min_val: Minimum value (default: 0)
            max_val: Maximum value (default: 100)

        Returns:
            Dictionary containing the gauge bar, its associated label, and range values
            {'gauge': lv.bar, 'label': lv.label, 'min_val': int, 'max_val': int}
        """
        # Create a bar widget (acts as a gauge in LVGL)
        gauge = lv.bar(self.screen)

        # Set position and size
        gauge.set_pos(x, y)
        gauge.set_size(width, height)

        # Set the range (min and max values)
        gauge.set_range(min_val, max_val)

        # Set initial value to minimum
        gauge.set_value(min_val, lv.ANIM.OFF)

        # Set mode to normal (shows progress from min to current value)
        gauge.set_mode(lv.bar.MODE.NORMAL)

        # Create a label to display the current value with big font
        label = lv.label(self.screen)
        label.set_text(str(min_val))
        label.set_style_text_color(lv.color_white(), 0)

        # Use the big font if available
        try:
            label.set_style_text_font(self.myfont_cn, 0)
            font_height = 24  # Approximate height for big font
            #label.set_style_text_font(lv.font_montserrat_16, 0)
            #font_height = 32  # Approximate height for big font
        except Exception as e:
            print(f"Exception setting big font: {e}")
            # Fallback to larger montserrat font if big font fails
            try:
                label.set_style_text_font(lv.font_montserrat_16, 0)
                font_height = 16
            except:
                font_height = 16  # Default fallback

        print(f"Actual font size: {font_height}")
        # Position label initially at the start of the gauge
        label.set_pos(x + 5, y + (height - font_height) // 2)

        return {'gauge': gauge, 'label': label, 'min_val': min_val, 'max_val': max_val}

    def set_gauge_value(self, gauge_dict, value, text="", animated=True, gauge_type="temperature"):
        """
        Set the current value of a gauge and display custom text.

        Args:
            gauge_dict: The dictionary returned by create_gauge containing 'gauge', 'label', 'min_val', 'max_val'
            value: The numerical value to set for the gauge bar
            text: Custom text to display (if empty, displays the numerical value)
            animated: Whether to animate the value change (default: True)
            gauge_type: Type of gauge - "temperature" or "humidity" (default: "temperature")
        """
        gauge = gauge_dict['gauge']
        label = gauge_dict['label']
        min_val = gauge_dict['min_val']
        max_val = gauge_dict['max_val']

        # Update gauge value
        anim_enable = lv.ANIM.ON if animated else lv.ANIM.OFF
        gauge.set_value(value, anim_enable)

        # Set color for the gauge bar based on gauge type
        if gauge_type == "humidity":
            color_value = self.get_humidity_color(value)
        else:  # default to temperature
            color_value = self.get_temperature_color(value)
        gauge.set_style_bg_color(lv.color_hex(color_value), lv.STATE.DEFAULT)
        gauge.set_style_bg_color(lv.color_hex(color_value), lv.PART.INDICATOR)

        # Update label text (use custom text if provided, otherwise use the numerical value)
        display_text = text if text else str(value)
        label.set_text(display_text)

        # Calculate new label position based on gauge value
        gauge_width = gauge.get_width()
        gauge_x = gauge.get_x()
        gauge_y = gauge.get_y()
        gauge_height = gauge.get_height()

        # Get the font height for proper positioning
        try:
            # Try to get the actual font height from the label's style
            current_font = label.get_style_text_font(0)
            if hasattr(current_font, 'line_height'):
                font_height = current_font.line_height
            else:
                # Fallback based on which font we're likely using
                try:
                    if label.get_style_text_font(0) == self.myfont_cn:
                        font_height = 24  # Big font
                    else:
                        font_height = 16  # Standard font
                except:
                    font_height = 16  # Default fallback
        except:
            font_height = 16  # Safe fallback

        # Calculate position based on value (as percentage of gauge width)
        if max_val > min_val:
            value_ratio = (value - min_val) / (max_val - min_val)
            # Position label at 60% of the filled area to keep it within the filled portion
            label_x = gauge_x + int(gauge_width * value_ratio * 0.6)

            # If the position would put the label too far to the right, adjust it
            # Adjust character width estimate based on font size
            char_width = 12 if font_height > 16 else 8  # Bigger font = wider characters
            label_width = len(display_text) * char_width
            if label_x + label_width > gauge_x + gauge_width - 5:
                label_x = gauge_x + gauge_width - label_width - 5

            # Ensure label doesn't go too far left either
            if label_x < gauge_x + 5:
                label_x = gauge_x + 5
        else:
            label_x = gauge_x + 5

        label_y = gauge_y + (gauge_height - font_height) // 2  # Center vertically
        label.set_pos(label_x, label_y)

    def get_ampere_color(self, ampere):
        """
        Calculate color based on ampere value for arc display.
        Red for negative values (left side), green for positive values (right side).

        Args:
            ampere: Current in amperes

        Returns:
            Color value in hex format (0xRRGGBB)
        """
        if ampere < 0:
            # Red for negative values (left side)
            return 0xFF0000  # Pure red
        else:
            # Green for positive values (right side)
            return 0x00FF00  # Pure green

    def create_ampere_arc(self, x=60, y=100, radius=80, min_val=-10, max_val=10):
        """
        Create and display an LVGL arc widget for ampere measurement.
        Center at 0A, negative values (red) on left, positive values (green) on right.

        Args:
            x: X position of arc center on screen
            y: Y position of arc center on screen
            radius: Radius of the arc
            min_val: Minimum ampere value (default: -10)
            max_val: Maximum ampere value (default: 10)

        Returns:
            Dictionary containing the arc widget and range values
            {'arc': lv.arc, 'label': lv.label, 'min_val': int, 'max_val': int}
        """
        # Create an arc widget
        arc = lv.arc(self.screen)

        # Set position and size (arc is positioned by its center)
        arc.set_pos(x - radius, y - radius)
        arc.set_size(radius * 2, radius * 2)

        # Set the value range (min and max ampere values)
        arc.set_range(min_val, max_val)

        # Set initial value to 0 (center)
        arc.set_value(0)

        # Configure arc angles for a semicircle (180 degrees)
        # LVGL angles are in degrees, 0° is at 3 o'clock, increasing clockwise
        # For a semicircle centered at bottom, we want 0° to 180°
        arc.set_bg_angles(0, 180)  # Background arc from 0° to 180°

        # Set the arc to show the value range from min to current value
        arc.set_angles(0, 180)  # Initially show full range

        # Create a label to display the current ampere value
        label = lv.label(self.screen)
        label.set_text("0.0 A")
        label.set_style_text_color(lv.color_white(), 0)

        # Use the big font if available
        try:
            label.set_style_text_font(self.myfont_cn, 0)
            font_height = 24
        except Exception as e:
            print(f"Exception setting big font: {e}")
            # Fallback to larger montserrat font
            try:
                label.set_style_text_font(lv.font_montserrat_16, 0)
                font_height = 16
            except:
                font_height = 16  # Default fallback

        # Position label at the center bottom of the arc
        label.set_pos(x - 30, y + radius - font_height - 10)

        return {'arc': arc, 'label': label, 'min_val': min_val, 'max_val': max_val}

    def set_ampere_arc_value(self, arc_dict, value, animated=True):
        """
        Set the current ampere value of an arc and update the display.

        Args:
            arc_dict: The dictionary returned by create_ampere_arc containing 'arc', 'label', 'min_val', 'max_val'
            value: The numerical ampere value to set
            animated: Whether to animate the value change (default: True)
        """
        arc = arc_dict['arc']
        label = arc_dict['label']
        min_val = arc_dict['min_val']
        max_val = arc_dict['max_val']

        # Ensure value is within range
        value = max(min_val, min(max_val, value))

        # Update arc value
        anim_enable = lv.ANIM.ON if animated else lv.ANIM.OFF
        arc.set_value(value)

        # Set arc color based on value (red for negative, green for positive)
        color = self.get_ampere_color(value)
        arc.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)

        # Update label text with formatted ampere value
        if abs(value) < 10:
            label_text = f"{value:.1f} A"
        else:
            label_text = f"{value:.0f} A"
        label.set_text(label_text)

        # Set label color to match arc color
        label.set_style_text_color(lv.color_hex(color), 0)

    def print_lvgl_version(self):
        """
        Print the current LVGL version information.

        Returns:
            str: The version string
        """
        try:
            major = lv.version_major()
            minor = lv.version_minor()
            patch = lv.version_patch()
            version_str = f"LVGL Version: {major}.{minor}.{patch}"
            print(version_str)

            # Also print the full version info if available
            try:
                info = lv.version_info()
                print(f"LVGL Info: {info}")
            except:
                pass

            return version_str
        except Exception as e:
            error_msg = f"Error getting LVGL version: {e}"
            print(error_msg)
            return error_msg

    def deinit(self):
        if hasattr(self, 'timer') and self.timer:
            try:
                self.timer.pause()
                self.timer.delete()
            except:
                pass
    
    def get_temperature_color(self, temperature):
        """
        Calculate color based on temperature value.
        Blue for low temperatures (<15°C), green around 20°C, red for high temperatures (>25°C).

        Args:
            temperature: Temperature in Celsius

        Returns:
            Color value in hex format (0xRRGGBB)
        """
        if temperature <= 15:
            # Blue for cold temperatures
            return 0x0000FF
        elif temperature <= 20:
            # Transition from blue to green (15°C to 20°C)
            ratio = (temperature - 15) / 5  # 0 to 1
            blue = int(255 * (1 - ratio))
            green = int(255 * ratio)
            red = 0
        elif temperature <= 25:
            # Transition from green to red (20°C to 25°C)
            ratio = (temperature - 20) / 5  # 0 to 1
            blue = 0
            green = int(255 * (1 - ratio))
            red = int(255 * ratio)
        else:
            # Red for hot temperatures
            return 0xFF0000

        # Convert RGB to hex
        return (red << 16) | (green << 8) | blue

    def get_humidity_color(self, humidity):
        """
        Calculate color based on humidity value.
        Yellow for low humidity (<30%), blue for high humidity (>70%).

        Args:
            humidity: Humidity percentage (0-100)

        Returns:
            Color value in hex format (0xRRGGBB)
        """
        if humidity <= 30:
            # Yellow for low humidity
            return 0xFFFF00
        elif humidity <= 70:
            # Transition from yellow to blue (30% to 70%)
            ratio = (humidity - 30) / 40  # 0 to 1
            red = int(255 * (1 - ratio))
            green = 255  # Keep green constant
            blue = int(255 * ratio)
        else:
            # Blue for high humidity
            return 0x0000FF

        # Convert RGB to hex
        return (red << 16) | (green << 8) | blue

    def show_camera_feed(self, buf, save_filename=None):
        # 将摄像头数据填充到canvas缓冲区
        #self.canvas_buf[:] = buf[:len(self.canvas_buf)]  # 假设buf与canvas分辨率匹配
        #self.show_draw()
        img_dsc = lv.draw_image_dsc_t()
        img_dsc.init()
        img_dsc.src = buf
        area = lv.area_t()
        area.x1 = 0
        area.y1 = 0
        area.set_width(240)
        area.set_height(320)
        lv.draw_image(self.layer,self.desc, area)
        lv.screen_load(self.screen)

        # Save the raw buffer if filename provided
        if save_filename:
            self.save_raw_buffer(buf, save_filename)

    def show_camera_img(self,buf):
        lv.draw_sw_rgb565_swap(buf,240*320*2)
        self.img_dsc.data = buf
        self.img.set_src(self.img_dsc)
        lv.refr_now(None)

    def show_camera(self,camera):
        self.timer =lv.timer_create(lambda t: self.show_camera_img(camera.capture()), 50, None)

    def save_displayed_image(self, filename, width=240, height=320):
        """
        Save the currently displayed camera image as a BMP file.

        Args:
            filename: Path to save the BMP file
            width: Image width in pixels
            height: Image height in pixels
        """
        try:
            # Take a snapshot of the current screen
            draw_buf = lv.snapshot_take(lv.screen_active(), lv.COLOR_FORMAT.RGB565)

            if draw_buf and hasattr(draw_buf, 'data') and draw_buf.data:
                # BMP header for RGB565 format
                # BMP files are stored upside down, so we need to flip the rows
                bmp_header = self._create_bmp_header(width, height, 16)  # 16 bits per pixel for RGB565

                with open(filename, 'wb') as f:
                    f.write(bmp_header)

                    # Get the raw data - for RGB565, each pixel is 2 bytes
                    data = draw_buf.data
                    data_size = len(data) if hasattr(data, '__len__') else draw_buf.data_size

                    print(f"Saving BMP: {width}x{height}, data size: {data_size} bytes")

                    # Write the image data (RGB565 format)
                    if isinstance(data, (bytes, bytearray)):
                        f.write(data)
                    else:
                        # If data is not directly accessible, we need a different approach
                        print("Warning: Could not access raw image data directly")
                        return False

                print(f"BMP image saved to {filename} ({len(bmp_header) + data_size} bytes)")
                return True
            else:
                print("Failed to capture snapshot or no data available")
                return False

        except Exception as e:
            print(f"Error saving BMP image: {e}")
            return False

    def _create_bmp_header(self, width, height, bits_per_pixel):
        """Create a BMP file header for the given dimensions and bit depth."""
        # BMP Header (14 bytes)
        file_size = 14 + 40 + (width * height * bits_per_pixel // 8)
        bmp_header = bytearray([
            0x42, 0x4D,          # BM
            file_size & 0xFF, (file_size >> 8) & 0xFF, (file_size >> 16) & 0xFF, (file_size >> 24) & 0xFF,  # File size
            0x00, 0x00,          # Reserved
            0x00, 0x00,          # Reserved
            0x36, 0x00, 0x00, 0x00  # Data offset (54 bytes for header)
        ])

        # DIB Header (40 bytes)
        dib_header = bytearray([
            0x28, 0x00, 0x00, 0x00,  # Header size
            width & 0xFF, (width >> 8) & 0xFF, (width >> 16) & 0xFF, (width >> 24) & 0xFF,  # Width
            height & 0xFF, (height >> 8) & 0xFF, (height >> 16) & 0xFF, (height >> 24) & 0xFF,  # Height
            0x01, 0x00,          # Planes
            bits_per_pixel & 0xFF, (bits_per_pixel >> 8) & 0xFF,  # Bits per pixel
            0x00, 0x00, 0x00, 0x00,  # Compression (BI_RGB)
            0x00, 0x00, 0x00, 0x00,  # Image size (can be 0 for BI_RGB)
            0x00, 0x00, 0x00, 0x00,  # X pixels per meter
            0x00, 0x00, 0x00, 0x00,  # Y pixels per meter
            0x00, 0x00, 0x00, 0x00,  # Colors used
            0x00, 0x00, 0x00, 0x00   # Important colors
        ])

        return bmp_header + dib_header

    def save_raw_buffer(self, buf, filename):
        """
        Save the raw camera buffer directly to file.

        Args:
            buf: Camera buffer data
            filename: Path to save the file
        """
        try:
            with open(filename, 'wb') as f:
                f.write(buf)
            print(f"Raw buffer saved to {filename} ({len(buf)} bytes)")
            return True
        except Exception as e:
            print(f"Error saving raw buffer: {e}")
            return False


class BMS:
    """
    Xiaoxiang/JBD BMS watcher over BLE (central mode).
    Provides scanning, start, and stop helpers for console logging.
    """

    # Typical BLE UART characteristic UUID used by many Xiaoxiang/JBD BMS modules.
    # Adjust if your module uses a different UUID.
    UART_UUID_STR = "0000ffe1-0000-1000-8000-00805f9b34fb"

    # Basic status request frame used by many Xiaoxiang/JBD BMS (from open-source tools).
    REQUEST_FRAME = b"\xDD\xA5\x03\x00\xFF\xFD\x77"

    def __init__(self, name=None, addr=None, poll_interval=5):
        """
        Create a BMS watcher.

        Args:
            name: BLE device name to match (bytes). Required if addr is not provided.
                  Example: name=b"JBD-BMS-1234"
            addr: BLE address (bytes). If provided, takes precedence over name.
                  Example: addr=bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
            poll_interval: Seconds between request frames (default: 5).
        """
        self.name = name
        self.addr = addr
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None

    @staticmethod
    def scan_devices(duration=5):
        """
        Scan for BLE devices to find your BMS name and address.

        Args:
            duration: Scan duration in seconds (default: 5)

        Returns:
            List of tuples (name, addr_type, addr) for discovered devices
        """
        print("BMS scan_devices called")
        try:
            import bluetooth
            from mpython_ble.advertising import decode_name
            from mpython_ble.const import IRQ
        except Exception as e:
            print("BLE scan: modules not available:", e)
            return []

        ble = bluetooth.BLE()
        ble.active(True)

        devices = []

        def _irq(event, data):
            if event == IRQ.IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                if isinstance(adv_data, memoryview):
                    adv_data = bytes(adv_data)
                addr_hex = bytes(addr).hex()
                print(f"\nDevice found - Addr: {addr_hex}, Type: {adv_type}, RSSI: {rssi}dBm")
                print(f"Raw adv_data: {adv_data}")
                
                # Print adv_data in hex for inspection
                print("adv_data hex:", " ".join(f"{b:02x}" for b in adv_data))
                
                # Try to parse the advertising data
                i = 0
                while i < len(adv_data):
                    length = adv_data[i]
                    if length == 0 or i + length > len(adv_data):
                        break
                        
                    adv_type = adv_data[i + 1]
                    adv_data_start = i + 2
                    adv_data_end = i + 1 + length
                    adv_data_bytes = adv_data[adv_data_start:adv_data_end]
                    if isinstance(adv_data_bytes, memoryview):
                        adv_data_bytes = bytes(adv_data_bytes)
                    
                    print(f"  AD Type: 0x{adv_type:02x}, Length: {length-1}, Data: {adv_data_bytes.hex()}")
                    
                    # Common AD Types
                    if adv_type == 0x01:  # Flags
                        print("    - Flags:", " ".join(f"{b:08b}" for b in adv_data_bytes))
                    elif adv_type == 0x08:  # Shortened Local Name
                        try:
                            print(f"    - Short Name: {adv_data_bytes.decode('ascii', 'replace')}")
                        except Exception as e:
                            print(f"    - Short Name (decode error): {e}")
                    elif adv_type == 0x09:  # Complete Local Name
                        try:
                            print(f"    - Complete Name: {adv_data_bytes.decode('ascii', 'replace')}")
                        except Exception as e:
                            print(f"    - Complete Name (decode error): {e}")
                    elif adv_type == 0xFF:  # Manufacturer Specific Data
                        print(f"    - Manufacturer Data: {adv_data_bytes.hex()}")
                    
                    i += 1 + length  # Move to next AD structure
                
                # Original name decoding for compatibility
                name = decode_name(adv_data)
                if isinstance(name, (memoryview, bytes)):
                    try:
                        if isinstance(name, memoryview):
                            name = bytes(name)
                        name = name.decode('utf-8', 'ignore').rstrip('\x00')
                    except Exception as e:
                        print(f"Name decode error: {e}")
                        name = None
                
                addr_bytes = bytes(addr)
                if not any(d[2] == addr_bytes for d in devices):
                    if name and name.strip():
                        print(f"  Found: {name} (RSSI: {rssi})")
                        devices.append((name, addr_type, addr_bytes))
                    else:
                        print(f"  Found: <no name> (RSSI: {rssi}) at {addr_hex}")
                        devices.append((f"<no name>", addr_type, addr_bytes))

        ble.irq(_irq)
        print(f"Scanning for BLE devices for {duration} seconds...")
        ble.gap_scan(int(duration * 1000), 30000, 30000)
        time.sleep(duration + 0.5)
        ble.gap_scan(None)  # Stop scanning
        ble.active(False)

        print(f"Scan complete. Found {len(devices)} device(s)")
        return devices

    def _watch_loop(self):
        """
        Internal background loop: connects to the BMS over BLE and periodically
        sends a request frame, printing any responses to the console.
        """
        try:
            from mpython_ble.application.centeral import Centeral
            from bluetooth import UUID
        except Exception as e:
            print("BMS watch: BLE modules not available:", e)
            self._running = False
            return

        if self.name is None and self.addr is None:
            print("BMS watch: ERROR - provide either 'name' or 'addr'")
            self._running = False
            return

        center = Centeral()

        print("BMS watch: scanning for device...")
        if self.name:
            print("  Name:", self.name)
        if self.addr:
            if isinstance(self.addr, (bytes, bytearray)):
                print("  Address:", self.addr.hex())
            else:
                print("  Address:", self.addr)

        profile = center.connect(name=self.name, addr=self.addr)
        if profile is None:
            print("BMS watch: failed to find or connect to BMS")
            self._running = False
            return

        print("BMS watch: connected, discovering UART characteristic...")

        uart_char = None
        uart_uuid = UUID(self.UART_UUID_STR)

        for service in profile.services:
            for ch in service.characteristics:
                try:
                    if ch.uuid == uart_uuid:
                        uart_char = ch
                        break
                except Exception:
                    if str(ch.uuid).lower() == self.UART_UUID_STR:
                        uart_char = ch
                        break
            if uart_char:
                break

        if uart_char is None:
            print("BMS watch: UART characteristic not found (UUID", self.UART_UUID_STR, ")")
            self._running = False
            center.disconnect()
            return

        print("BMS watch: using characteristic handle", uart_char.value_handle)

        def _notify_cb(value_handle, data):
            print("BMS notify (handle", value_handle, "):", data.hex())

        center.notify_callback(_notify_cb)

        print("BMS watch: starting polling loop (interval:", self.poll_interval, "s)")

        while self._running and center.is_connected():
            try:
                center.characteristic_write(uart_char.value_handle, self.REQUEST_FRAME)
            except Exception as e:
                print("BMS watch: write failed:", e)
                break
            time.sleep(self.poll_interval)

        print("BMS watch: stopping, disconnecting...")
        try:
            center.disconnect()
        except Exception:
            pass
        self._running = False

    def start(self):
        """
        Start watching BMS data over BLE and log it to the console.
        """
        if self._running:
            print("BMS watch is already running")
            return

        self._running = True
        try:
            self._thread = _thread.start_new_thread(self._watch_loop, ())
            print("BMS watch: background thread started")
        except Exception as e:
            print("BMS watch: failed to start thread:", e)
            self._running = False

    def stop(self):
        """
        Stop the BMS watch loop. The background thread will exit after the next poll.
        """
        if not self._running:
            print("BMS watch is not running")
            return
        self._running = False
        print("BMS watch: stop requested")


class Camera(object):
    # Frame size to resolution mapping (width, height)
    FRAME_RESOLUTIONS = {
        camera.FRAME_96X96: (96, 96),
        camera.FRAME_QQVGA: (160, 120),
        camera.FRAME_QCIF: (176, 144),
        camera.FRAME_HQVGA: (240, 176),
        camera.FRAME_240X240: (240, 240),
        camera.FRAME_QVGA: (320, 240),
        camera.FRAME_CIF: (400, 296),
        camera.FRAME_HVGA: (480, 320),
        camera.FRAME_VGA: (640, 480),
        camera.FRAME_SVGA: (800, 600),
        camera.FRAME_XGA: (1024, 768),
        camera.FRAME_HD: (1280, 720),
        camera.FRAME_SXGA: (1280, 1024),
        camera.FRAME_UXGA: (1600, 1200),
        camera.FRAME_FHD: (1920, 1080),
        camera.FRAME_P_HD: (720, 1280),
        camera.FRAME_P_3MP: (864, 1536),
        camera.FRAME_QXGA: (2048, 1536),
        camera.FRAME_QHD: (2560, 1440),
        camera.FRAME_WQXGA: (2560, 1600),
        camera.FRAME_P_FHD: (1080, 1920),
        camera.FRAME_QSXGA: (2560, 1920),
    }
    
    def __init__(self):
        self.cam = camera
        self.frame_size = camera.FRAME_HVGA  # Default
        self.pixel_format = camera.RGB565  # Default
        self.width = 480  # Default for HVGA
        self.height = 320  # Default for HVGA
    
    def init(self, framesize=None, format=None):
        """
        Initialize the camera.
        
        Args:
            framesize: Optional frame size constant (e.g., camera.FRAME_HVGA)
            format: Optional pixel format (e.g., camera.RGB565, camera.YUV422, camera.GRAYSCALE)
        """
        #复位摄像头
        myi2c = I2C(0, scl=Pin(48), sda=Pin(47), freq=100000)
        temp = myi2c.readfrom_mem(0x20, 0x06, 1)
        myi2c.writeto(0x20,bytearray([0x06, (temp[0] & 0xFD)]))
        temp = myi2c.readfrom_mem(0x20, 0x02, 1)
        myi2c.writeto(0x20,bytearray([0x02, (temp[0] | 0x00)]))
        time.sleep(0.1)
        temp = myi2c.readfrom_mem(0x20, 0x02, 1)
        myi2c.writeto(0x20,bytearray([0x02, (temp[0] | 0x02)]))
        
        # Store configuration
        if framesize is not None:
            self.frame_size = framesize
        if format is not None:
            self.pixel_format = format
        
        # Get resolution from frame size
        if self.frame_size in self.FRAME_RESOLUTIONS:
            self.width, self.height = self.FRAME_RESOLUTIONS[self.frame_size]
        
        # Initialize camera with stored config
        # Note: camera.init() first arg is camera ID (0), then keyword args
        if framesize is not None or format is not None:
            self.cam.init(0, framesize=self.frame_size, format=self.pixel_format)
        else:
            self.cam.init(0)
    
    def capture(self):
        return self.cam.capture()
    
    def encode_jpeg(self, buf=None, quality=12):
        """
        Encode a raw image buffer to JPEG.
        
        Args:
            buf: Optional image buffer from capture(). If None, captures a new frame.
            quality: JPEG quality (0-100, higher is better quality)
        
        Returns:
            JPEG encoded bytes, or False on error
        """
        
        try:
            # If no buffer provided, capture a new frame
            if buf is None:
                print("encode_jpeg buf is None, capturing...")
                buf = self.capture()
                time.sleep(0.1)
                buffer = self.capture()
                time.sleep(0.1)
                buffer = self.capture()
                lv.draw_sw_rgb565_swap(buffer,480*320*2)
                print("encode_jpeg captured buf type:", type(buf), "len:", len(buf) if buf else "None")

            if not buf:
                print("encode_jpeg buf is False/None after capture")
                return False
            
            # Check if buffer is already JPEG encoded
            if len(buf) >= 2 and buf[0] == 0xFF and buf[1] == 0xD8:
                print("encode_jpeg buf is JPEG")
                return buf  # Already JPEG, return as-is
            
            print("encode_jpeg encode_jpeg")
            # Encode raw format to JPEG
            jpeg_buf = self.cam.encode_jpeg(
                buf,                    # positional arg 1
                self.width,             # positional arg 2
                self.height,            # positional arg 3
                self.pixel_format,      # positional arg 4
                quality=quality         # keyword-only arg
            )
            print("encode_jpeg jpeg_buf", jpeg_buf)
            return jpeg_buf
        except Exception as e:
            print("Error encoding JPEG: {}".format(e))
            return False
    
    def save_to_file(self, filename, buf=None, quality=12):
        """
        Encode and save the captured image buffer to a JPEG file.
        
        Args:
            filename: Path to the output file (e.g., '/image.jpg' or '/sd/image.jpg')
            buf: Optional image buffer from capture(). If None, captures a new frame.
            quality: JPEG quality (0-100, higher is better quality)
        
        Returns:
            True if successful, False otherwise
        """

        print("save_to_file called with filename={}, buf={}, quality={}".format(
            filename, "None" if buf is None else "len={}".format(len(buf)), quality))

        try:
            # Encode to JPEG (handles both raw and already-JPEG buffers)
            print("save_to_file: calling encode_jpeg...")
            jpeg_buf = self.encode_jpeg(buf, quality)

            if not jpeg_buf:
                print("save_to_file: encode_jpeg failed")
                return False

            print("save_to_file: writing {} bytes to file {}".format(len(jpeg_buf), filename))

            # Open file in binary write mode
            with open(filename, 'wb') as f:
                f.write(jpeg_buf)

            print("save_to_file: successfully saved to file")
            return True
        except Exception as e:
            print("Error saving image to file: {}".format(e))
            return False

    def setParameter(self, whitebalance=0, brightness=0):
        """
        Set camera white balance and brightness settings.

        Args:
            whitebalance (int): White balance mode (0-4):
                0 - auto (default)
                1 - sunny
                2 - cloudy
                3 - office
                4 - home
            brightness (int): Brightness level (-2 to 2):
                -2 - darkest
                0 - default
                2 - brightest

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Set white balance
            if whitebalance < 0 or whitebalance > 4:
                print("Error: whitebalance must be between 0 and 4")
                return False
            self.cam.whitebalance(whitebalance)

            # Set brightness
            if brightness < -2 or brightness > 2:
                print("Error: brightness must be between -2 and 2")
                return False
            self.cam.brightness(brightness)

            return True
        except Exception as e:
            print("Error setting camera settings:", e)
            return False

    def deinit(self):
        self.cam.deinit()
      
'''
六轴 educore定时器
'''
class accelerometer():
    def __init__(self):
        self.tim_count = 0
        self._is_shaked = False
        self._last_x = 0
        self._last_y = 0
        self._last_z = 0
        self._count_shaked = 0
        myi2c = I2C(0, scl=Pin(48), sda=Pin(47), freq=100000)
        devices = myi2c.scan()
        if 0x19 in devices:
            #K10
            self.tim = Timer(17)
            self.tim.init(period=100, mode=Timer.PERIODIC, callback=self.educore_callback)
            self.accel_sensor = Accelerometer()
        else:
            #K10box
            self.tim = None
            self.accel_sensor = None

    def educore_callback(self, _):
        self.tim_count += 1 
        try:
            self.accelerometer_callback()
            try:
                gc.collect()
            except KeyboardInterrupt:
                print("educore_callback gc.collect KeyboardInterrupt - shutting down")
                if self.tim:
                    self.tim.deinit()
        except KeyboardInterrupt:
            print("KeyboardInterrupt out - shutting down")
            if self.tim:
                self.tim.deinit()
        except Exception as e:
            print("Exception out")
            print(str(e))
        if self.tim_count == 200:
            self.tim_count = 0

    def accelerometer_callback(self):
        '''加速度计'''
        try:
            if self._is_shaked:
                self._count_shaked += 1
                if self._count_shaked == 5:
                    self._count_shaked = 0
                    self.accel_sensor.shake_status = False
            self.accel_sensor._measure()
            x = self.accel_sensor.x()
            y = self.accel_sensor.y()
            z = self.accel_sensor.z()
            if self._last_x == 0 and self._last_y == 0 and self._last_z == 0:
                self._last_x = x
                self._last_y = y
                self._last_z = z
                self.accel_sensor.shake_status = False
                return
            diff_x = x - self._last_x
            diff_y = y - self._last_y
            diff_z = z - self._last_z
            self._last_x = x
            self.last_y = y
            self._last_z = z
            if self._count_shaked > 0:
                return
            self._is_shaked = (diff_x * diff_x + diff_y * diff_y + diff_z * diff_z > 1)
            if self._is_shaked:
                self.accel_sensor.shake_status = True
        except KeyboardInterrupt:
            print("accelerometer_callback KeyboardInterrupt - shutting down")
            if self.tim:
                self.tim.deinit()
            raise
        except Exception as e:
            print(f"accelerometer_callback Exception: {e}")
        
    def X(self):
        return self.accel_sensor.x()
    
    def Y(self):
        return self.accel_sensor.y()
    
    def Z(self):
        return self.accel_sensor.z()
    
    def read_x(self):
        return self.accel_sensor.x()
    
    def read_y(self):
        return self.accel_sensor.y()
    
    def read_z(self):
        return self.accel_sensor.z()
    
    def shake(self):
        return self.accel_sensor.shake()
    def gesture(self):
        return self.accel_sensor._gesture
    def status(self,status=""):
        if status is "forward":
            if self.gesture() == self.accel_sensor.TILT_FORWARD:
                return True
            else:
                return False
        elif status is "back":
            if self.gesture() == self.accel_sensor.TILT_BACK:
                return True
            else:
                return False
        elif status is "left":
            if self.gesture() == self.accel_sensor.TILT_LEFT:
                return True
            else:
                return False
        elif status is "right":
            if self.gesture() == self.accel_sensor.TILT_RIGHT:
                return True
            else:
                return False
        elif status is "up":
            if self.gesture() == self.accel_sensor.SCREEN_UP:
                return True
            else:
                return False
        elif status is "down":
            if self.gesture() == self.accel_sensor.SCREEN_DOWN:
                return True
            else:
                return False
        else:
            return False

    def deinit(self):
        self.tim.deinit()

'''继承wifi'''
class WiFi(wifi):
    def __init__(self):
        super().__init__()

    def connect(self, ssid, psd, timeout=10000):
        self.connectWiFi(ssid, psd, int(timeout/1000))
    
    def status(self):
        return self.sta.isconnected()

    def info(self):
        return str(self.sta.ifconfig())

'''MQTT'''
class MqttClient():
    def __init__(self):
        self.client = None
        self.server = None
        self.port = None
        self.client_id = None
        self.user = None
        self.passsword = None
        self.topic_msg_dict = {}
        self.topic_callback = {}
        self.tim_count = 0
        self._connected = False
        self.lock = False

    def connect(self, **kwargs):
        server = kwargs.get('server',"iot.mpython.cn" )
        port = kwargs.get('port',1883 )
        client_id = kwargs.get('client_id',"" )
        user = kwargs.get('user',"" )
        psd = kwargs.get('psd',None)
        password = kwargs.get('password',None)
        if(psd==None and password==None):
            psd = ""
        elif(password!=None):
            psd = password
        try:
            self.client = MQTT(client_id, server, port, user, psd, 60)
            self.client.connect()
            self.server = server
            self.port = port
            self.client_id = client_id
            self.user = user
            self.passsword = psd
            print('Connected to MQTT Broker "{}"'.format(self.server))
            self._connected = True
            self.client.set_callback(self.on_message)
            time.sleep(0.5)
            self.tim = Timer(15)
            self.tim.init(period=100, mode=Timer.PERIODIC, callback=self.mqtt_heartbeat)
            gc.collect()
        except Exception as e:
            print('Connected to MQTT Broker error:{}'.format(e))

    def connected(self):
        return self._connected

    def publish(self, topic, content, _qos = 1):
        try:
            self.lock = True
            self.client.publish(str(topic),str(content).encode("utf-8"),qos=_qos)
            self.lock = False
        except Exception as e:
            print('publish error:{}'.format(e))

    def message(self, topic):
        topic = str(topic)
        if(not topic in self.topic_msg_dict):
            # self.topic_msg_dict[topic] = None
            self.topic_callback[topic] = False 
            self.subscribe(topic, self.default_callbak)
            return self.topic_msg_dict[topic]
        else:
            return self.topic_msg_dict[topic]
        
    def received(self, topic, callback):
        self.subscribe(topic, callback)

    def subscribe(self, topic, callback):
        self.lock = True
        try:
            topic = str(topic)
            if(not topic in self.topic_msg_dict):
                global _callback
                _callback = callback
                self.topic_msg_dict[topic] = None
                self.topic_callback[topic] = True
                exec('global mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic)),globals())
                exec('mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic)) + ' = _callback',globals())
                self.client.subscribe(topic)
                time.sleep(0.1)
            elif(topic in self.topic_msg_dict and self.topic_callback[topic] == False):
                global _callback
                _callback = callback
                self.topic_callback[topic] = True
                exec('global mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic)),globals())
                exec('mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic)) + ' = _callback',globals())
                time.sleep(0.1)
            else:
                print('Already subscribed to the topic:{}'.format(topic))
            self.lock = False
        except Exception as e:
            print('MQTT subscribe error:'+str(e))

    def on_message(self, topic, msg):
        try:
            gc.collect()
            topic = topic.decode('utf-8', 'ignore')
            msg = msg.decode('utf-8', 'ignore')
            #print("Received '{payload}' from topic '{topic}'\n".format(payload = msg, topic = topic))
            if(topic in self.topic_msg_dict):
                self.topic_msg_dict[topic] = msg
                if(self.topic_callback[topic]):
                    exec('global mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic)),globals())
                    eval('mqtt_topic_' + bytes.decode(ubinascii.hexlify(topic))+'()',globals())
        except Exception as e:
            print('MQTT on_message error:'+str(e))
    
    def default_callbak(self):
        pass
    
    def mqtt_check_msg(self):
        try:
            self.client.check_msg()
        except Exception as e:
            print('MQTT check msg error:'+str(e))

    def mqtt_heartbeat(self,_):
        self.tim_count += 1 
        if(not self.lock):
            self.mqtt_check_msg()
        if(self.tim_count==200):
            self.tim_count = 0
            try:
                self.client.ping() # 心跳消息
                self._connected = True
            except Exception as e:
                print('MQTT keepalive ping error:'+str(e))
                self._connected = False

'''
K10扬声器类
'''
class Speaker(object):
    def __init__(self):
        print("init speaker\n")
        self.i2s = I2S(1,sck = 0,ws=38, sd= 45, mode=I2S.TX, bits=32, format=I2S.MONO, rate=16000, ibuf=20000)
        self.i2s.deinit()
        self._i2c = k10_i2c
        print("init done\n")
        self.buzzMelody = 2
        self.playTone = 2
        self.freqTable = [ 31, 33, 35, 37, 39, 41, 44, 46, 49, 52, 55, 58, 62, 65, 69, 73, 78, 82, 87, 92, 98, 104, 110, 
                          117, 123, 131, 139, 147, 156, 165, 175, 185, 196, 208, 220, 233, 247, 262, 277, 294, 311, 330, 349, 370, 392, 
                          415, 440, 466, 494, 523, 554, 587, 622, 659, 698, 740, 784, 831, 880, 932, 988, 1047, 1109, 1175, 1245, 1319, 
                          1397, 1480, 1568, 1661, 1760, 1865, 1976, 2093, 2217, 2349, 2489, 2637, 2794, 2960, 3136, 3322, 3520, 3729, 3951, 4186]
        self.currentDuration = 4  # Default duration (Crotchet)
        self.currentOctave = 4    # Middle octave
        self.beatsPerMinute = 15  # Default BPM
        self.TWO_PI = 6.283185307179586476925286766559
        self.music_notes={"DADADADUM":"r4:2|g|g|g|eb:8|r:2|f|f|f|d:8|",
                          "ENTERTAINER":"d4:1|d#|e|c5:2|e4:1|c5:2|e4:1|c5:3|c:1|d|d#|e|c|d|e:2|b4:1|d5:2|c:4|",
                          "PRELUDE":"c4:1|e|g|c5|e|g4|c5|e|c4|e|g|c5|e|g4|c5|e|c4|d|g|d5|f|g4|d5|f|c4|d|g|d5|f|g4|d5|f|b3|d4|g|d5|f|g4|d5|f|b3|d4|g|d5|f|g4|d5|f|c4|e|g|c5|e|g4|c5|e|c4|e|g|c5|e|g4|c5|e|",
                          "ODE":"e4|e|f|g|g|f|e|d|c|c|d|e|e:6|d:2|d:8|e:4|e|f|g|g|f|e|d|c|c|d|e|d:6|c:2|c:8|",
                          "NYAN":"f#5:2|g#|c#:1|d#:2|b4:1|d5:1|c#|b4:2|b|c#5|d|d:1|c#|b4:1|c#5:1|d#|f#|g#|d#|f#|c#|d|b4|c#5|b4|d#5:2|f#|g#:1|d#|f#|c#|d#|b4|d5|d#|d|c#|b4|c#5|d:2|b4:1|c#5|d#|f#|c#|d|c#|b4|c#5:2|b4|c#5|b4|f#:1|g#|b:2|f#:1|g#|b|c#5|d#|b4|e5|d#|e|f#|b4:2|b|f#:1|g#|b|f#|e5|d#|c#|b4|f#|d#|e|f#|b:2|f#:1|g#|b:2|f#:1|g#|b|b|c#5|d#|b4|f#|g#|f#|b:2|b:1|a#|b|f#|g#|b|e5|d#|e|f#|b4:2|c#5|",
                          "RINGTONE":"c4:1|d|e:2|g|d:1|e|f:2|a|e:1|f|g:2|b|c5:4|",
                          "FUNK":"c2:2|c|d#|c:1|f:2|c:1|f:2|f#|g|c|c|g|c:1|f#:2|c:1|f#:2|f|d#|",
                          "BIRTHDAY":"c4:3|c:1|d:4|c:4|f|e:8|c:3|c:1|d:4|c:4|g|f:8|c:3|c:1|c5:4|a4|f|e|d|a#:3|a#:1|a:4|f|g|f:8|",
                          "WEDDING":"c4:4|f:3|f:1|f:8|c:4|g:3|e:1|f:8|c:4|f:3|a:1|c5:4|a4:3|f:1|f:4|e:3|f:1|g:8|",
                          "FUNERAL":"c3:4|c:3|c:1|c:4|d#:3|d:1|d:3|c:1|c:3|b2:1|c3:4|",
                          "PUNCHLINE":"c4:3|g3:1|f#|g|g#:3|g|r|b|c4|",
                          "BADDY":"c3:3|r|d:2|d#|r|c|r|f#:8|",
                          "CHASE":"a4:1|b|c5|b4|a:2|r|a:1|b|c5|b4|a:2|r|a:2|e5|d#|e|f|e|d#|e|b4:1|c5|d|c|b4:2|r|b:1|c5|d|c|b4:2|r|b:2|e5|d#|e|f|e|d#|e|",
                          "BA_DING":"b5:1|e6:3|",
                          "JUMP_UP":"c5:1|d|e|f|g|",
                          "JUMP_DOWN":"g5:1|f|e|d|c|",
                          "POWER_UP":"g4:1|c5|e|g:2|e:1|g:3|",
                          "POWER_DOWN":"g5:1|d#|c|g4:2|b:1|c5:3|"}
        

    def __del__(self):
        print("Speaker deleted\n")
        if self.i2s:
            self.i2s.deinit()
            self.i2s = None
        try:
            self._i2c.writeto_mem(0x20,0x2A,bytearray([0x00]))
        except:
            pass

    def deinit(self):
        print("Speaker deinit\n")
        if self.i2s:
            self.i2s.deinit()
            self.i2s = None
        try:
            self._i2c.writeto_mem(0x20,0x2A,bytearray([0x00]))
        except:
            pass
        
    def reinit(self,bits=16,sample_rate=16000,channels=1):
        self.i2s = I2S(1,sck = 0, ws = 38, sd = 45,mode=I2S.TX, bits=bits, 
                       format=I2S.MONO if channels == 1 else I2S.STEREO, rate=sample_rate, ibuf=20000)

    def parse_wav_header(self, wav_file):
        # 解析 WAV 文件头部
        wav_file.seek(0)
        riff = wav_file.read(4)
        if riff != b'RIFF':
            raise ValueError("Not a valid WAV file")

        wav_file.seek(22)
        num_channels = int.from_bytes(wav_file.read(2), 'little')
        sample_rate = int.from_bytes(wav_file.read(4), 'little')

        wav_file.seek(34)
        bits_per_sample = int.from_bytes(wav_file.read(2), 'little')

        return sample_rate, bits_per_sample, num_channels
    
    def play_tone(self,freq, beat):
        buf = bytearray(4)
        for i in range(beat):
            sample = int(32767.0 * math.sin(i * 2 * math.pi  * freq / 8000))
            struct.pack_into('<hh', buf, 0, sample, sample)  # 打包左右声道
            self.i2s.write(buf)

    def play_tone_music(self,tone_music: str):
        name = tone_music.upper()  # 确保输入大写
        if name in self.music_notes:
            music_sequence = self.music_notes[name]
            for note in music_sequence.split("|"):
                if note:  # 跳过空字符串
                    self.play_next_note(note)  # 调用实际播放方法
                    
        else:
            print(f"Error: {name} not found in music_data")
            pass

    def play_next_note(self, tone: str):
        curr_note = tone
        current_duration = self.currentDuration
        current_octave = self.currentOctave
        is_rest = False
        parsing_octave = True
        note = 0
        beat_pos = 0

        for pos, note_char in enumerate(curr_note):
            if note_char in ['c', 'C']:
                note = 1
            elif note_char in ['d', 'D']:
                note = 3
            elif note_char in ['e', 'E']:
                note = 5
            elif note_char in ['f', 'F']:
                note = 6
            elif note_char in ['g', 'G']:
                note = 8
            elif note_char in ['a', 'A']:
                note = 10
            elif note_char in ['b', 'B']:
                note = 12
            elif note_char in ['r', 'R']:
                is_rest = True
            elif note_char == '#':
                note += 1
            elif note_char == ':':
                parsing_octave = False
                beat_pos = pos
            elif parsing_octave and note_char.isdigit():
                current_octave = int(note_char)
        
        if not parsing_octave and beat_pos + 1 < len(curr_note) and curr_note[beat_pos + 1].isdigit():
            current_duration = int(curr_note[beat_pos + 1])

        beat = (60000 / self.beatsPerMinute) / 4

        if not is_rest:
            key_number = note + (12 * (current_octave - 1))
            frequency = self.freqTable[key_number] if 0 <= key_number < len(self.freqTable) else 0
            self.play_tone(frequency, current_duration * beat) #发送声音效果

        self.currentDuration = current_duration
        self.currentOctave = current_octave

    def play_sys_music(self,path):
        full_path = "/" + path
        self.play_music(full_path)

    def play_tf_music(self, path):
        full_path = "/sd/" + path
        self.play_music(full_path)
        
    def play_music(self,path):
        #使能功放(k10 box才有的功能)
        try:
            self._i2c.writeto_mem(0x20,0x2A,bytearray([0x01]))
        except:
            pass
        #打开WAV文件
        with open(path,"rb") as wav_file:
            sample_rate, bits_per_sample, num_channels = self.parse_wav_header(wav_file)
            self.reinit(bits=bits_per_sample,sample_rate=sample_rate,channels=num_channels)
            while True:
                audio_buf = wav_file.read(1024)
                if not audio_buf:
                    break
                self.i2s.write(audio_buf)
        self.i2s.deinit()
        #失能功放
        try:
            self._i2c.writeto_mem(0x20,0x2A,bytearray([0x00]))
        except:
            pass

    def stop_music(self):
        self.i2s.deinit()
        #失能功放
        try:
            self._i2c.writeto_mem(0x20,0x2A,bytearray([0x00]))
        except:
            pass


class Es7243e(object):
    ES7243E_ADDR1 = 0X15
    ES7243E_ADDR2 = 0X11
    def __init__(self, i2c):
        self.i2c = i2c
        self.devices = self.i2c.scan()
        if self.devices:
            if self.ES7243E_ADDR1 in self.devices:
                self.ctrl_state(self.ES7243E_ADDR1,False)
                time.sleep(0.1)
                self.config(self.ES7243E_ADDR1)
                time.sleep(0.1)
                self.ctrl_state(self.ES7243E_ADDR1,True)
            elif self.ES7243E_ADDR2 in self.devices:
                self.ctrl_state(self.ES7243E_ADDR2,False)
                time.sleep(0.1)
                self.config(self.ES7243E_ADDR2)
                time.sleep(0.1)
                self.ctrl_state(self.ES7243E_ADDR2,True)
            else:
                print("mic init error")
                pass
    def write_cmd(self,addr, reg, cmd):
        send_buf = bytearray(2)
        send_buf[0] = reg
        send_buf[1] = cmd
        self.i2c.writeto(addr, send_buf)
    
    def ctrl_state(self, addr, state):
        if state:
            self.write_cmd(addr, 0xF9, 0x00)
            self.write_cmd(addr, 0xF9, 0x00)
            self.write_cmd(addr, 0x04, 0x01)
            self.write_cmd(addr, 0x17, 0x01)
            self.write_cmd(addr, 0x20, 0x10)
            self.write_cmd(addr, 0x21, 0x10)
            self.write_cmd(addr, 0x00, 0x80)
            self.write_cmd(addr, 0x01, 0x3A)
            self.write_cmd(addr, 0x16, 0x3F)
            self.write_cmd(addr, 0x16, 0x00)
        else:
            self.write_cmd(addr, 0x04, 0x02)
            self.write_cmd(addr, 0x04, 0x01)
            self.write_cmd(addr, 0xF7, 0x30)
            self.write_cmd(addr, 0xF9, 0x01)
            self.write_cmd(addr, 0x16, 0xFF)
            self.write_cmd(addr, 0x17, 0x00)
            self.write_cmd(addr, 0x01, 0x38)
            self.write_cmd(addr, 0x20, 0x00)
            self.write_cmd(addr, 0x21, 0x00)
            self.write_cmd(addr, 0x00, 0x00)
            self.write_cmd(addr, 0x00, 0x1E)
            self.write_cmd(addr, 0x01, 0x30)
            self.write_cmd(addr, 0x01, 0x00)
    
    def config(self,addr):
        self.write_cmd(addr, 0x01, 0x3A)
        self.write_cmd(addr, 0x00, 0x80)
        self.write_cmd(addr, 0xF9, 0x00)
        self.write_cmd(addr, 0x04, 0x02)
        self.write_cmd(addr, 0x04, 0x01)
        self.write_cmd(addr, 0xF9, 0x01)
        self.write_cmd(addr, 0x00, 0x1E)
        self.write_cmd(addr, 0x01, 0x00)
        
        self.write_cmd(addr, 0x02, 0x00)
        self.write_cmd(addr, 0x03, 0x20)
        self.write_cmd(addr, 0x04, 0x03)
        self.write_cmd(addr, 0x0D, 0x00)
        self.write_cmd(addr, 0x05, 0x00)
        self.write_cmd(addr, 0x06, 0x03)
        self.write_cmd(addr, 0x07, 0x00)
        self.write_cmd(addr, 0x08, 0xFF)

        self.write_cmd(addr, 0x09, 0xCA)
        self.write_cmd(addr, 0x0A, 0x85)
        self.write_cmd(addr, 0x0B, 0x2C)
        self.write_cmd(addr, 0x0E, 0xff)
        self.write_cmd(addr, 0x0F, 0x80)
        self.write_cmd(addr, 0x14, 0x0C)
        self.write_cmd(addr, 0x15, 0x0C)
        self.write_cmd(addr, 0x17, 0x02)
        self.write_cmd(addr, 0x18, 0x26)
        self.write_cmd(addr, 0x19, 0x77)
        self.write_cmd(addr, 0x1A, 0xF4)
        self.write_cmd(addr, 0x1B, 0x66)
        self.write_cmd(addr, 0x1C, 0x44)
        self.write_cmd(addr, 0x1E, 0x00)
        self.write_cmd(addr, 0x1F, 0x0C)
        self.write_cmd(addr, 0x20, 0x1A)
        self.write_cmd(addr, 0x21, 0x1A)
        
        self.write_cmd(addr, 0x00, 0x80)
        self.write_cmd(addr, 0x01, 0x3A)
        self.write_cmd(addr, 0x16, 0x3F)
        self.write_cmd(addr, 0x16, 0x00)
        

class Mic(object):
    def __init__(self,bits=16,sample_rate=16000,channels=1):
        self.mic = Es7243e(i2c)
        self.i2s = I2S(0,sck = 0, ws = 38, sd = 39,mode=I2S.RX, bits=bits, 
                       format=I2S.MONO if channels == 1 else I2S.STEREO, rate=sample_rate, ibuf=20000)
        self.i2s.deinit()
        self.bits = bits
        self.sample_rate = sample_rate
        self.channels = channels
        self.time = time
    def reinit(self,bits=16,sample_rate=16000,channels=1):
        self.i2s = I2S(0,sck = 0, ws = 38, sd = 39,mode=I2S.RX, bits=bits, 
                       format=I2S.MONO if channels == 1 else I2S.STEREO, rate=sample_rate, ibuf=20000)


    def write_wav_header(self, file, num_samples):
        # 计算文件大小
        byte_rate = self.sample_rate * self.channels * self.bits // 8
        block_align = self.channels * self.bits // 8
        data_size = num_samples * block_align
        file_size = data_size + 36
        
        # 写入 WAV 文件头
        file.write(b'RIFF')
        file.write(file_size.to_bytes(4, 'little'))
        file.write(b'WAVE')
        file.write(b'fmt ')  # 子块ID
        file.write((16).to_bytes(4, 'little'))  # 子块大小
        file.write((1).to_bytes(2, 'little'))   # 音频格式（1是PCM）
        file.write(self.channels.to_bytes(2, 'little'))
        file.write(self.sample_rate.to_bytes(4, 'little'))
        file.write(byte_rate.to_bytes(4, 'little'))
        file.write(block_align.to_bytes(2, 'little'))
        file.write(self.bits.to_bytes(2, 'little'))
        file.write(b'data')
        file.write(data_size.to_bytes(4, 'little'))

    def recode_to_wav(self,path,time):
        self.reinit(bits = self.bits, sample_rate = self.sample_rate, channels=self.channels)
        #创建录音缓存区
        buffer_size = 1024
        audio_buf = bytearray(buffer_size)

        #打开WAV文件
        with open(path, 'wb') as wav_file:
            #暂时写入WAV文件头，后续更新数据大小
            self.write_wav_header(wav_file,num_samples=0)

            #开始录音
            num_samples = 0
            start_time = self.time.time()
            while self.time.time() - start_time < time:
                #从I2S中读取数据
                self.i2s.readinto(audio_buf)
                wav_file.write(audio_buf)
                num_samples += len(audio_buf) // (self.bits // 8)
            #更新文件头中的实际数据大小
            wav_file.seek(0)
            self.write_wav_header(wav_file, num_samples)
        self.i2s.deinit()
        print("Recording saved to:", path)
    def recode_sys(self, name="",time=10):
        full_path = "/" + name
        self.recode_to_wav(path=full_path, time=time)

    def recode_tf(self, name="",time=10):
        full_path = "/sd/" + name
        self.recode_to_wav(path=full_path, time=time)

class TF_card(object):
    def __init__(self):
        self.spi_bus = SPI.Bus(host = 1, mosi = 42, miso = 41, sck = 44)
        self.sd = SDCard(spi_bus = self.spi_bus, cs = 40, freq = 1000000)
        try:
            vfs.mount(self.sd, "/sd")
        except:
            print("SD card not detected")
