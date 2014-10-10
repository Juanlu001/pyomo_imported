from pyutilib.misc import Options
import pyutilib.th as unittest
from pyomo.core import *
from pyomo.openopt.func_designer import Pyomo2FuncDesigner
try:
    import pyomo.openopt.FuncDesigner
    FD_available=True
except:
    FD_available=False

fns = [sin, cos, tan, sinh, cosh, tanh, asin, acos, atan, asinh, acosh, atanh, log, exp, log10, sqrt, pow, abs,  ceil, floor]
xs  = [1.0, 1.0, 1.0, 1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,   1.0,   0.5,   1.0, 1.0, 1.0,   1.0,  1.0, -1.0, 1.5,  1.5] 


@unittest.skipUnless(FD_available, "FuncDesigner module required")
class Tests(unittest.TestCase):

    def setUp(self):
        self.model = ConcreteModel()
        self.model.x = Var()

    def compare(self):
        instance = self.model.create()
        S = Pyomo2FuncDesigner(instance)
        self.assertAlmostEqual(instance.f(), S.f(S.initial_point))

    def tearDown(self):
        self.model = None


@unittest.nottest
def expr_test(self, name):
    options = self.get_options(name)
    self.model.x.value = options.x
    if name == 'pow':
        self.model.f = Objective(expr=options.fn(self.model.x, 2))
    else:
        self.model.f = Objective(expr=options.fn(self.model.x))
    self.compare()
    


for i in range(len(fns)):
    options = Options()
    options.fn = fns[i]
    options.x  = xs[i]
    Tests.add_fn_test(fn=expr_test, name=fns[i].__name__, options=options)    

if __name__ == "__main__":
    unittest.main()
