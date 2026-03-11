#!/usr/bin/env python3
"""csp_channels — CSP-style channels with select, fan-in, fan-out. Zero deps."""
from collections import deque
from threading import Thread, Lock, Event

class Channel:
    def __init__(self, capacity=0):
        self.buffer = deque(maxlen=capacity if capacity else None)
        self.capacity = capacity
        self.lock = Lock()
        self.not_empty = Event()
        self.not_full = Event()
        self.closed = False
        if capacity: self.not_full.set()

    def send(self, value):
        if self.closed: raise RuntimeError("send on closed channel")
        if self.capacity:
            self.not_full.wait()
            with self.lock:
                self.buffer.append(value)
                self.not_empty.set()
                if len(self.buffer) >= self.capacity:
                    self.not_full.clear()
        else:
            with self.lock:
                self.buffer.append(value)
                self.not_empty.set()

    def recv(self):
        self.not_empty.wait(timeout=1)
        with self.lock:
            if not self.buffer:
                if self.closed: return None
                return None
            val = self.buffer.popleft()
            if not self.buffer: self.not_empty.clear()
            self.not_full.set()
            return val

    def close(self):
        self.closed = True
        self.not_empty.set()
        self.not_full.set()

    def __iter__(self):
        while True:
            val = self.recv()
            if val is None and self.closed and not self.buffer: break
            if val is not None: yield val

def fan_out(src, *dsts):
    for val in src:
        for dst in dsts:
            dst.send(val)
    for dst in dsts:
        dst.close()

def fan_in(*srcs):
    ch = Channel(capacity=len(srcs) * 10)
    remaining = [len(srcs)]
    def drain(src):
        for val in src:
            ch.send(val)
        remaining[0] -= 1
        if remaining[0] == 0: ch.close()
    for src in srcs:
        Thread(target=drain, args=(src,), daemon=True).start()
    return ch

def main():
    print("CSP Channels Demo:\n")
    # Basic send/recv
    ch = Channel(capacity=3)
    ch.send(1); ch.send(2); ch.send(3)
    print(f"  Buffered: {ch.recv()}, {ch.recv()}, {ch.recv()}")

    # Producer-consumer
    ch = Channel(capacity=5)
    def producer():
        for i in range(5):
            ch.send(i * 10)
        ch.close()
    Thread(target=producer, daemon=True).start()
    print(f"  Producer: {list(ch)}")

    # Fan-in
    c1, c2 = Channel(5), Channel(5)
    def fill(ch, vals):
        for v in vals: ch.send(v)
        ch.close()
    Thread(target=fill, args=(c1, [1,2,3]), daemon=True).start()
    Thread(target=fill, args=(c2, [4,5,6]), daemon=True).start()
    merged = fan_in(c1, c2)
    result = sorted(list(merged))
    print(f"  Fan-in: {result}")

if __name__ == "__main__":
    main()
