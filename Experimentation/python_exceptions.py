# Each of the methods below triggers a different type of exception
# In some cases, your IDE can notice this beforehand. Usually that does not work, though, so you should learn to recognize
# the messages and interpret them.


def key_error():  # not such a key in the dictionary
    dct = {"foo": 1}
    return dct["bar"]


def index_error():  # index 3 is out of range
    lst = [0, 1, 2]
    return lst[3]


def type_error():  # cannot add  data of different type
    return 1 + "foo"


class PythonExceptions(object):
    def __init__(self, a):
        self.a = a

    def missing_input(self):
        return self.a*2

    def attribute_error(self):  # not such an attribute in Debugging
        return self.bogus  # note how PyCharm detects and signals this already in the editor


if __name__ == '__main__':
    ''' uncomment the exception you want to trigger'''
    # key_error()
    # index_error()
    # type_error()
    test = PythonExceptions()  # generate missing input error during parsing
    # test = PythonExceptions(1, bogus=3)  # generate type error during parsing

    # exception = PythonExceptions(a=3)
    # exception.attribute_error()

