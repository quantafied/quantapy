"""Source/vortex panel method for NACA 4-digit airfoils.

Converted from the Jupyter notebook `source_panel_method.ipynb` into a
standard Python script.

The default case reproduces the notebook setup:
    NACA 2412, chord = 1, alpha = 5 deg, panels = 200

Usage:
    python source_panel_method.py
    python source_panel_method.py --foil 0012 --alpha 3 --nop 160 --save-plots --no-show
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class PanelGeometry:
    """Geometry arrays for the airfoil panel discretization."""

    XB: np.ndarray  # x boundary points
    YB: np.ndarray  # y boundary points
    XC: np.ndarray  # x control points
    YC: np.ndarray  # y control points
    theta: np.ndarray  # panel angle relative to x-axis [rad]
    beta: np.ndarray  # panel normal angle relative to freestream [rad]
    s: np.ndarray  # panel length


@dataclass
class PanelSolution:
    """Solved panel-method coefficients."""

    gamma: np.ndarray
    at: np.ndarray
    velocity: np.ndarray
    cp: np.ndarray
    cn: np.ndarray
    ca: np.ndarray
    cl_distribution: np.ndarray
    cl: float


def parse_naca4(foil: str) -> tuple[str, str, str, str]:
    """Split a NACA 4-digit airfoil string into its four digit characters."""
    foil = foil.strip()
    if len(foil) != 4 or not foil.isdigit():
        raise ValueError("foil must be a 4-digit NACA designation, for example '2412'.")
    return foil[0], foil[1], foil[2], foil[3]


def panel_gen(
    foil: str = "2412",
    chord: float = 1.0,
    alpha_deg: float = 5.0,
    nop: int = 200,
    plot: bool = True,
    show: bool = True,
    save_path: str | Path | None = None,
) -> PanelGeometry:
    """Generate NACA 4-digit airfoil panel geometry.

    Parameters
    ----------
    foil:
        NACA 4-digit airfoil identifier, such as ``"2412"``.
    chord:
        Chord length.
    alpha_deg:
        Angle of attack in degrees.
    nop:
        Number of panels. This should be even because the notebook's geometry
        construction splits panels evenly between upper and lower surfaces.
    plot:
        Whether to create the discretization plot.
    show:
        Whether to display plots interactively.
    save_path:
        Optional path to save the discretization plot.
    """
    if nop <= 0 or nop % 2 != 0:
        raise ValueError("nop must be a positive even integer.")

    D1, D2, D3, D4 = parse_naca4(foil)
    alpha = math.radians(alpha_deg)

    thickness = float(D3 + D4) / 100.0
    max_camber = float(D1) * 0.01
    camber_location = float(D2) * 0.1

    # Cosine-spaced x coordinates from trailing edge to leading edge and back.
    x = np.linspace(0.0, 2.0 * np.pi, nop + 1)
    x = chord * 0.5 * (np.cos(x) + 1.0)

    # Camber line.
    y_c = np.zeros(nop + 1)
    if max_camber != 0 and camber_location != 0:
        for i in range(nop):
            if 0 <= x[i] <= camber_location * chord:
                y_c[i] = (max_camber * x[i] / camber_location**2) * (
                    2 * camber_location - x[i] / chord
                )
            elif camber_location * chord <= x[i] <= chord:
                y_c[i] = max_camber * ((chord - x[i]) / (1 - camber_location) ** 2) * (
                    1 + (x[i] / chord) - 2 * camber_location
                )

    x_t = x * np.cos(alpha) + y_c * np.sin(alpha)
    y_c_t = -x * np.sin(alpha) + y_c * np.cos(alpha)
    _ = (x_t, y_c_t)  # Kept for parity with the notebook; transformed arrays are not reused.

    # Camber slope angle.
    dy_c = np.zeros(nop + 1)
    if max_camber != 0 and camber_location != 0:
        for i in range(nop):
            if 0 < x[i] < camber_location * chord:
                dy_c[i] = (2 * max_camber / camber_location**2) * (camber_location - x[i] / chord)
            elif camber_location * chord < x[i] < chord:
                dy_c[i] = (2 * max_camber / (1 - camber_location) ** 2) * (
                    camber_location - x[i] / chord
                )

    theta_camber = np.array([math.atan2(value, 1.0) for value in dy_c])

    # Symmetric thickness distribution.
    y_t = chord * 5 * thickness * (
        0.2969 * np.sqrt(x / chord)
        - 0.1260 * x / chord
        - 0.3516 * (x / chord) ** 2
        + 0.2843 * (x / chord) ** 3
        - 0.1036 * (x / chord) ** 4
    )

    # Cambered airfoil upper/lower coordinates.
    XU = x - y_t * np.sin(theta_camber)
    XL = x + y_t * np.sin(theta_camber)
    YU = y_c + y_t * np.cos(theta_camber)
    YL = y_c - y_t * np.cos(theta_camber)

    # Rotate coordinates to represent angle of attack.
    XU_t = XU * np.cos(alpha) + YU * np.sin(alpha)
    XL_t = XL * np.cos(alpha) + YL * np.sin(alpha)
    YU_t = -XU * np.sin(alpha) + YU * np.cos(alpha)
    YL_t = -XL * np.sin(alpha) + YL * np.cos(alpha)

    half = nop // 2
    XU_t = XU_t[:half]
    XL_t = XL_t[:half]
    YU_t = YU_t[:half]
    YL_t = YL_t[:half]

    # Boundary points.
    XB = np.zeros(nop + 1)
    XB[:half] = XL_t
    XB[half] = 0.0
    XB[half + 1 : nop + 1] = np.flip(XU_t, axis=0)

    YB = np.zeros(nop + 1)
    YB[:half] = YL_t
    YB[half] = 0.0
    YB[half + 1 : nop + 1] = np.flip(YU_t, axis=0)

    # Control points.
    XC = np.zeros(nop)
    YC = np.zeros(nop)
    for i in range(nop):
        XC[i] = 0.5 * (XB[i] + XB[i + 1])
        YC[i] = 0.5 * (YB[i] + YB[i + 1])

    # Panel geometry.
    s = np.zeros(nop)
    theta = np.zeros(nop)
    for i in range(nop):
        s[i] = np.sqrt((XB[i + 1] - XB[i]) ** 2 + (YB[i + 1] - YB[i]) ** 2)
        theta[i] = math.atan2(YB[i + 1] - YB[i], XB[i + 1] - XB[i])

    beta = theta + np.pi / 2.0

    if plot:
        fig, ax = plt.subplots(figsize=(20, 6))
        ax.set_title(f"{foil} Discretization")
        ax.plot(XB, YB, "ro", label="Boundary Points")
        ax.plot(XB, YB, "k", label="Surface")
        ax.plot(XC, YC, "xg", label="Control Points")
        ax.legend()
        ax.grid()
        if save_path is not None:
            fig.savefig(save_path, bbox_inches="tight", dpi=150)
        if show:
            plt.show()
        else:
            plt.close(fig)

    return PanelGeometry(XB=XB, YB=YB, XC=XC, YC=YC, theta=theta, beta=beta, s=s)


def vortex_strength(geometry: PanelGeometry, nop: int) -> tuple[np.ndarray, np.ndarray]:
    """Solve the linear system for vortex strengths at each control point."""
    XB, YB, XC, YC = geometry.XB, geometry.YB, geometry.XC, geometry.YC
    theta, s = geometry.theta, geometry.s

    an = np.zeros((nop + 1, nop + 1))
    at = np.zeros((nop + 1, nop + 1))

    cn1 = np.zeros((nop, nop))
    cn2 = np.zeros((nop, nop))
    ct1 = np.zeros((nop, nop))
    ct2 = np.zeros((nop, nop))

    for i in range(nop):
        for j in range(nop):
            if i == j:
                cn1[i, j] = -1.0
                cn2[i, j] = 1.0
                ct1[i, j] = np.pi / 2.0
                ct2[i, j] = np.pi / 2.0
            else:
                A = -(XC[i] - XB[j]) * np.cos(theta[j]) - (YC[i] - YB[j]) * np.sin(theta[j])
                B = (XC[i] - XB[j]) ** 2 + (YC[i] - YB[j]) ** 2
                C = np.sin(theta[i] - theta[j])
                D = np.cos(theta[i] - theta[j])
                E = (XC[i] - XB[j]) * np.sin(theta[j]) - (YC[i] - YB[j]) * np.cos(theta[j])
                F = np.log(1.0 + (s[j] ** 2 + 2.0 * A * s[j]) / B)
                G = math.atan2(E * s[j], B + A * s[j])
                P = (XC[i] - XB[j]) * np.sin(theta[i] - 2.0 * theta[j]) + (
                    YC[i] - YB[j]
                ) * np.cos(theta[i] - 2.0 * theta[j])
                Q = (XC[i] - XB[j]) * np.cos(theta[i] - 2.0 * theta[j]) - (
                    YC[i] - YB[j]
                ) * np.sin(theta[i] - 2.0 * theta[j])

                cn2[i, j] = D + 0.5 * Q * F / s[j] - (A * C + D * E) * G / s[j]
                cn1[i, j] = 0.5 * D * F + C * G - cn2[i, j]
                ct2[i, j] = C + 0.5 * P * F / s[j] + (A * D - C * E) * G / s[j]
                ct1[i, j] = 0.5 * C * F - D * G - ct2[i, j]

    for i in range(nop):
        an[i, 0] = cn1[i, 0]
        an[i, -1] = cn2[i, nop - 1]
        at[i, 0] = ct1[i, 0]
        at[i, -1] = ct2[i, nop - 1]
        for j in range(1, nop):
            an[i, j] = cn1[i, j] + cn2[i, j - 1]
            at[i, j] = ct1[i, j] + ct2[i, j - 1]

    rhs = np.append(np.sin(theta), 0.0)

    # Kutta condition.
    an[-1, 0] = 1.0
    an[-1, -1] = 1.0
    for j in range(1, nop):
        an[-1, j] = 0.0

    gamma = np.linalg.solve(an, rhs)
    return gamma, at


def compute_coefficients(
    geometry: PanelGeometry,
    gamma: np.ndarray,
    at: np.ndarray,
    alpha_deg: float,
    plot: bool = True,
    show: bool = True,
    save_path: str | Path | None = None,
) -> PanelSolution:
    """Compute velocity, pressure, and lift coefficients."""
    nop = len(geometry.s)
    alpha = math.radians(alpha_deg)

    velocity = np.zeros(nop)
    cp = np.zeros(nop)

    for i in range(nop):
        smt = 0.0
        for j in range(nop + 1):
            smt += at[i, j] * gamma[j]
        velocity[i] = np.cos(geometry.theta[i]) + smt
        cp[i] = 1.0 - velocity[i] ** 2

    if plot:
        fig, ax = plt.subplots(figsize=(20, 15))
        ax.set_title("Pressure Coefficient w Respect to Transformed Coordinates")
        ax.plot(geometry.XC, cp)
        ax.set_xlabel("Control Point Along X-Axis")
        ax.set_ylabel(r"$C_p$")
        ax.grid()
        ax.invert_yaxis()
        if save_path is not None:
            fig.savefig(save_path, bbox_inches="tight", dpi=150)
        if show:
            plt.show()
        else:
            plt.close(fig)

    cn = -cp * geometry.s * np.sin(geometry.beta)
    ca = -cp * geometry.s * np.cos(geometry.beta)
    cl_distribution = cn * np.cos(alpha) - ca * np.sin(alpha)
    cl = float(np.sum(cl_distribution))

    return PanelSolution(
        gamma=gamma,
        at=at,
        velocity=velocity,
        cp=cp,
        cn=cn,
        ca=ca,
        cl_distribution=cl_distribution,
        cl=cl,
    )


def run_panel_method(
    foil: str = "2412",
    chord: float = 1.0,
    alpha_deg: float = 5.0,
    nop: int = 200,
    plot: bool = True,
    show: bool = True,
    output_dir: str | Path | None = None,
) -> tuple[PanelGeometry, PanelSolution]:
    """Run the full panel-method workflow."""
    output_dir_path = Path(output_dir) if output_dir is not None else None
    if output_dir_path is not None:
        output_dir_path.mkdir(parents=True, exist_ok=True)

    geometry_plot = output_dir_path / "airfoil_discretization.png" if output_dir_path else None
    cp_plot = output_dir_path / "pressure_coefficient.png" if output_dir_path else None

    geometry = panel_gen(
        foil=foil,
        chord=chord,
        alpha_deg=alpha_deg,
        nop=nop,
        plot=plot,
        show=show,
        save_path=geometry_plot,
    )
    gamma, at = vortex_strength(geometry, nop=nop)
    solution = compute_coefficients(
        geometry=geometry,
        gamma=gamma,
        at=at,
        alpha_deg=alpha_deg,
        plot=plot,
        show=show,
        save_path=cp_plot,
    )
    return geometry, solution


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a NACA 4-digit source/vortex panel method.")
    parser.add_argument("--foil", default="2412", help="NACA 4-digit airfoil, e.g. 2412")
    parser.add_argument("--chord", type=float, default=1.0, help="Chord length")
    parser.add_argument("--alpha", type=float, default=5.0, help="Angle of attack in degrees")
    parser.add_argument("--nop", type=int, default=200, help="Number of panels, must be even")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting")
    parser.add_argument("--no-show", action="store_true", help="Do not display plots interactively")
    parser.add_argument(
        "--save-plots",
        action="store_true",
        help="Save generated plots to --output-dir. Implies plot generation.",
    )
    parser.add_argument("--output-dir", default="panel_method_outputs", help="Directory for saved plots")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    output_dir = args.output_dir if args.save_plots else None
    plot = args.save_plots or not args.no_plot

    _, solution = run_panel_method(
        foil=args.foil,
        chord=args.chord,
        alpha_deg=args.alpha,
        nop=args.nop,
        plot=plot,
        show=not args.no_show,
        output_dir=output_dir,
    )

    print(f"NACA {args.foil}")
    print(f"alpha = {args.alpha:.6g} deg")
    print(f"panels = {args.nop}")
    print(f"CL = {solution.cl:.8f}")


if __name__ == "__main__":
    main()
