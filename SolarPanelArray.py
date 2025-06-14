from parapy.core import Base, Input, Part, child, Attribute
from parapy.geom import Position
from SolarPanel import SolarPanel
from OptimizedPlacementCost import OptimizedPlacement

class SolarPanelArray(Base):
    """
    Container that groups all :class:`SolarPanel` objects belonging to a
    *single* roof face.

    Inputs
    ----------
    roof_face : parapy.geom.Face
        Support surface – forwarded to :class:`OptimizedPlacement`.
    coords : list[float]
        Latitude / longitude – forwarded to :class:`OptimizedPlacement`.
    budget : float
        Budget for *this* face (already pre-allocated by :class:`House`).
    loss : float, default 18 %
        Electrical loss factor.

    Parts
    -----
    solution : :class:`OptimizedPlacement`
        Performs heuristics to find best fitting geometric / financial /
        energy yielding solar panel placement.
    solar_panels : list[:class:`SolarPanel`]
        Individual solar panels, positioned and typed by the optimizer.
    """

    roof_face = Input() # Parapy Faces of both flat and gable roofs
    coords = Input() # Latitude and longitude of the house
    budget = Input() # Budget for this face
    loss = Input(18) # Electrical loss factor, default 18%

    @Part
    def solution(self):
        return OptimizedPlacement(roof_face=self.roof_face,
                                  coords=self.coords,
                                  budget=self.budget,
                                  loss=self.loss)

    @Part
    def solar_panels(self):
        return SolarPanel(quantify=len(self.solution.real_points),
                          type=self.solution.best_result[0][0][child.index]['type'],
                          color=self.solution.best_result[0][0][child.index]['color'],
                          position=self.solution.panel_frames[child.index])


