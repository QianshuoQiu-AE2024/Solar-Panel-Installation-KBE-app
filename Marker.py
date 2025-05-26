from parapy.core import Base, Input, child, Part, Attribute
from parapy.geom import Sphere, translate, TextLabel, Vector


class Marker(Base):
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