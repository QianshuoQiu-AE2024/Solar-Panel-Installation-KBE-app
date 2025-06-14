#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#
# This file is subject to the terms and conditions defined in
# the license agreement that you have received with this source code
#
# THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY
# KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR
# PURPOSE.


from parapy.core import Base, Attribute, Part, Input
from parapy.geom import Box


class ParaPyExceptions(Base):

    @Attribute
    def key_error(self):  # not such a key in the dictionary
        dct = {"foo": 1}
        return dct["bar"]

    @Attribute
    def index_error(self):  # index 3 is out of range
        lst = [0, 1, 2]
        return lst[3]

    @Attribute
    def type_error(self):  # cannot add different data type
        return 1 + "foo"

    @Attribute
    def attribute_error(self):  # not such an attribute in Debugging
        return self.bogus

    # circular reference error: a --> c ---> b --> a
    @Attribute
    def a(self):
        return self.c + 1

    @Attribute
    def b(self):
        return self.a + 1

    @Attribute
    def c(self):
        return self.b + 1

    @Attribute
    def invalid_attribute(self):
        return self.whatever  # returning a not existing class attribute

    # behaviour when a user defined class is involved (Container, in this example)
    @Part
    def invalid_argument(self):
        """Part definition that specifies an unexpected input."""
        return Container(volume=10,
                         height=1,
                         bogus="bogus input")
        # note how PyCharm marks `bogus` as unexpected argument for the class
        # `Container`, while ParaPy ignores it!
        # …however, note what happens if you try defining a `container` object
        # like this in the Python console!

        # This shows the value of running some buggy code in the console:
        # Not just do you get more error messages and warnings, but it gives
        # you direct access to the objects your code is trying (and failing…)
        # to work with.

    @Part
    def missing_required_input(self):  # passing insufficient input
        return Container(height=1)  # note how PyCharm already signals a missing input

    # behaviour when a ParaPy primitive is involved (Box, in this example)
    @Part  # this behaves like an exception and pops up run time
    def missing_required_input_primitive(self):  # passing insufficient input
        return Box(height=1)  # note how PyCharm already signals a missing input

    # @Part  # this behaves like a syntax error and prevents app execution
    # def invalid_argument_primitive(self):  # passing invalid argument input
    #     return Box(width=10,
    #                height=1,
    #                bogus="bogus input")  # note how PyCharm already marks this as
    #     # unexpected argument for the class Box


class Container(Base):
    """ParaPy class that does nothing but store its two required inputs:
    `volume` and `height`."""
    volume = Input()
    height = Input()


if __name__ == '__main__':
    # Run this script, and click through the different attributes and part inputs!
    from parapy.gui import display
    exceptions = ParaPyExceptions(label='parapy_exceptions')
    display(exceptions)