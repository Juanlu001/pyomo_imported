#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

# A Suffix example for the collection of duals.
#
# This Pyomo example is formulated as a python script.
# To run this script execute the following command:
#
# $ pyomo_python gurobi_ampl_iis.py
#
# Execution of this script requires that a solver with
# dual reporting capabilities (e.g., CPLEX, Gurobi, Cbc)
# is in the current search path for executables
# on this system. This example was tested using Gurobi
# Solver 5.1.0

import pyomo.environ
from pyomo.core import *
from pyomo.opt import SolverFactory

### Create the a solver plugin
solver = 'gurobi'
solver_io = 'lp' # Uses the LP file interface
stream_solver = False     # True prints solver output to screen
keepfiles =     False     # True prints intermediate file names (.nl,.sol,...) 
opt = SolverFactory(solver,solver_io=solver_io)

if opt is None:
    print("")
    print("ERROR: Unable to create solver plugin for %s "\
          "using the %s interface" % (solver, solver_io))
    print("")
    exit(1)

# import the simple example model containing a
# 'dual' IMPORT Suffix component
from duals_pyomo import model

### Generate the constraint expression trees if necessary
if solver_io != 'nl':
    # only required when not using the ASL (NL file) interface
    model.preprocess()
###

### Send the model to gurobi_ampl and collect the solution
# The solver plugin will scan the model for all active suffixes
# valid for importing, which it will store into the results object
results = opt.solve(model,
                    keepfiles=keepfiles,
                    tee=stream_solver)
model.load(results)

print("")
print("Dual Solution")
print("%s: %s" % (model.con, model.dual[model.con]))
