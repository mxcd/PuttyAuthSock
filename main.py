import wx
from wx import adv
import os
import os.path
import subprocess
import time
import sys
from pathlib import Path

base_dir = "./"

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS + "/files/"

TRAY_TOOLTIP = 'PuttyAuthSock'
TRAY_ICON_INACTIVE = os.path.join(base_dir, 'icon.png')
TRAY_ICON_ACTIVE = os.path.join(base_dir, 'icon_green.png')

PLINK_CMD = 'plink.exe -ssh -A -batch -i {} {}@{} ' \
            '"rm -rf ~/.auth_sock || 0; ln -s \"$SSH_AUTH_SOCK\" \"~/.auth_sock\"; sleep infinity&; echo $!;"'

# Thanks a lot to FogleBird for getting me started on wxpython
# https://stackoverflow.com/a/6389727/891624



def subprocess_args(include_stdout=True):
    if hasattr(subprocess, 'STARTUPINFO'):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        env = os.environ
    else:
        si = None
        env = None

    if include_stdout:
        ret = {'stdout': subprocess.PIPE}
    else:
        ret = {}

    ret.update({'stdin': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'startupinfo': si,
                'env': env })
    return ret


def create_menu_item(menu, label, func):
    item = wx.MenuItem(menu, -1, label)
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)
    return item


class TaskBarIcon(adv.TaskBarIcon):
    def __init__(self):
        super(TaskBarIcon, self).__init__()
        self.set_icon(TRAY_ICON_INACTIVE)
        self.active = False
        self.auth_sock_pid = None
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        # create_menu_item(menu, 'Say Hello', self.on_hello)
        # menu.AppendSeparator()
        create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def set_icon(self, path):
        icon = wx.Icon()
        icon.LoadFile(path)
        self.SetIcon(icon, TRAY_TOOLTIP)

    def on_left_down(self, event):
        if not self.active:
            self.init_auth_sock()
        else:
            self.kill_auth_sock()

    def init_auth_sock(self):
        print("Starting auth_sock")
        self.run_auth_sock()
        self.active = True
        self.set_icon(TRAY_ICON_ACTIVE)

    def run_auth_sock(self):
        ip = get_wsl_ip()
        user = get_wsl_username()
        ppk_file = get_ppk_file()
        print("Starting agent forwarding")
        process = subprocess.Popen(PLINK_CMD.format(ppk_file, user, ip), **subprocess_args(True))
        time.sleep(1)
        self.auth_sock_pid = int(process.stdout.readline().strip())

    def kill_auth_sock(self):
        print("Killing auth sock")
        kill_pid(self.auth_sock_pid)
        print("Removing auth_sock file")
        remove_auth_sock()
        self.active = False
        self.set_icon(TRAY_ICON_INACTIVE)

    def on_exit(self, event):
        if self.active:
            self.kill_auth_sock()
        wx.CallAfter(self.Destroy)


def main():
    app = wx.App()
    TaskBarIcon()
    app.MainLoop()


def get_ppk_file():
    home = str(Path.home())
    putty_auth_sock_dir = os.path.join(home, ".ssh")
    ppk_file = os.path.join(putty_auth_sock_dir, "putty_auth_sock.ppk")
    return ppk_file


def get_wsl_ip():
    # we need to read WSL's IP address every time it has been started since it is not static
    ip_cmd = "ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'"
    ip = subprocess.check_output(['bash', '-c', '{}'.format(ip_cmd)], **subprocess_args(False)).decode('ascii')
    return ip.strip()


def start_wsl_ssh():
    subprocess.check_output(['wsl', '-u', 'root', '--', 'service', 'ssh', 'start'], **subprocess_args(False))


def get_wsl_username():
    username = subprocess.check_output(['bash', '-c', '"whoami"'], **subprocess_args(False)).decode('ascii')
    return username.strip()


def remove_auth_sock():
    subprocess.check_output(['wsl', '--', 'rm', '-rf', '~/.auth_sock'], **subprocess_args(False))


def kill_pid(pid):
    subprocess.check_output(['wsl', '--', 'kill',  '{}'.format(pid)], **subprocess_args(False))


if __name__ == '__main__':
    start_wsl_ssh()
    main()