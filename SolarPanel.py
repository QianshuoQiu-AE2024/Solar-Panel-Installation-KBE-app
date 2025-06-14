from parapy.core import Input, Part, Attribute
from parapy.geom import GeomBase, Vector, Box, Position, Point



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

    Part
    ----------
    module : parapy.geom.Box
        Solar panel module modelled as a box with a specified height, width
        and length. The color shows the type of solar panel and the position
        is passed on from the optimizer solution.

    Notes
    -----
    * The Box uses ``centered=False`` so its “local (0,0,0)” is indeed
      the lower-left corner that the lay-out optimizer works with.
    """

    type = Input() # 'small', 'medium', 'large'
    position = Input() # panel_frame from OptimizedPlacementCost
    color = Input() # Visulaization color of the solar panel type

    @Attribute
    def type_size(self):
        sizes = {
            "small":  (0.05, 0.991, 0.991),
            "medium": (0.05, 1.65,  0.991),
            "large":  (0.05, 1.956, 0.991),
        }
        return Vector(*sizes.get(self.type, sizes["small"]))

    # Generate the box geometry for the solar panel module
    @Part
    def module(self):
        return Box(height=self.type_size.x, width=self.type_size.y, length=self.type_size.z,
                   centered=False,
                   color=self.color,
                   position=self.position)


if __name__ == '__main__':
    from parapy.gui import display
    display(SolarPanel(type='medium', position=Position(Point(1, 2, 3)), tilt=55, orientation=3))  # Example custom dimensions

