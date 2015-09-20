#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

#
# Example 2.2 - Allen Holder
#

from pyomo.core import *

# Instantiate the model
model = AbstractModel()

# Parameters for Set Definitions
model.NumTimePeriods = Param(within=NonNegativeIntegers)

# Sets
model.StartTime = RangeSet(1,model.NumTimePeriods)

# Parameters
model.RequiredWorkers = Param(model.StartTime, within=NonNegativeIntegers)

# Variables
model.NumWorkers = Var(model.StartTime, within=NonNegativeIntegers)

# Objective
def CalcTotalWorkers(M):
    return sum (M.NumWorkers[i] for i in M.StartTime)
model.TotalWorkers = Objective(rule=CalcTotalWorkers, sense=minimize)

# Constraints
def EnsureWorkforce(M, i):
    if i != M.NumTimePeriods.value:
        return M.NumWorkers[i] + M.NumWorkers[i+1] >= M.RequiredWorkers[i+1]
    else:
        return M.NumWorkers[1] + M.NumWorkers[M.NumTimePeriods.value] \
               >= M.RequiredWorkers[1]
model.WorkforceDemand = Constraint(model.StartTime, rule=EnsureWorkforce)
