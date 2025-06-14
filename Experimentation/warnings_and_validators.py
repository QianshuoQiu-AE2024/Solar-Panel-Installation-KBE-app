import warnings

from parapy.core import Input, Attribute, Part
from parapy.core.validate import LessThanOrEqualTo, GreaterThan
from parapy.geom import Box, GeomBase


class WarningsExample(GeomBase):
    """
    Demonstrate different ways of generating warnings and validators
    """

    length: float = Input(validator=LessThanOrEqualTo(100))  # ParaPy validator
    """
    length of the box
    Note, it should be less than or equal to 100
    """

    width: float = Input()
    """
    width of the box
    """

    height: float = Input(10., validator=GreaterThan(2))  # ParaPy validator (optional input)
    """
    height of the box.
    Note, it should be larger than 2
    """

    popup_gui: bool = Input(False)
    """
    Do you want to show the width/length aspect ratio warning (imposed_width) with a pop-up? Set a boolean
    """

    @Attribute
    def imposed_width(self) -> float:
        """
        Checks whether the width is larger than length. If larger, raises
        a warning and sets the value of width equal to length
        """
        if self.width > self.length:
            msg = f"width ({self.width}) should be less than the length ({self.length}). Input will be ignored, and box "\
                    "width will be set equal to length."
            # print warning message in console:
            warnings.warn(msg)
            if self.popup_gui:  # invoke pop-up dialogue box using Tk"""
                generate_warning("Warning: Value changed", msg)
            i_width = self.length
        else:
            i_width = self.width
        return i_width
        #! Note: You could also assign the largest feasible value to
        #! `self.width` directly, that is: change the Input value.
        #! Advantage: The user can see directly which value is being used
        #! Disadvantages: This needs to happen as part of an attribute
        #! definition on which `self.box` depends, since it needs to be
        #! evaluated every time the box is drawn.
        #! Also, it may not be a good idea to change users' inputs without
        #! asking.

    @Part
    def box(self):
        """
        Generates a box with imposed width, length and height
        """
        return Box(self.imposed_width,
                   self.length,
                   self.height)


def generate_warning(warning_header, msg):
    """
    This function generates a warning dialog box
    :param warning_header: The text to be shown on the dialog box header
    :param msg: the message to be shown in dialog box
    :return: None as it is GUI operation
    """
    # tkinter is the GUI library used by the ParaPy desktop GUI
    from tkinter import Tk, messagebox

    # initialization
    window = Tk()
    window.withdraw()

    # generates message box and waits for user to close it
    messagebox.showwarning(warning_header, msg)

    # close the message window, terminate the associated process
    window.deiconify()
    window.destroy()
    window.quit()


if __name__ == '__main__':
    obj = WarningsExample(length=20, width=10, height=10) # try what happens if you pass `length=200` here
    from parapy.gui import display
    display(obj)