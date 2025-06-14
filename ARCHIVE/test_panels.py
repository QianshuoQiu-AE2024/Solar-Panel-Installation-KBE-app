from parapy.core import Base, Input, Attribute, Part, child
from parapy.geom import Face, Rectangle, Position, rotate, Point, Orientation
from SolarPanelArray import SolarPanelArray

class TestPanels(Base):

    @Attribute(in_tree=True)
    def roof_faces(self):
        return [Face(Rectangle(width=7, length=4, position=rotate(Position(Point(0, 0, 0)), 'y', 25, deg=True)))]#, Face(Rectangle(width=7, length=4))]

    @Attribute
    def coords(self):
        return [30.370216, 12.895168]

    @Part
    def solar_panel_arrays(self):
        return SolarPanelArray(
            quantify=len(self.roof_faces),
            roof_face=self.roof_faces[child.index],
            coords=self.coords
        )

if __name__ == '__main__':
    from parapy.gui import display
    obj = TestPanels()
    display(obj)