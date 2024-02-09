from machine import Pin, SDCard, SPI, RTC
import time, os, json, math
from lib import keyboard, beeper
from lib import microhydra as mh
import machine
from lib import st7789py as st7789
from launcher.icons import icons
from font import vga1_8x16 as fontsmall
from font import vga2_16x32 as font





"""

VERSION: 0.4

CHANGES: added settings app, added wifi settings, fixed display not centering properly on scoll, added scroll bar.


This program is designed to be used in conjunction with the "apploader.py" program, to select and launch MPy apps for the Cardputer.

The basic app loading logic works like this:

 - apploader reads reset cause and RTC.memory to determine which app to launch
 - apploader launches 'launcher.py' when hard reset, or when RTC.memory is blank
 - launcher scans app directories on flash and SDCard to find apps
 - launcher shows list of apps, allows user to select one
 - launcher stores path to app in RTC.memory, and soft-resets the device
 - apploader reads RTC.memory to find path of app to load
 - apploader clears the RTC.memory, and imports app at the given path
 - app at given path now has control of device.
 - pressing the reset button will relaunch the launcher program, and so will calling machine.reset() from the app. 



This approach was chosen to reduce the chance of conflicts or memory errors when switching apps.
Because MicroPython completely resets between apps, the only "wasted" ram from the app switching process will be from launcher.py



"""



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Constants: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

black = const(0)
white = const(65535)
default_ui_color = const(53243)
default_bg_color = const(4421)
default_ui_sound = const(True)
default_volume = const(2)

appname_y = const(80) 
target_vscsad = const(40) # scrolling display "center"

display_width = const(240)
display_height = const(135)





#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Finding Apps ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




def scan_apps():
    # first we need a list of apps located on the flash or SDCard

    main_directory = os.listdir("/")

    # if the sd card is not mounted, we need to mount it.
    if "sd" not in main_directory:
        sd = SDCard(slot=2, sck=Pin(40), miso=Pin(39), mosi=Pin(14), cs=Pin(12))
        
        try:
            os.mount(sd, '/sd')
        except OSError:
            print("Could not mount SDCard!")
            
        main_directory = os.listdir("/")

    sd_directory = []
    if "sd" in main_directory:
        sd_directory = os.listdir("/sd")

    # if the apps folder does not exist, create it.
    if "apps" not in main_directory:
        os.mkdir("/apps")
        main_directory = os.listdir("/")
        
    # do the same for the sdcard apps directory
    if "apps" not in sd_directory and "sd" in main_directory:
        os.mkdir("/sd/apps")
        sd_directory = os.listdir("/sd")



    # if everything above worked, sdcard should be mounted (if available), and both app directories should exist. now look inside to find our apps:
    main_app_list = os.listdir("/apps")
    sd_app_list = []

    if "sd" in main_directory:
        sd_app_list = os.listdir("/sd/apps")





    # now lets collect some separate app names and locations
    app_names = []
    app_paths = {}

    for entry in main_app_list:
        if entry.endswith(".py"):
            this_name = entry[:-3]
            
            # the purpose of this check is to prevent dealing with duplicated apps.
            # if multiple apps share the same name, then we will simply use the app found most recently. 
            if this_name not in app_names:
                app_names.append( this_name ) # for pretty display
            
            app_paths[f"{this_name}"] = f"/apps/{entry}"

        elif entry.endswith(".mpy"):
            this_name = entry[:-4]
            if this_name not in app_names:
                app_names.append( this_name )
            app_paths[f"{this_name}"] = f"/apps/{entry}"
            
            
    for entry in sd_app_list:
        if entry.endswith(".py"): #repeat for sdcard
            this_name = entry[:-3]
            
            if this_name not in app_names:
                app_names.append( this_name )
            
            app_paths[f"{this_name}"] = f"/sd/apps/{entry}"
    
    app_names.sort()
    
    #add an appname to refresh the app list
    app_names.append("Reload Apps")
    #add an appname to control the beeps
    app_names.append("UI Sound")
    #add an appname to open settings app
    app_names.append("Settings")
    app_paths["Settings"] = ".frozen/launcher/settings.py" # this path must be modified for 'frozen' version
    
    
    return app_names, app_paths










#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Function Definitions: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def launch_app(app_path):
    #print(f'launching {app_path}')
    rtc = machine.RTC()
    rtc.memory(app_path)
    time.sleep_ms(10)
    machine.reset()
    



