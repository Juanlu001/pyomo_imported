#
# A duality example adapted from
#    http://www.stanford.edu/~ashishg/msande111/notes/chapter4.pdf
#
import pyomo.environ
from pyomo.core import *
from pyomo.bilevel import *

def pyomo_create_model(options, model_options):

    model = ConcreteModel()
    model.z = Var(bounds=(1,2))
    model.x1 = Var(within=NonNegativeReals)
    model.x2 = Var(within=NonNegativeReals)
    model.o = Objective(expr=model.z*(3*model.x1 + 2.5*model.x2), sense=minimize)

    # Create a submodel
    # The argument indicates the lower-level decision variables
    model.sub = SubModel(fixed=model.z)
    model.sub.obj = Objective(expr=model.o.expr, sense=maximize)
    model.sub.c1 = Constraint(expr=4.44*model.x1 <= 100)
    model.sub.c2 = Constraint(expr=6.67*model.x2 <= 100)
    model.sub.c3 = Constraint(expr=4*model.x1 + 2.86*model.x2 <= 100)
    model.sub.c4 = Constraint(expr=3*model.x1 + 6*model.x2 <= 100)

    return model
