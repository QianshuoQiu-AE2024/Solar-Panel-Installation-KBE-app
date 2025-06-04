from parapy.core import Base, Input, Part, child
from parapy.geom import Position
from SolarPanel import SolarPanel
from OptimizedPlacementCost import OptimizedPlacement

class SolarPanelArray(Base):
    roof_face = Input()
    coords = Input()

    @Part
    def optimizer(self):
        return OptimizedPlacement(roof_face=self.roof_face, coords=self.coords)

    @Part
    def panels(self):
        return SolarPanel(quantify=len(self.optimizer.real_points),
                          type=self.optimizer.best_result[0][0][child.index]['type'],
                          color=self.optimizer.best_result[0][0][child.index]['color'],
                          position=Position(self.optimizer.real_points[child.index]),
                          tilt=self.optimizer.tilt_xy,
                          orientation=self.optimizer.best_result[0][2],
                          shift=self.optimizer.best_result[0][0][child.index]['length'])