def center_text_x(text, char_width = 16):
    """
        Calculate the x coordinate to draw a text string, to make it horizontally centered. (plus the text width)
    """
    str_width = len(text) * char_width
    # display is 240 px wide
    start_coord = 120 - (str_width // 2)
    
    return start_coord, str_width


def easeInCubic(x):
    return x * x * x

def easeOutCubic(x):
    return 1 - ((1 - x) ** 3)






#--------------------------------------------------------------------------------------------------
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Loop: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#--------------------------------------------------------------------------------------------------




def main_loop():
    
    #bump up our clock speed so the UI feels smoother (240mhz is the max officially supported, but the default is 160mhz)
    machine.freq(240_000_000)
    
    #before anything else, we should scan for apps
    app_names, app_paths = scan_apps()
    app_selector_index = 0
    prev_selector_index = 0
    
    
    #init the keyboard
    kb = keyboard.KeyBoard()
    pressed_keys = []
    prev_pressed_keys = []
    
    
    
    
    #init driver for the graphics
    spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None)
    tft = st7789.ST7789(
    spi,
    display_height,
    display_width,
    reset=Pin(33, Pin.OUT),
    cs=Pin(37, Pin.OUT),
    dc=Pin(34, Pin.OUT),
    backlight=Pin(38, Pin.OUT),
    rotation=1,
    color_order=st7789.BGR
    )
    
    tft.vscrdef(40,display_width,40)
    tft.vscsad(target_vscsad)
    
    
    
    
    
    # variables:
    config_modified = False
    #load config
    try:
        with open("config.json", "r") as conf:
            config = json.loads(conf.read())
            ui_color = config["ui_color"]
            bg_color = config["bg_color"]
            ui_sound = config["ui_sound"]
            volume = config["volume"]
            wifi_ssid = config["wifi_ssid"]
            wifi_pass = config["wifi_pass"]
    except:
        print("could not load settings from config.json. reloading default values.")
        config_modified = True
        ui_color = default_ui_color
        bg_color = default_bg_color
        ui_sound = default_ui_sound
        volume = default_volume
        wifi_ssid = ''
        wifi_pass = ''
        with open("config.json", "w") as conf:
            config = {"ui_color":ui_color, "bg_color":bg_color, "ui_sound":ui_sound, "volume":volume, "wifi_ssid":'', "wifi_pass":''}
            conf.write(json.dumps(config))
        
    mid_color = mh.mix_color565(bg_color, ui_color)
        
    nonscroll_elements_displayed = False
    
    force_redraw_display = True
    
    #this is used as a flag to tell a future loop to redraw the frame mid-scroll animation
    delayed_redraw = False
    
    launching = False
    current_vscsad = 40
    
    scroll_direction = 0 #1 for right, -1 for left, 0 for center
    refresh_timer = 0
    
    #init the beeper!
    beep = beeper.Beeper()
    
    #starupp sound
    if ui_sound:
        beep.play('C4 D4 D4',0.12,volume)
    #init diplsay
    tft.fill_rect(-40,0,280, display_height, bg_color)
    
    
    while True:
        
        
        # ----------------------- check for key presses on the keyboard. Only if they weren't already pressed. --------------------------
        pressed_keys = kb.get_pressed_keys()
        if pressed_keys != prev_pressed_keys:
            
            # ~~~~~~ check if the arrow keys are newly pressed ~~~~~
            if "/" in pressed_keys and "/" not in prev_pressed_keys: # right arrow
                app_selector_index += 1
                
                #animation:

                scroll_direction = 1
                current_vscsad = target_vscsad
                if ui_sound:
                    beep.play("D6 C5", 0.1, volume)

                
            elif "," in pressed_keys and "," not in prev_pressed_keys: # left arrow
                app_selector_index -= 1
                
                #animation:
                
                scroll_direction = -1
                
                #this prevents multiple scrolls from messing up the animation
                current_vscsad = target_vscsad
                
                if ui_sound:
                    beep.play("D6 C5", 0.1, volume)
                
            
        
            # ~~~~~~~~~~ check if GO or ENTER are pressed ~~~~~~~~~~
            if "GO" in pressed_keys or "ENT" in pressed_keys:
                
                # special "settings" app options will have their own behaviour, otherwise launch the app
                if app_names[app_selector_index] == "UI Sound":
                    
                    if ui_sound == 0: # currently muted, then unmute
                        ui_sound = True
                        force_redraw_display = True
                        beep.play("C4 G4 G4", 0.2, volume)
                        config_modified = True
                    else: # currently unmuted, then mute
                        ui_sound = False
                        force_redraw_display = True
                        config_modified = True
                
                elif app_names[app_selector_index] == "Reload Apps":
                    app_names, app_paths = scan_apps()
                    app_selector_index = 0
                    current_vscsad = 42 # forces scroll animation triggers
                    if ui_sound:
                        beep.play('D4 C4 D4',0.08,volume)
                        
                else: # ~~~~~~~~~~~~~~~~~~~ LAUNCH THE APP! ~~~~~~~~~~~~~~~~~~~~
                    
                    #save config if it has been changed:
                    if config_modified:
                        with open("config.json", "w") as conf:
                            config = {
                            "ui_color":ui_color,
                            "bg_color":bg_color,
                            "ui_sound":ui_sound,
                            "volume":volume,
                            "wifi_ssid":wifi_ssid,
                            "wifi_pass":wifi_pass}
                            conf.write(json.dumps(config))
                        
                    # shut off the display
                    tft.fill(black)
                    tft.sleep_mode(True)
                    Pin(38, Pin.OUT).value(0) #backlight off
                    spi.deinit()
                    
                    if ui_sound:
                        beep.play('C4 B4 C5 C5',0.14,volume)
                        
                    launch_app(app_paths[app_names[app_selector_index]])
                
                
                
            # once we parse the keypresses for this loop, we need to store them for next loop
            prev_pressed_keys = pressed_keys
        
        
        
        
        #wrap around our selector index, in case we go over or under the target amount
        app_selector_index = app_selector_index % len(app_names)
    
    
        time.sleep_ms(4) #this loop runs about 3000 times a second without sleeps. The sleeps actually help things feel smoother.
        
        
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Graphics: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        #decide now if we will be redrawing the text.
        # we are capturing this so that we can black out and redraw the screen in two parts
        if (app_selector_index != prev_selector_index):
            delayed_redraw = True
        
        
        prev_app_text = app_names[prev_selector_index]
        current_app_text = app_names[app_selector_index]
        
        
        
        
        # if scrolling animation, move in the direction specified!
        if scroll_direction != 0:
            tft.vscsad(current_vscsad % 240)
            if scroll_direction == 1:
                current_vscsad += math.floor(easeOutCubic((current_vscsad - 40) / 120) * 10) + 5
                if current_vscsad >= 160:
                    current_vscsad = -80
                    scroll_direction = 0
            else:
                current_vscsad -= math.floor(easeOutCubic((current_vscsad - 40) / -120) * 10) + 5
                if current_vscsad <= -80:
                    current_vscsad = 160
                    scroll_direction = 0

                
        # if vscsad/scrolling is not centered, move it toward center!
        if scroll_direction == 0 and current_vscsad != target_vscsad:
            tft.vscsad(current_vscsad % 240)
            if current_vscsad < target_vscsad:

                current_vscsad += (abs(current_vscsad - target_vscsad) // 8) + 1
            elif current_vscsad > target_vscsad:
                current_vscsad -= (abs(current_vscsad - target_vscsad) // 8) + 1

        
        
        # if we are scrolling, we should change some UI elements until we finish
        if nonscroll_elements_displayed and (current_vscsad != target_vscsad):
            tft.fill_rect(0,133,240,2,bg_color) # erase scrollbar
            nonscroll_elements_displayed = False
            
            
        elif nonscroll_elements_displayed == False and (current_vscsad == target_vscsad):
            #scroll bar
            scrollbar_width = 240 // len(app_names)
            tft.fill_rect((scrollbar_width * app_selector_index),133,scrollbar_width,2,mid_color)
            nonscroll_elements_displayed = True
            
        
        #refresh the text mid-scroll, or when forced
        if (delayed_redraw and scroll_direction == 0 ) or force_redraw_display:
            #delayed_redraw = False
            refresh_timer += 1
            
            if refresh_timer == 1 or force_redraw_display: # redraw text
                #crop text for display
                if len(prev_app_text) > 15:
                    prev_app_text = prev_app_text[:12] + "..."
                if len(current_app_text) > 15:
                    current_app_text = current_app_text[:12] + "..."
                
                #blackout the old text
                tft.fill_rect(-40, appname_y, 280, 32, bg_color)
            
                #draw new text
                tft.text(font, current_app_text, center_text_x(current_app_text)[0], appname_y, ui_color, bg_color)
            
            if refresh_timer == 2 or force_redraw_display: # redraw icon
                refresh_timer = 0
                delayed_redraw = False
                
                #blackout old icon #TODO: delete this step when all text is replaced by icons
                tft.fill_rect(96, 30, 48, 32, bg_color)
                
                #special menu options for settings
                if current_app_text == "UI Sound":
                    if ui_sound:
                        tft.text(font, "On", center_text_x("On")[0], 30, white, bg_color)
                    else:
                        tft.text(font, "Off", center_text_x("Off")[0], 30, white, bg_color)
                        
                elif current_app_text == "Reload Apps":
                    tft.bitmap_icons(icons, icons.RELOAD, (bg_color,ui_color),104, 30)
                    
                elif current_app_text == "Settings":
                    tft.bitmap_icons(icons, icons.GEAR, (bg_color,ui_color),104, 30)
                    
                elif app_paths[app_names[app_selector_index]][:3] == "/sd":
                    tft.bitmap_icons(icons, icons.SDCARD, (bg_color,ui_color),104, 30)
                else:
                    tft.bitmap_icons(icons, icons.FLASH, (bg_color,ui_color),104, 30)
            

        
            
        
        #reset vars for next loop
        force_redraw_display = False
        
        #update prev app selector index to current one for next cycle
        prev_selector_index = app_selector_index
            
        
        
# run the main loop!
main_loop()



