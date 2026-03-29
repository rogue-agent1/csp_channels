#!/usr/bin/env python3
"""CSP-style channels (Go-like) with select, fan-in/fan-out."""
import sys, threading, queue, time, random

class Channel:
    def __init__(self, capacity=0):
        self._queue = queue.Queue(maxsize=capacity if capacity > 0 else 1)
        self._closed = False; self._unbuffered = capacity == 0

    def send(self, value):
        if self._closed: raise RuntimeError("send on closed channel")
        self._queue.put(value)

    def recv(self, timeout=None):
        try: return self._queue.get(timeout=timeout), True
        except queue.Empty:
            if self._closed: return None, False
            raise

    def close(self): self._closed = True

    def __iter__(self):
        while True:
            try:
                val, ok = self.recv(timeout=0.5)
                if not ok: break
                yield val
            except queue.Empty:
                if self._closed: break

def select(*cases, default=None):
    """Non-blocking select over multiple channels."""
    for ch, direction in cases:
        if direction == "recv":
            try:
                val = ch._queue.get_nowait()
                return ch, val
            except queue.Empty: continue
    if default is not None: return None, default
    while True:
        for ch, direction in cases:
            if direction == "recv":
                try:
                    val = ch._queue.get(timeout=0.05)
                    return ch, val
                except queue.Empty: continue

def fan_out(source, n):
    channels = [Channel(10) for _ in range(n)]
    def distribute():
        i = 0
        for val in source:
            channels[i % n].send(val); i += 1
        for ch in channels: ch.close()
    threading.Thread(target=distribute, daemon=True).start()
    return channels

def fan_in(*channels):
    out = Channel(10)
    count = [len(channels)]
    def merge(ch):
        for val in ch: out.send(val)
        count[0] -= 1
        if count[0] == 0: out.close()
    for ch in channels:
        threading.Thread(target=merge, args=(ch,), daemon=True).start()
    return out

def main():
    print("=== CSP Channels Demo ===\n")
    print("Basic send/recv:")
    ch = Channel(5)
    for i in range(5): ch.send(i)
    for i in range(5):
        val, _ = ch.recv()
        print(f"  recv: {val}")

    print("\nProducer-Consumer:")
    ch = Channel(3)
    def producer():
        for i in range(8): ch.send(i); time.sleep(0.02)
        ch.close()
    def consumer(name):
        for val in ch: print(f"  {name} got {val}")
    threading.Thread(target=producer, daemon=True).start()
    threads = [threading.Thread(target=consumer, args=(f"C{i}",), daemon=True) for i in range(2)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=3)

    print("\nFan-out/Fan-in pipeline:")
    source = Channel(20)
    def feed():
        for i in range(12): source.send(i)
        source.close()
    threading.Thread(target=feed, daemon=True).start()
    workers = fan_out(source, 3)
    processed = []
    def work(ch_in, ch_out):
        for val in ch_in: ch_out.send(val * val); time.sleep(0.01)
        ch_out.close()
    out_channels = []
    for w in workers:
        out = Channel(10); out_channels.append(out)
        threading.Thread(target=work, args=(w, out), daemon=True).start()
    merged = fan_in(*out_channels)
    results = list(merged)
    print(f"  Input: 0-11, Squared output: {sorted(results)}")

if __name__ == "__main__": main()
