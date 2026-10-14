"""Plot one scenario from a decoded CAN log (speed, distance, ECU state and deceleration)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from mini_hil_bench.can_db import KPH_PER_MPS
from mini_hil_bench.config import EcuConfig
from mini_hil_bench.ecu.aeb_ecu import AebState

FIGURE_SIZE_IN = (9.0, 8.0)
FIGURE_DPI = 100


def plot_scenario(df: pd.DataFrame, ecu: EcuConfig, out_path: str | Path, title: str) -> Path:
    """Save a three-panel PNG of a scenario.

    Panels share the time axis: ego speed (with the minimum activation speed), distance to
    the object (valid samples only), and AEB state with the requested deceleration (with the
    partial and full braking levels).

    Args:
        df: Decoded log from ``read_blf``.
        ecu: ECU calibration, used for the threshold lines.
        out_path: Destination PNG path; parent directories are created.
        title: Figure title.

    Returns:
        The path of the written PNG.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=FIGURE_SIZE_IN)
    FigureCanvasAgg(fig)  # render off-screen with the Agg backend, no global pyplot state
    ax_speed, ax_dist, ax_ecu = fig.subplots(3, 1, sharex=True)
    fig.suptitle(title)

    speed = df[df["message"] == "VehicleState"]
    ax_speed.plot(speed["time_s"], speed["EgoSpeed"], label="EgoSpeed")
    ax_speed.axhline(ecu.min_speed_mps * KPH_PER_MPS, ls="--", c="gray", label="min speed")
    ax_speed.set_ylabel("Ego speed [km/h]")

    radar = df[(df["message"] == "RadarObject") & (df["ObjValid"] == 1)]
    ax_dist.plot(radar["time_s"], radar["ObjDistance"], ".", ms=2, label="ObjDistance (valid)")
    ax_dist.set_ylabel("Distance [m]")

    command = df[df["message"] == "AebCommand"]
    ax_ecu.step(command["time_s"], command["AebState"], where="post", label="AebState")
    ax_ecu.set_yticks([s.value for s in AebState], [s.name for s in AebState], fontsize="small")
    ax_decel = ax_ecu.twinx()
    ax_decel.plot(command["time_s"], command["DecelRequest"], c="tab:red", label="DecelRequest")
    for level, name in ((ecu.partial_decel_mps2, "partial"), (ecu.full_decel_mps2, "full")):
        ax_decel.axhline(level, ls=":", c="tab:red", alpha=0.6, label=f"{name} decel")
    ax_decel.set_ylabel("Decel request [m/s²]")
    ax_ecu.set_xlabel("Time [s]")

    for ax in (ax_speed, ax_dist, ax_decel):
        ax.legend(loc="upper right", fontsize="small")
    ax_ecu.legend(loc="upper left", fontsize="small")
    for ax in (ax_speed, ax_dist, ax_ecu):
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIGURE_DPI)
    return out_path
