from parapy.core import Base, Input, Attribute

class Summary(Base):
    info = Input()

    @Attribute
    def total_cost(self):
        return self.info[0]

    @Attribute
    def usable_power(self):
        return self.info[1]

    @Attribute
    def money_saved(self):
        return self.info[2]

    @Attribute
    def msg(self):
        return (f"Your solar panels cost €{int(self.info[0])} "
                f"and will produce about {self.info[1]:.0f} kWh per year "
                f"saving an average of €{int(self.info[2])} per year")
    @Attribute
    def title(self):
        return "Solar Panel Summary"