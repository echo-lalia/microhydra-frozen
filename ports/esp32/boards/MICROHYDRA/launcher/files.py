from lib import st7789fbuf, mhconfig, mhoverlay, smartkeyboard, beeper
from font import vga2_16x32 as font
import os, machine, time, math


_DISPLAY_HEIGHT = const(135)
_DISPLAY_WIDTH = const(240)

_ITEMS_PER_SCREEN = const(_DISPLAY_HEIGHT // 32)
_ITEMS_PER_SCREEN_MINUS = const(_ITEMS_PER_SCREEN - 1)

_CHAR_PADDING = const(1)
_LINE_HEIGHT = const(32 + _CHAR_PADDING)

_CHARS_PER_SCREEN = const(_DISPLAY_WIDTH // 16)

_SCROLLBAR_WIDTH = const(3)
_SCROLLBAR_START_X = const(_DISPLAY_WIDTH - _SCROLLBAR_WIDTH)

_SCROLL_TIME = const(5000) # ms per one text scroll

_PATH_JOIN = const("|//|")

FILE_HANDLERS = {
    "":'.frozen/launcher/HyDE.py', # default
    "py":'.frozen/launcher/HyDE.py',
    "txt":'.frozen/launcher/HyDE.py',
    }



tft = st7789fbuf.ST7789(
    machine.SPI(
        1,baudrate=40000000,sck=machine.Pin(36),mosi=machine.Pin(35),miso=None),
    _DISPLAY_HEIGHT,
    _DISPLAY_WIDTH,
    reset=machine.Pin(33, machine.Pin.OUT),
    cs=machine.Pin(37, machine.Pin.OUT),
    dc=machine.Pin(34, machine.Pin.OUT),
    backlight=machine.Pin(38, machine.Pin.OUT),
    rotation=1,
    color_order=st7789fbuf.BGR
    )

config = mhconfig.Config()
kb = smartkeyboard.KeyBoard(config=config)
overlay = mhoverlay.UI_Overlay(config, kb, display_fbuf=tft)
beep = beeper.Beeper()

sd = None

# copied_file = None
clipboard = None

def mount_sd():
    global sd
    # sd needs to be mounted for any files in /sd
    try:
        if sd == None:
            sd = machine.SDCard(slot=2, sck=machine.Pin(40), miso=machine.Pin(39), mosi=machine.Pin(14), cs=machine.Pin(12))
        os.mount(sd, '/sd')
    except OSError:
        print("Could not mount SDCard!")

class ListView:
    def __init__(self, tft, config, items, dir_dict):
        self.tft = tft
        self.config = config
        self.items = items
        self.dir_dict = dir_dict
        self.view_index = 0
        self.cursor_index = 0
    
    def draw(self):
        tft = self.tft
        tft.fill(self.config["bg_color"])
        
        for idx in range(0, _ITEMS_PER_SCREEN):
            item_index = idx + self.view_index
            
            if item_index == self.cursor_index:
                # draw selection box
                tft.rect(
                    0, idx*_LINE_HEIGHT, _SCROLLBAR_START_X, 32, self.config.palette[0], fill=True
                    )
                # special styling on "add" button
                if self.items[item_index] == "/.../":
                    draw_hamburger_menu(104, idx*_LINE_HEIGHT, self.config.palette[5])
                    #tft.bitmap_text(font, "...", 96, idx*32, self.config.palette[5])
                else:
                    
                    if self.dir_dict[self.items[item_index]]:
                        mytext = "/" + self.items[item_index]
                        x = 0
                    else:
                        mytext = self.items[item_index]
                        x = 2
                    
                    # scroll text if too long
                    if len(mytext) > _CHARS_PER_SCREEN:
                        scroll_distance = (len(mytext) - _CHARS_PER_SCREEN) * -16
                        x = int(ping_pong_ease(time.ticks_ms(), _SCROLL_TIME) * scroll_distance)
                        
                    
                    #style based on directory or not
                    if self.dir_dict[self.items[item_index]]:
                        tft.bitmap_text(font, mytext, x, idx*_LINE_HEIGHT, self.config.palette[5])
                    else:
                        tft.bitmap_text(font, mytext, x, idx*_LINE_HEIGHT, self.config.palette[5])
                
            elif item_index < len(self.items):
                # special styling on "add" button
                if self.items[item_index] == "/.../":
                    draw_hamburger_menu(104, idx*_LINE_HEIGHT, self.config.palette[2])
                    #tft.bitmap_text(font, "...", 96, idx*32, self.config.palette[4])
                else:
                    #style based on directory or not
                    if self.dir_dict[self.items[item_index]]:
                        tft.bitmap_text(font, "/" + self.items[item_index], 0, idx*_LINE_HEIGHT, self.config.palette[3])
                    else:
                        tft.bitmap_text(font, self.items[item_index], 2, idx*_LINE_HEIGHT, self.config.palette[4])
        
        # draw scrollbar
        scrollbar_height = _DISPLAY_HEIGHT // max(1, (len(self.items) - _ITEMS_PER_SCREEN_MINUS))
        scrollbar_y = int((_DISPLAY_HEIGHT-scrollbar_height) * (self.view_index / max(len(self.items) - _ITEMS_PER_SCREEN, 1)))
        tft.rect(_SCROLLBAR_START_X, scrollbar_y, _SCROLLBAR_WIDTH, scrollbar_height, self.config.palette[2], fill=True)
    
    def clamp_cursor(self):
        self.cursor_index %= len(self.items)
        self.view_to_cursor()
    
    def view_to_cursor(self):
        if self.cursor_index < self.view_index:
            self.view_index = self.cursor_index
        if self.cursor_index >= self.view_index + _ITEMS_PER_SCREEN:
            self.view_index = self.cursor_index - _ITEMS_PER_SCREEN + 1

    def up(self):
        self.cursor_index = (self.cursor_index - 1) % len(self.items)
        self.view_to_cursor()
            
    def down(self):
        self.cursor_index = (self.cursor_index + 1) % len(self.items)
        self.view_to_cursor()
     
def draw_hamburger_menu(x,y,color):
    # draw 32x32 hamburger menu icon
    _WIDTH=const(32)
    _HEIGHT=const(2)
    _PADDING=const(10)
    _OFFSET=const(6)
    
    tft.rect(x,y+_PADDING,_WIDTH,_HEIGHT,color)
    tft.rect(x,y+_PADDING+_OFFSET,_WIDTH,_HEIGHT,color)
    tft.rect(x,y+_PADDING+_OFFSET+_OFFSET,_WIDTH,_HEIGHT,color)
         
def ease_in_out_sine(x):
    return -(math.cos(math.pi * x) - 1) / 2

def ping_pong_ease(value,maximum):
    odd_pong = ((value // maximum) % 2 == 1)
    
    fac = ease_in_out_sine((value % maximum) / maximum)

    if odd_pong:
        return 1 - (fac)
    else:
        return (fac)

def parse_files():
    """Parse result of os.ilistdir() into a sorted list, and a dictionary with directory information."""
    dirdict = {}
    dirlist = []
    filelist = []
    #add directories to the top
    for ilist in os.ilistdir():
        name = ilist[0]; itype = ilist[1]
        if itype == 0x4000:
            dirlist.append(name)
            dirdict[name] = True
        else:
            filelist.append(name)
            dirdict[name] = False
    dirlist.sort()
    filelist.sort()
    # append special option to view for adding new files
    filelist.append("/.../")
    
    return (dirlist + filelist, dirdict)

def ext_options(overlay):
    """Create popup with options for new file or directory."""
    cwd = os.getcwd()
    
    options = ["Paste", "New Directory", "New File", "Refresh", "Exit to launcher"]
    
    if clipboard == None:
        # dont give the paste option if there's nothing to paste.
        options.pop(0)
    
    option = overlay.popup_options(options, title=f"{cwd}:")
    if option == "New Directory":
        play_sound(("D3"), 30)
        name = overlay.text_entry(title="Directory name:", blackout_bg=True)
        play_sound(("G3"), 30)
        try:
            os.mkdir(name)
        except Exception as e:
            overlay.error(e)
            
    elif option == "New File":
        play_sound(("B3"), 30)
        name = overlay.text_entry(title="File name:", blackout_bg=True)
        play_sound(("G3"), 30)
        try:
            with open(name, "w") as newfile:
                newfile.write("")
        except Exception as e:
            overlay.error(e)
            
    elif option == "Refresh":
        play_sound(("B3","G3","D3"), 30)
        mount_sd()
        os.sync()
        
    elif option == "Paste":
        play_sound(("D3","G3","D3"), 30)
        
        source_path, file_name = clipboard
        
        source = f"{source_path}/{file_name}".replace('//','/')
        dest = f"{cwd}/{file_name}".replace('//','/')
        
        with open(source,"rb") as old_file:
            with open(dest, "wb") as new_file:
                while True:
                    l = old_file.read(512)
                    if not l: break
                    new_file.write(l)
    
    elif option == "Exit to launcher":
        overlay.draw_textbox("Exiting...", _DISPLAY_WIDTH//2, _DISPLAY_HEIGHT//2)
        tft.show()
        rtc = machine.RTC()
        rtc.memory('')
        machine.reset()

def file_options(file, overlay):
    """Create popup with file options for given file."""
    global clipboard
    
    options = ("open", "copy", "rename", "delete")
    option = overlay.popup_options(options, title=f'"{file}":')
    
    if option == "open":
        play_sound(("G3"), 30)
        open_file(file)
    elif option == "copy":
        # store copied file to clipboard
        clipboard = (os.getcwd(), file)
#         new_name = overlay.text_entry(start_value=file, title=f"Rename '{file}':", blackout_bg=True)
        play_sound(("D3","G3","D3"), 30)
#         with open(file,"rb") as source:
#             with open(new_name, "wb") as dest:
#                 while True:
#                     l = source.read(512)
#                     if not l: break
#                     dest.write(l)
        
    elif option == "rename":
        play_sound(("B3"), 30)
        new_name = overlay.text_entry(start_value=file, title=f"Rename '{file}':", blackout_bg=True)
        os.rename(file,new_name)
        
    elif option == "delete":
        play_sound(("D3"), 30)
        confirm = overlay.popup_options(("cancel", "confirm"), title=f'Delete "{file}"?', extended_border=True)
        if confirm == "confirm":
            play_sound(("D3","B3","G3","G3"), 30)
            os.remove(file)


def open_file(file):
    cwd = os.getcwd()
    if not cwd.endswith("/"): cwd += "/"
    filepath = cwd + file
    
    # visual feedback
    overlay.draw_textbox("Opening...", _DISPLAY_WIDTH//2, _DISPLAY_HEIGHT//4)
    overlay.draw_textbox(filepath, _DISPLAY_WIDTH//2, _DISPLAY_HEIGHT//2)
    tft.show()
    
    filetype = file.split(".")[-1]
    if filetype not in FILE_HANDLERS.keys():
        filetype = ""
    handler = FILE_HANDLERS[filetype]
    
    full_path = handler + _PATH_JOIN + filepath
    
    # write path to RTC memory
    rtc = machine.RTC()
    rtc.memory(full_path)
    time.sleep_ms(10)
    machine.reset()
    
def play_sound(notes, time_ms=30):
    if config['ui_sound']:
        beep.play(notes, time_ms, config['volume'])

def main_loop(tft, kb, config, overlay):
    
    new_keys = kb.get_new_keys()
    mount_sd()
    file_list, dir_dict = parse_files()
    
    view = ListView(tft, config, file_list, dir_dict)
    
    while True:
        new_keys = kb.get_new_keys()
        for key in new_keys:
            if key == ";":
                view.up()
                play_sound(("G3","B3"), 30)
            elif key == ".":
                view.down()
                play_sound(("D3","B3"), 30)
            elif key == "ENT" or key == "SPC":
                play_sound(("G3","B3","D3"), 30)
                selection_name = file_list[view.cursor_index]
                if selection_name == "/.../": # new file
                    ext_options(overlay)
                    file_list, dir_dict = parse_files()
                    view.items = file_list
                    view.dir_dict = dir_dict
                    view.clamp_cursor()
                else:
                    if dir_dict[selection_name] == True:
                        # this is a directory, open it
                        os.chdir(selection_name)
                        file_list, dir_dict = parse_files()
                        view.items = file_list
                        view.dir_dict = dir_dict
                        view.cursor_index = 0
                        view.view_index = 0
                    else:
                        # this is a file, give file options
                        file_options(file_list[view.cursor_index], overlay)
                        file_list, dir_dict = parse_files()
                        view.items = file_list
                        view.dir_dict = dir_dict
                        view.clamp_cursor()
                        
            elif key ==  "BSPC" or key == "`":
                play_sound(("D3","B3","G3"), 30)
                # previous directory
                if os.getcwd() == "/sd":
                    os.chdir("/")
                else:
                    os.chdir("..")
                file_list, dir_dict = parse_files()
                view.items = file_list
                view.dir_dict = dir_dict
                view.cursor_index = 0
                view.view_index = 0
                
            elif key == "GO":
                    ext_options(overlay)
                    file_list, dir_dict = parse_files()
                    view.items = file_list
                    view.dir_dict = dir_dict
                    view.clamp_cursor()
        
        view.draw()
        tft.show()
        
        time.sleep_ms(10)
    
    
main_loop(tft, kb, config, overlay)
