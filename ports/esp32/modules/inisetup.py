import vfs
from flashbdev import bdev


def check_bootsec():
    buf = bytearray(bdev.ioctl(5, 0))  # 5 is SEC_SIZE
    bdev.readblocks(0, buf)
    empty = True
    for b in buf:
        if b != 0xFF:
            empty = False
            break
    if empty:
        return True
    fs_corrupted()


def fs_corrupted():
    import time
    import micropython

    # Allow this loop to be stopped via Ctrl-C.
    micropython.kbd_intr(3)

    while 1:
        print(
            """\
The filesystem appears to be corrupted. If you had important data there, you
may want to make a flash snapshot to try to recover it. Otherwise, perform
factory reprogramming of MicroPython firmware (completely erase flash, followed
by firmware programming).
"""
        )
        time.sleep(3)


def setup():
    check_bootsec()
    print("Performing initial setup")
    if bdev.info()[4] == "vfs":
        vfs.VfsLfs2.mkfs(bdev)
        fs = vfs.VfsLfs2(bdev)
    elif bdev.info()[4] == "ffat":
        vfs.VfsFat.mkfs(bdev)
        fs = vfs.VfsFat(bdev)
    vfs.mount(fs, "/")
    with open("readme.md", "w") as f:
        f.write(
            """\
## Welcome to MicroHydra!

MicroHydra is an experimental app switcher for MicroPython, which also provides some os-like features, and a framework for easily making simple apps.

### Useful Links

To find various MicroHydra-compatible apps shared by the community, see the apps repo here:  
https://github.com/echo-lalia/MicroHydra-Apps

MicroHydra, and its apps, are built using MicroPython.   
For information on the modules and features built into MicroPython, see the MicroPython docs:  
https://docs.micropython.org/en/latest/

To learn more about built-in MicroHydra modules, or to learn more about making your own apps, see the wiki:  
https://github.com/echo-lalia/MicroHydra/wiki

If you encounter any issues, or have any feature suggestions to share, raise an issue on the GitHub page:  
https://github.com/echo-lalia/MicroHydra/issues

And finally, if you'd like to talk to other MicroHydra users or developers, MH now has its own Discord:  
https://discord.gg/6e4KUDpgQC

"""
        )
    return fs
