from parapy.core import Input, Part, Attribute
from parapy.geom import GeomBase, Vector, rotate, Box, Position, Point



class SolarPanel(GeomBase):
    """
    Thin wrapper that turns a rectangular Parametric Box into a
    solar panel module with the right size, placement, tilt,
    orientation and colour.

    Inputs
    ----------
    type : {'small', 'medium', 'large'}
        Panel size (see :pyattr:`type_size` for exact dimensions).
    position : parapy.geom.Position
        Local frame whose *origin* is the panel’s bottom-left corner and
        whose axes already point in the desired directions (created by
        :pyattr:`OptimizedPlacement.panel_frames`).
    color : str | tuple
        Visualization of the solar panel type.

    Notes
    -----
    * The Box uses ``centered=False`` so its “local (0,0,0)” is indeed
      the lower-left corner that the lay-out optimiser works with.
    """

    type = Input()
    position = Input()
    tilt = Input()
    orientation = Input()
    color = Input()

    @Attribute
    def type_size(self):
        sizes = {
            "small":  (0.05, 0.991, 0.991),
            "medium": (0.05, 1.65,  0.991),
            "large":  (0.05, 1.956, 0.991),
        }
        return Vector(*sizes.get(self.type, sizes["small"]))

    @Part
    def panel(self):
        return Box(height=self.type_size.x, width=self.type_size.y, length=self.type_size.z,
                   centered=False,
                   color=self.color,
                   position=self.position)


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

