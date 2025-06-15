from parapy.core import Base, Input, Attribute
import os

class TextWriter(Base):
    """
    Simple text writer that gathers, organises and then outputs
    the results from the complete solar panel installation app.

    Inputs
    ----------
    solar_panel_details : dict
        Dictionary containing all information about the solar panels,
        their placement, roof area and radiation.
    summary_info : tuple
        ``(total_cost, usable_energy_kwh, money_saved_eur_per_year)``,
        produced by :pyattr:`House.summary_info`.
    filename : os.path
        Path of where to store output and definition of file name.

    Attributes
    ----------
    save_file : None
        Function that takes all the gathered data from 'House' and
        exports it into a text file so it can be used and shared.
    """
    solar_panel_details = Input()
    summary_info = Input()
    filename = os.path.join("OUTPUT", "Results.txt")  # Dynamic path

    @Attribute
    def save_file(self):
        print("TextWriter: Writing file...")

        if not self.solar_panel_details or not self.summary_info:
            print("[ERROR] TextWriter: Missing input data")
            return

        try:
            os.makedirs(os.path.dirname(self.filename), exist_ok=True)

            with open(self.filename, "w", encoding="utf-8") as f:
                # Write per-roof-face data
                for i, detail in enumerate(self.solar_panel_details):

                    f.write(f"Roof Face {i + 1}:\n")
                    f.write(f"      Roof Area: {detail['roof_area']:.2f} m²\n")
                    f.write(f"      Panel Total Area: {detail['panel_total_area']:.2f} m²\n")
                    counts = detail['panel_counts']
                    f.write(f"      Number of Panels:\n")
                    f.write(f"          Small: {counts['small']}\n")
                    f.write(f"          Medium: {counts['medium']}\n")
                    f.write(f"          Large: {counts['large']}\n")
                    f.write(f"      Best Tilt: {detail['best_tilt']:.1f}°\n")
                    f.write(f"      Best Azimuth: {detail['best_azimuth']:.1f}°\n")
                    f.write(f"      Actual Azimuth: {detail['actual_azimuth']:.1f}°\n")
                    f.write(f"      Avg Daily Radiation: {detail['avg_daily_radiation']:.2f} kWh/m²/day\n\n")

                # Write summary info
                total_cost, usable_energy, money_saved = self.summary_info
                f.write("Summary:\n")
                f.write(f"      Total Cost: €{total_cost:.2f}\n")
                f.write(f"      Usable Energy: {usable_energy:.2f} kWh/year\n")
                f.write(f"      Money Saved: €{money_saved:.2f}/year\n")

        except Exception as e:
            print(f"[ERROR] Failed to write file: {e}")