#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

from pyomo.environ import *

model = AbstractModel()
model.X = Var()

if model.X >= 10.0:
    pass
if value(model.X) >= 10.0:
    pass

def c_rule(m):
    if m.X >= 10.0:
        pass
    if value(m.X) >= 10.0:
        pass
    return m.X >= 10.0

model.C = Constraint(rule=c_rule)
