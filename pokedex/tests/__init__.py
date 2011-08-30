
import inspect
from functools import wraps

# test support code
def params(funcarglist):
    """Basic list-of-dicts test parametrization

    From: http://pytest.org/funcargs.html

    Example:
    @params([dict(a=1, b=2), dict(a=3, b=4)])
    def test_lt(a, b):
        assert a < b
    """
    def decorator(function):
        function.funcarglist = funcarglist
        return function
    return decorator

def positional_params(*paramlist):
    """Magic list-of-lists parametrization

    Example:
    @params([(1, 2), (3, 4)])
    def test_lt(a, b):
        assert a < b
    """
    def decorator(function):
        function.posarglist = paramlist
        return function
    return decorator

def single_params(*paramlist):
    """Magic list-of-lists parametrization

    Example:
    @params('1', '2', '3', '4'])
    def test_int(k):
        assert int(k)
    """
    def decorator(function):
        function.posarglist = [[param] for param in paramlist]
        return function
    return decorator
