#!/usr/bin/env python3
"""Тестовый стенд AIsktagOS: QEMU с «железом» VMware (SVGA II, vmxnet3, pvscsi) + QMP.

  vm.py start <name> <bios|uefi|secureboot> <iso> [disk]
  vm.py shot <name> <out.png>
  vm.py keys <name> <key> [key...]      например: ret, tab, down, ctrl-alt-t
  vm.py type <name> <text>
  vm.py stop <name>
"""
import json
import os
import socket
import subprocess
import sys
import time

BASE = os.environ.get("VM_DIR", "/var/tmp/aisktagos-vm")
OVMF = "/usr/share/OVMF"


def sock(name):
    return f"{BASE}/{name}.qmp"


def qmp(name, cmd, **args):
    s = socket.socket(socket.AF_UNIX)
    s.connect(sock(name))
    f = s.makefile("rw")
    f.readline()
    f.write(json.dumps({"execute": "qmp_capabilities"}) + "\n"); f.flush(); f.readline()
    f.write(json.dumps({"execute": cmd, "arguments": args}) + "\n"); f.flush()
    while True:
        r = json.loads(f.readline())
        if "return" in r or "error" in r:
            s.close()
            return r


def start(name, mode, iso, disk=None):
    os.makedirs(BASE, exist_ok=True)
    argv = ["qemu-system-x86_64", "-name", name, "-m", "6144", "-smp", "4",
            "-accel", "tcg,thread=multi", "-cpu", "max",
            "-vga", os.environ.get("VGA", "vmware"),
            "-netdev", "user,id=n0", "-device", "vmxnet3,netdev=n0",
            "-device", "pvscsi,id=scsi0",
            "-display", "none", "-qmp", f"unix:{sock(name)},server,nowait",
            "-serial", f"unix:{BASE}/{name}.tty,server,nowait", "-monitor", "none",
            "-usb", "-device", "usb-tablet"]
    if mode == "bios":
        argv += ["-machine", "pc"]
    else:
        vars_src = f"{OVMF}/OVMF_VARS_4M.ms.fd" if mode == "secureboot" else f"{OVMF}/OVMF_VARS_4M.fd"
        code = f"{OVMF}/OVMF_CODE_4M.secboot.fd" if mode == "secureboot" else f"{OVMF}/OVMF_CODE_4M.fd"
        vars_dst = f"{BASE}/{name}.vars.fd"
        if not os.path.exists(vars_dst):
            subprocess.run(["cp", vars_src, vars_dst], check=True)
        argv += ["-machine", "q35,smm=on" if mode == "secureboot" else "q35",
                 "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
                 "-drive", f"if=pflash,format=raw,unit=1,file={vars_dst}"]
        if mode == "secureboot":
            argv += ["-global", "driver=cfi.pflash01,property=secure,value=on"]
    if os.environ.get("APPEND"):
        casper = os.environ.get("CASPER_DIR", "/var/tmp/aisktagos-work/iso/casper")
        argv += ["-kernel", f"{casper}/vmlinuz", "-initrd", f"{casper}/initrd",
                 "-append", os.environ["APPEND"]]
    if iso:
        argv += ["-drive", f"file={iso},media=cdrom,readonly=on,if=none,id=cd0",
                 "-device", "ide-cd,drive=cd0,bootindex=1" if mode == "bios" else "ide-cd,drive=cd0,bootindex=1"]
    if disk:
        argv += ["-drive", f"file={disk},if=none,id=d0,format=qcow2",
                 "-device", "scsi-hd,drive=d0,bus=scsi0.0,bootindex=2"]
    log = open(f"{BASE}/{name}.log", "w")
    p = subprocess.Popen(argv, stdout=log, stderr=log, start_new_session=True)
    open(f"{BASE}/{name}.pid", "w").write(str(p.pid))
    time.sleep(2)
    subprocess.Popen([sys.executable, __file__, "serlog", name], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("started", p.pid)


def serlog(name):
    """Пишет вывод последовательного порта в .serial и отправляет в гостя строки из .in."""
    import select
    s = socket.socket(socket.AF_UNIX)
    for _ in range(50):
        try:
            s.connect(f"{BASE}/{name}.tty")
            break
        except OSError:
            time.sleep(0.2)
    fifo = f"{BASE}/{name}.in"
    if not os.path.exists(fifo):
        os.mkfifo(fifo)
    fin = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    out = open(f"{BASE}/{name}.serial", "ab", buffering=0)
    while True:
        r, _, _ = select.select([s, fin], [], [])
        if s in r:
            data = s.recv(65536)
            if not data:
                return
            out.write(data)
        if fin in r:
            s.sendall(os.read(fin, 65536))


def main():
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "start":
        start(name, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None,
              sys.argv[5] if len(sys.argv) > 5 else None)
    elif cmd == "serlog":
        serlog(name)
    elif cmd == "sh":
        # vm.py sh <name> "<команда>" — ввести строку в консоль ttyS0
        with open(f"{BASE}/{name}.in", "w") as f:
            f.write(" ".join(sys.argv[3:]) + "\n")
    elif cmd == "shot":
        out = sys.argv[3]
        r = qmp(name, "screendump", filename=out, format="png")
        print(r)
    elif cmd == "keys":
        for k in sys.argv[3:]:
            keys = [{"type": "qcode", "data": x} for x in k.split("-")]
            qmp(name, "send-key", keys=keys)
            time.sleep(0.4)
    elif cmd == "type":
        text = " ".join(sys.argv[3:])
        m = {" ": "spc", "-": "minus", ".": "dot", "/": "slash", "_": "shift-minus", "@": "shift-2"}
        for ch in text:
            code = m.get(ch)
            if code is None:
                code = ("shift-" + ch.lower()) if ch.isupper() else ch
            qmp(name, "send-key", keys=[{"type": "qcode", "data": x} for x in code.split("-")])
            time.sleep(0.15)
    elif cmd == "click":
        # vm.py click <name> x y [double] [W H] — координаты в пикселях экрана
        x, y = int(sys.argv[3]), int(sys.argv[4])
        double = len(sys.argv) > 5 and sys.argv[5] == "double"
        w = int(os.environ.get("W", 1280)); h = int(os.environ.get("H", 800))
        ax, ay = x * 32767 // w, y * 32767 // h
        qmp(name, "input-send-event", events=[
            {"type": "abs", "data": {"axis": "x", "value": ax}},
            {"type": "abs", "data": {"axis": "y", "value": ay}}])
        time.sleep(0.2)
        for _ in range(2 if double else 1):
            qmp(name, "input-send-event", events=[{"type": "btn", "data": {"down": True, "button": "left"}}])
            time.sleep(0.05)
            qmp(name, "input-send-event", events=[{"type": "btn", "data": {"down": False, "button": "left"}}])
            time.sleep(0.1)
    elif cmd == "stop":
        try:
            qmp(name, "quit")
        except OSError:
            pass
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
