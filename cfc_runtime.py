"""Siemens CFC style soft-PLC runtime.

Logic is defined as CFC blocks; I/O is exchanged with an Arduino on COM5.
Protocol (text, newline terminated):
  Arduino -> PC : "I0=0,I1=1,..."
  PC -> Arduino : "O0=1,O1=0,..."
"""
import serial, time

PORT = "COM5"
BAUD = 115200


class Block:
    def __init__(self, name):
        self.name = name
        self.out = {}

    def step(self, inputs):
        raise NotImplementedError


class AND(Block):
    def __init__(self, name):
        super().__init__(name)
        self.out = {"OUT": False}

    def step(self, inputs):
        self.out["OUT"] = bool(inputs.get("IN1")) and bool(inputs.get("IN2"))


class OR(Block):
    def __init__(self, name):
        super().__init__(name)
        self.out = {"OUT": False}

    def step(self, inputs):
        self.out["OUT"] = bool(inputs.get("IN1")) or bool(inputs.get("IN2"))


class NOT(Block):
    def __init__(self, name):
        super().__init__(name)
        self.out = {"OUT": False}

    def step(self, inputs):
        self.out["OUT"] = not bool(inputs.get("IN"))


class TON(Block):
    def __init__(self, name, pt=1.0):
        super().__init__(name)
        self.pt = pt
        self.out = {"Q": False, "ET": 0.0}
        self._start = None

    def step(self, inputs):
        now = time.time()
        if inputs.get("IN"):
            if self._start is None:
                self._start = now
            et = now - self._start
            self.out["ET"] = et
            self.out["Q"] = et >= self.pt
        else:
            self._start = None
            self.out["Q"] = False
            self.out["ET"] = 0.0


def parse_inputs(line):
    res = {}
    for part in line.strip().split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            res[k.strip()] = v.strip() in ("1", "true", "True", "HIGH")
    return res


def format_outputs(outs):
    return ",".join(f"{k}={1 if v else 0}" for k, v in outs.items()) + "\n"


def main():
    # Example CFC network: OUT0 = NOT(IN0 AND IN1) OR TON(IN2)
    and1 = AND("AND1")
    not1 = NOT("NOT1")
    ton1 = TON("TON1", pt=2.0)
    or1 = OR("OR1")

    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    print("CFC runtime on", PORT)

    try:
        while True:
            line = ser.readline().decode(errors="ignore")
            if not line:
                continue
            ins = parse_inputs(line)
            and1.step({"IN1": ins.get("I0", False), "IN2": ins.get("I1", False)})
            not1.step({"IN": and1.out["OUT"]})
            ton1.step({"IN": ins.get("I2", False)})
            or1.step({"IN1": not1.out["OUT"], "IN2": ton1.out["Q"]})

            outs = {"O0": or1.out["OUT"], "O1": ton1.out["Q"]}
            ser.write(format_outputs(outs).encode())
            print("IN", ins, "-> OUT", outs)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()
