"""Generic educational geometry. No task-specific mechanics or decision logic."""
import numpy as np
from matplotlib.patches import Arc, Circle

from .charts import numeric


def orthographic(points, *, azimuth=30, elevation=20):
    """Project supplied 3D coordinates into a camera's 2D right/up basis.

    This is an orthographic diagram, not a perspective or visibility test.
    """
    points = numeric(points, ndim=2)
    if points.shape[1] != 3 or not np.isfinite([azimuth, elevation]).all():
        raise ValueError("Expected finite Nx3 coordinates and view angles")
    a, e = np.deg2rad([azimuth, elevation])
    right = np.array([-np.sin(a), np.cos(a), 0])
    up = np.array([-np.cos(a)*np.sin(e), -np.sin(a)*np.sin(e), np.cos(e)])
    return points @ np.array([right, up]).T


def angle_marker(ax, vertex, ray1, ray2, *, radius, label):
    """Mark the smaller angle of two supplied 2D rays (degrees for plotting)."""
    v, a, b = [numeric(p) for p in (vertex, ray1, ray2)]
    if any(len(p) != 2 for p in (v, a, b)) or not np.isfinite(radius) or radius <= 0:
        raise ValueError("Expected 2D points and positive radius")
    a, b = a-v, b-v
    if min(np.linalg.norm(a), np.linalg.norm(b)) <= 1e-12:
        raise ValueError("Angle rays must be nonzero")
    start = np.degrees(np.arctan2(a[1], a[0]))
    delta = (np.degrees(np.arctan2(b[1], b[0])) - start + 180) % 360 - 180
    lo, hi = sorted([start, start+delta])
    ax.add_patch(Arc(v, 2*radius, 2*radius, theta1=lo, theta2=hi, color="#285F86", linewidth=1))
    middle = np.deg2rad((lo+hi)/2)
    ax.annotate(label, v+1.45*radius*np.array([np.cos(middle), np.sin(middle)]),
                ha="center", va="center")
    return abs(delta)


def sphere_section(fig, *, radius, height):
    """Sphere and a horizontal circular section, paired with its meridian section.

    Dimensions come from the caller. The diagram illustrates r² + h² = R²;
    it does not establish any claim about a particular physical application.
    """
    if not np.isfinite([radius, height]).all() or radius <= 0 or abs(height) >= radius:
        raise ValueError("A nondegenerate section requires R>0 and |h|<R")
    section_radius = np.sqrt(radius**2-height**2)
    left = fig.add_subplot(1, 2, 1, projection="3d")
    right = fig.add_subplot(1, 2, 2)
    t = np.linspace(0, 2*np.pi, 160)
    u, v = np.meshgrid(np.linspace(0, 2*np.pi, 48), np.linspace(0, np.pi, 24))
    x, y, z = radius*np.cos(u)*np.sin(v), radius*np.sin(u)*np.sin(v), radius*np.cos(v)
    left.plot_surface(x, y, z, color="#B7CBD7", alpha=.12, linewidth=0, shade=False)
    left.plot_wireframe(x, y, z, rstride=6, cstride=8, color="#697884", alpha=.3, linewidth=.55)
    left.plot(section_radius*np.cos(t), section_radius*np.sin(t), np.full_like(t, height),
              color="#285F86", linewidth=2)
    left.plot([0, 0], [0, 0], [0, height], color="#D88736", linewidth=1.5)
    left.scatter([0], [0], [0], color="#333333", s=12)
    left.text(0, 0, -radius*.18, "$O$")
    left.text(radius*.16, 0, height/2, "$h$", color="#D88736")
    left.set_proj_type("ortho")
    left.set_box_aspect((1, 1, 1), zoom=1.15)
    left.set(xlim=(-radius, radius), ylim=(-radius, radius), zlim=(-radius, radius))
    left.view_init(elev=22, azim=-58)
    left.set_axis_off()
    right.add_patch(Circle((0, 0), radius, facecolor="#F2F6F8", edgecolor="#697884", linewidth=1))
    right.plot([-section_radius, section_radius], [height, height], color="#285F86", linewidth=2)
    right.plot([0, section_radius], [0, height], color="#697884", linewidth=1)
    right.plot([0, 0], [0, height], color="#D88736", linewidth=1.4)
    right.scatter([0], [0], color="#333333", s=14)
    right.annotate("$O$", (0, 0), xytext=(-13, -13), textcoords="offset points")
    right.annotate("$h$", (0, height/2), xytext=(-12, 0), textcoords="offset points")
    right.annotate("$R$", (section_radius*.6, height*.6), xytext=(8, -8), textcoords="offset points")
    right.annotate("$r$", (section_radius/2, height), xytext=(0, 9), textcoords="offset points")
    right.set(xlim=(-1.15*radius, 1.15*radius), ylim=(-1.15*radius, 1.15*radius))
    right.set_aspect("equal")
    right.set_axis_off()
    left.set_title("(a) 空间结构", fontsize=9, pad=0)
    right.set_title("(b) 子午截面", fontsize=9)
    return left, right
