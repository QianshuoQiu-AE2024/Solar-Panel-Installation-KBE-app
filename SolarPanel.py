from parapy.core import Input, Part, Attribute
from parapy.geom import GeomBase, Vector, rotate, Box, Position, Point



class SolarPanel(GeomBase):
    """examples of different ways to define and position circles in ParaPy"""
    type = Input()
    position = Input()
    tilt = Input()
    orientation = Input()

    @Attribute
    def type_size(self):
        if self.type == "small":
            return Vector(0.05, 0.991, 0.991)
        elif self.type == "medium":
            return Vector(0.05, 1.65, 0.991)
        elif self.type == "large":
            return Vector(0.05, 1.956, 0.991)
        else:
            return Vector(0.05, 0.991, 0.991)


    @Part
    def panel(self):
        return Box(height=self.type_size.x, width=self.type_size.y, length=self.type_size.z,
                   centered=False,  # check in the class Box definition the effect of setting centered to False
                   color="green",
                   position=rotate(rotate(self.position,
                                          'z',self.orientation,deg=True),'x', self.tilt, deg=True))


if __name__ == '__main__':
    from parapy.gui import display
    display(SolarPanel(type='medium', position=Position(Point(1, 2, 3)), tilt=55, orientation=3))  # Example custom dimensions

    # Check the positions of the circles in the Input tab of the GUI!
    # Do you notice anything interesting? Pay special attention to crv5
    # Although you translated the circle along the x- and y-axes,
    # the 90-degree rotation altered its local orientation relative
    # to the global frame. As a result, from a global perspective,
    # the translation occurred along the x- and z-axes.
    # (there are also ways to specify directions in other frames, including the global one)

