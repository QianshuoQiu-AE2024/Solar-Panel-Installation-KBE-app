from parapy.core import Base, Input, Attribute
from tkinter import Tk, messagebox


class Summary(Base):
    """
    Simple summary of the overall cost / energy yield /
    savings for the entire :class:`House`.

    Inputs
    ----------
    info : tuple
        ``(total_cost, usable_energy_kwh, money_saved_eur_per_year)``,
        produced by :pyattr:`House.summary_info`.

    Important Attributes
    ----------
    total_cost : int
    usable_energy : float
        Annual energy generation after efficiency losses.
    money_saved : int
        EUR saved on a yearly basis.
    """

    info = Input()

    def _popup_error(self, title: str, msg: str):
        dlg = Tk();
        dlg.withdraw()  # hide the root window
        messagebox.showerror(title, msg)  # modal dialog
        dlg.destroy()

    @Attribute
    def total_cost(self):
        return self.info[0]

    @Attribute
    def usable_energy(self):
        return self.info[1]

    @Attribute
    def money_saved(self):
        return self.info[2]

    @Attribute
    def msg(self):
        msg = (f"Your solar panels cost €{int(self.info[0])} "
         f"and will produce about {self.info[1]:.0f} kWh per year "
         f"saving an average of €{int(self.info[2])} per year")
        self._popup_error("Invalid gable_roof_indices", msg)
        return None
    @Attribute
    def title(self):
        return "Solar Panel Summary"