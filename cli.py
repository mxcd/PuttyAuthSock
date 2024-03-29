import os
import os.path
import subprocess
import time
import sys
from pathlib import Path
import winreg
import kh2reg
import signal
from threading import Event

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

active = False
auth_sock_pid = None


def on_exit(a, b):
    if active:
        kill_auth_sock()
    exit(0)


def init_auth_sock():
    global active
    print("Starting auth_sock")
    run_auth_sock()
    active = True


def run_auth_sock():
    global auth_sock_pid
    ip = get_wsl_ip()
    user = get_wsl_username()
    ppk_file = get_ppk_file()
    print("Starting agent forwarding")
    process = subprocess.Popen(PLINK_CMD.format(ppk_file, user, ip), **subprocess_args(True))
    time.sleep(1)
    auth_sock_pid = int(process.stdout.readline().strip())


def kill_auth_sock():
    global active, auth_sock_pid
    print("Killing auth sock")
    kill_pid(auth_sock_pid)
    print("Removing auth_sock file")
    remove_auth_sock()
    active = False


def get_ssh_dir():
    home = str(Path.home())
    ssh_dir = os.path.join(home, ".ssh")
    return ssh_dir


def get_ppk_file():
    ppk_file = os.path.join(get_ssh_dir(), "putty_auth_sock.ppk")
    return ppk_file


def get_wsl_ip():
    # we need to read WSL's IP address every time it has been started since it is not static
    ip_cmd = "ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'"
    ip = subprocess.check_output(['bash', '-c', '{}'.format(ip_cmd)], **subprocess_args(False)).decode('ascii')
    print("Using IP address {}".format(ip))
    return ip.strip()


def start_wsl_ssh():
    subprocess.check_output(['wsl', '-u', 'root', '--', 'service', 'ssh', 'start'], **subprocess_args(False))


def register_known_host():
    known_host_entry = obtain_wsl_known_host_entry()
    add_putty_reg_key(known_host_entry)


def obtain_wsl_known_host_entry():
    fingerprints = subprocess.check_output(['ssh-keyscan', get_wsl_ip()], **subprocess_args(False)).decode()
    fingerprints = fingerprints.split("\n")
    for fingerprint in fingerprints:
        if 'ssh-ed25519' in fingerprint:
            return fingerprint
    print("Error: unable to obtain ssh-rsa fingerprint")


def update_known_hosts(known_host_entry):
    known_hosts_file = os.path.join(get_ssh_dir(), "known_hosts")
    with open(known_hosts_file, 'r') as f:
        known_hosts = f.read().split("\n")

    os.remove(known_hosts_file)

    # Filter out eventually outdated known_host lines that match the fingerprint
    # known_host_entry is of format "<IP> <format> <fingerprint>"
    fingerprint = known_host_entry.split(" ")[2].strip()
    known_hosts = [known_host for known_host in known_hosts if fingerprint not in known_host]
    known_hosts.append(known_host_entry)

    with open(known_hosts_file, 'w') as f:
        f.write("\n".join([known_host.strip() for known_host in known_hosts]))


def get_wsl_username():
    username = subprocess.check_output(['bash', '-c', '"whoami"'], **subprocess_args(False)).decode('ascii')
    print("Using username {}".format(username))
    return username.strip()


def remove_auth_sock():
    subprocess.check_output(['wsl', '--', 'rm', '-rf', '~/.auth_sock'], **subprocess_args(False))


def kill_pid(pid):
    subprocess.check_output(['wsl', '--', 'kill',  '{}'.format(pid)], **subprocess_args(False))


# Adds the known_host_entry to the registry
# https://git.tartarus.org/?p=simon/putty.git;a=blob;f=contrib/kh2reg.py;hb=HEAD
def add_putty_reg_key(known_host_entry):
    regkey, regval = kh2reg.handle_line(known_host_entry)
    print(regkey)
    print(regval)
    handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\SimonTatham\PuTTY\SshHostKeys', 0, winreg.KEY_ALL_ACCESS)
    winreg.SetValueEx(handle, regkey, 0, winreg.REG_SZ, regval)
    winreg.CloseKey(handle)


if __name__ == '__main__':
    start_wsl_ssh()
    register_known_host()
    run_auth_sock()

    signal.signal(signal.SIGINT, on_exit)
    print('Running')
    while True:
        time.sleep(1)

