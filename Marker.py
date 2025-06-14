from parapy.core import Base, Input, child, Part, Attribute
from parapy.geom import Sphere, translate, TextLabel, Vector


class Marker(Base):
    """
    Visual helper that draws little balls (and labels) at arbitrary points.

    Inputs
    ----------
    points : Sequence[parapy.geom.Point]
        World-space coordinates to mark.
    color : str | tuple
        ParaPy colour spec (e.g. ``'red'`` or ``(1,0,0)``).
    offset : parapy.geom.Vector, default (0,0,0)
        Translation applied to all ``points`` before rendering.
    radius : float, default 0.25 m
        Sphere radius.
    text_size : float, default 0.8 m
        Height of the numeric index labels.
    hidden : bool, default ``False``
        Hide/show the markers (useful when the GUI gets cluttered).

    Parts
    -----
    markers : list[parapy.geom.Sphere]
        Red sphere around marked point for visualization.
    marker_labels : list[parapy.geom.TextLabel]
        Label to indicate index of marked point.
    """

    points = Input()
    color = Input()
    offset= Input(Vector(0,0,0))
    radius = Input(0.25)
    text_size = Input(0.8)
    hidden = Input(False)


    @Part
    def markers(self):
        return Sphere(
            radius=self.radius,
            position=translate(self.points[child.index], self.offset, 1),
            label=f"{child.index}",
            color=self.color,
            quantify=len(self.points),
            hidden=self.hidden
        )

    @Attribute
    def label_offset(self):
        return self.offset + Vector(0,0,0.5)

    @Part
    def marker_labels(self):
        return TextLabel(
            quantify=len(self.points),
            text=str(child.index),
            position=translate(self.points[child.index], self.label_offset, 1),
            size=0.8,
            color=self.color
        )