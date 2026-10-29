"""Terminals over a WebSocket: a pty running a command, bridged to xterm.js in the page.

Minimal RFC 6455 server side (no extensions): browser frames are masked; text frames carry JSON control
({"t": "in", "d": "..."} or {"t": "resize", "cols": C, "rows": R}); the pty's output goes out as binary frames.
"""
import base64
import fcntl
import hashlib
import json
import os
import pty
import select
import signal
import struct
import termios
import threading
import time

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def send_frame(sock, payload, opcode=0x2):
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([n])
    elif n < 1 << 16:
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    sock.sendall(head + payload)


def recv_exact(rfile, n):
    data = b""
    while len(data) < n:
        chunk = rfile.read(n - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return data


def recv_frame(rfile):
    """(opcode, payload) of the next complete message (continuation frames joined)."""
    msg, op = b"", None
    while True:
        b1, b2 = recv_exact(rfile, 2)
        fin, opcode = b1 & 0x80, b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", recv_exact(rfile, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", recv_exact(rfile, 8))[0]
        mask = recv_exact(rfile, 4) if b2 & 0x80 else None
        data = recv_exact(rfile, n)
        if mask:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode >= 0x8:                      # control frames may interleave
            return opcode, data
        if opcode:
            op = opcode
        msg += data
        if fin:
            return op, msg


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(2, rows), max(2, cols), 0, 0))


def serve(handler, argv, cwd, env, on_close_bytes=b""):
    """Run argv in a pty and bridge it to the WebSocket on handler's connection until either side ends."""
    sock, rfile = handler.connection, handler.rfile
    pid, fd = pty.fork()
    if pid == 0:                                # child
        try:
            os.chdir(cwd)
        except OSError:
            pass
        os.execvpe(argv[0], argv, env)
    set_size(fd, 100, 30)
    lock, alive = threading.Lock(), [True]

    def pump():                                 # pty -> socket
        try:
            while alive[0]:
                r, _, _ = select.select([fd], [], [], 0.5)
                if not r:
                    continue
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                with lock:
                    send_frame(sock, data)
        except OSError:
            pass
        finally:
            alive[0] = False
            try:
                with lock:
                    send_frame(sock, b"", 0x8)
            except OSError:
                pass

    threading.Thread(target=pump, daemon=True).start()
    try:
        while alive[0]:
            op, data = recv_frame(rfile)
            if op == 0x8:
                break
            if op == 0x9:
                with lock:
                    send_frame(sock, data, 0xA)
                continue
            if op == 0x1:
                msg = json.loads(data)
                if msg.get("t") == "in":
                    os.write(fd, msg.get("d", "").encode())
                elif msg.get("t") == "resize":
                    set_size(fd, int(msg.get("cols", 100)), int(msg.get("rows", 30)))
            elif op == 0x2:
                os.write(fd, data)
    except (EOFError, OSError, ValueError):
        pass
    finally:
        alive[0] = False
        try:
            if on_close_bytes:                  # e.g. herdr's detach keys, so the agent keeps running
                os.write(fd, on_close_bytes)
                time.sleep(0.4)
        except OSError:
            pass
        for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
            try:
                if os.waitpid(pid, os.WNOHANG) != (0, 0):
                    break
                os.kill(pid, sig)
                time.sleep(0.3)
            except (ChildProcessError, ProcessLookupError):
                break
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        os.close(fd)
