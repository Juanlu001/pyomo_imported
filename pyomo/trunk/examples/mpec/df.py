# df.py
# Problem adapted from
#
# Modeling and solution environments for MPEC: GAMS and MATLAB
# Steven P Dirkse and Michael C. Ferris
# in Reformulation: Nonsmooth, Piecewise Smooth, Semismooth and Smoothing Methods
# Applied Optimization Volume 22, 1999, pp. 127-147.
# Editors Masao Fukushima and Liqun Qi
#
import pyomo.modeling
from pyomo.core import *
from pyomo.mpec import Complementarity

M = ConcreteModel()
M.x = Var(bounds=(-1,2))
M.y = Var()

M.o = Objective(expr=(M.x - 1 - M.y)**2)
M.c1 = Constraint(expr=M.x**2 <= 2)
M.c2 = Constraint(expr=(M.x - 1)**2 + (M.y - 1)**2 <= 3)
M.c3 = Complementarity(expr=(M.y - M.x**2 + 1 >= 0, M.y >= 0))


model = TransformationFactory('mpec.simple_disjunction').apply(M)
model.pprint()