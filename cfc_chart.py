"""Siemens SIMATIC style Continuous Function Chart (CFC) renderer.

Draws function blocks with pins, wiring (incl. feedback loops) and labels.
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


BLOCKS = {
    "AND": (1.8, 1.0, ["IN1", "IN2"], ["OUT"]),
    "OR": (1.8, 1.0, ["IN1", "IN2"], ["OUT"]),
    "NOT": (1.6, 0.9, ["IN"], ["OUT"]),
    "RS": (1.8, 1.2, ["S", "R1"], ["Q", "Q1"]),
    "TON": (2.0, 1.3, ["IN", "PT"], ["Q", "ET"]),
    "CTU": (2.0, 1.3, ["CU", "R", "PV"], ["Q", "CV"]),
    "ADD": (1.8, 1.1, ["IN1", "IN2"], ["OUT"]),
    "MOVE": (1.6, 0.9, ["IN"], ["OUT"]),
    "CMP>": (1.8, 1.0, ["IN1", "IN2"], ["OUT"]),
}


def pin_y(y, h, i, n):
    return y + h * (i + 1) / (n + 1)


def draw_block(ax, x, y, name):
    w, h, ins, outs = BLOCKS[name]
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                         edgecolor="#1f3864", facecolor="#dbeafe", linewidth=1.6)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h + 0.08, name, ha="center", va="bottom",
            fontsize=10, fontweight="bold", color="#1f3864")
    for i, p in enumerate(ins):
        py = pin_y(y, h, i, len(ins))
        ax.plot(x, py, "o", color="#1f3864", markersize=4)
        ax.text(x - 0.06, py, p, ha="right", va="center", fontsize=8)
    for i, p in enumerate(outs):
        py = pin_y(y, h, i, len(outs))
        ax.plot(x + w, py, "o", color="#1f3864", markersize=4)
        ax.text(x + w + 0.06, py, p, ha="left", va="center", fontsize=8)
    return w, h, ins, outs


def out_pin(x, y, name, idx=0):
    w, h, ins, outs = BLOCKS[name]
    return (x + w, pin_y(y, h, idx, len(outs)))


def in_pin(x, y, name, idx=0):
    w, h, ins, outs = BLOCKS[name]
    return (x, pin_y(y, h, idx, len(ins)))


def wire(ax, a, b, feedback=False):
    style = "arc3,rad=0.35" if feedback else "arc3,rad=0.15"
    arrow = FancyArrowPatch(a, b, arrowstyle="->", mutation_scale=11,
                           color="#404040", linewidth=1.3, connectionstyle=style)
    ax.add_patch(arrow)


def main():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(-0.5, 12)
    ax.set_ylim(-0.5, 8)
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.35, color="#999")
    ax.set_title("Siemens SIMATIC CFC — Continuous Function Chart", fontsize=13)

    # Layout: (x, y, name)
    layout = [
        (0.5, 6.0, "AND"),
        (3.5, 6.0, "OR"),
        (6.5, 6.0, "NOT"),
        (9.0, 6.0, "MOVE"),
        (1.0, 3.5, "TON"),
        (4.0, 3.5, "CTU"),
        (7.0, 3.5, "RS"),
        (9.5, 3.5, "CMP>"),
        (3.0, 1.0, "ADD"),
    ]
    pos = {}
    for x, y, name in layout:
        draw_block(ax, x, y, name)
        pos[name] = (x, y)

    # Wiring
    wire(ax, out_pin(*pos["AND"], "AND"), in_pin(*pos["OR"], "OR"))
    wire(ax, out_pin(*pos["OR"], "OR"), in_pin(*pos["NOT"], "NOT"))
    wire(ax, out_pin(*pos["NOT"], "NOT"), in_pin(*pos["MOVE"], "MOVE"))
    wire(ax, out_pin(*pos["TON"], "TON"), in_pin(*pos["CTU"], "CTU"))
    wire(ax, out_pin(*pos["CTU"], "CTU"), in_pin(*pos["RS"], "RS"))
    wire(ax, out_pin(*pos["RS"], "RS"), in_pin(*pos["CMP>"], "CMP>"))
    wire(ax, out_pin(*pos["ADD"], "ADD", 0), in_pin(*pos["TON"], "TON", 1))
    # Feedback loop
    wire(ax, out_pin(*pos["MOVE"], "MOVE"), in_pin(*pos["AND"], "AND", 1), feedback=True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
