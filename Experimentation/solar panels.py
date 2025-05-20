



from parapy.core import Input, Part
from parapy.geom import GeomBase, Circle, translate, rotate, Box



class panels(GeomBase):
    """examples of different ways to define and position circles in ParaPy"""

    tilt: float=Input()
    orientation: float=Input()


    @Part
    def small_panel(self):
        return Box(height=0.05, width=0.991, length=0.991,
                   centered=False,  # check in the class Box definition the effect of setting centered to False
                   color="green",
                   position=rotate(rotate(self.position,
                                          'z',self.orientation,deg=True),'x', self.tilt, deg=True))

    @Part
    def mid_panel(self):
        return Box(height=0.05, width=1.65, length=0.991,
                   centered=False,  # check in the class Box definition the effect of setting centered to False
                   color="green",
                   position=rotate(rotate(self.position,
                                          'z', self.orientation, deg=True), 'x', self.tilt, deg=True))

    @Part
    def large_panel(self):
        return Box(height=0.05, width=1.956, length=0.991,
                   centered=False,  # check in the class Box definition the effect of setting centered to False
                   color="green",
                   position=rotate(rotate(self.position,
                                          'z', self.orientation, deg=True), 'x', self.tilt, deg=True))




if __name__ == '__main__':
    from parapy.gui import display
    display(panels(tilt=55, orientation=3))  # Example custom dimensions

    # Check the positions of the circles in the Input tab of the GUI!
    # Do you notice anything interesting? Pay special attention to crv5
    # Although you translated the circle along the x- and y-axes,
    # the 90-degree rotation altered its local orientation relative
    # to the global frame. As a result, from a global perspective,
    # the translation occurred along the x- and z-axes.
    # (there are also ways to specify directions in other frames, including the global one)

