#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

import pyomo.opt
import pyutilib.misc

class MPEC_Solver2(pyomo.opt.OptSolver):

    pyomo.util.plugin.alias('mpec_lg', doc='Global solver for linear MPEC problems')

    def __init__(self, **kwds):
        kwds['type'] = 'mpec_lg'
        pyomo.opt.OptSolver.__init__(self,**kwds)

    def _presolve(self, *args, **kwds):
        #
        # Cache the instance
        #
        self._instance = args[0]
        pyomo.opt.OptSolver._presolve(self, *args, **kwds)

    def _apply_solver(self):
        #
        # Transform instance
        #
        instance = self._instance.transform('mpec.simple_disjunction')
        # TODO: Handle condition where the M value is not defined
        if self.options.transform:
            instance2 = instance.transform(self.options.transform)
        else:
            instance2 = instance.transform('gdp.bigm')
        #
        # Solve with a specified solver
        #
        solver = self.options.solver
        if not self.options.solver:
            solver = 'glpk'
        opt = pyomo.opt.SolverFactory(solver)
        self.results = opt.solve(instance2,
                                tee=self.tee,
                                timelimit=self._timelimit)
        #
        # Transform the result back into the original model
        #
        self.results = instance2.update_results(self.results)
        # TODO: This doesn't work yet.

        #
        # Return the sub-solver return condition value and log
        #
        return pyutilib.misc.Bunch(rc=getattr(opt,'_rc', None), log=getattr(opt,'_log',None))

    def _postsolve(self):
        #
        # Uncache the instance
        #
        self._instance = None
        #
        # Return the results
        #
        # TODO: initialize the solver results
        #
        return self.results

    def X_postsolve(self):
        results = pyomo.opt.SolverResults()
        solv = results.solver
        solv.name = self.options.subsolver
        #solv.status = self._glpk_get_solver_status()
        #solv.memory_used = "%d bytes, (%d KiB)" % (peak_mem, peak_mem/1024)
        solv.wallclock_time = self._ans.elapsed['solver_time']
        solv.cpu_time = self._ans.elapsed['solver_cputime']
        solv.termination_condition = pyomo.opt.TerminationCondition.maxIterations
        prob = results.problem
        prob.name = self._instance.name
        prob.number_of_constraints = self._instance.statistics.number_of_constraints
        prob.number_of_variables = self._instance.statistics.number_of_variables
        prob.number_of_binary_variables = self._instance.statistics.number_of_binary_variables
        prob.number_of_integer_variables = self._instance.statistics.number_of_integer_variables
        prob.number_of_continuous_variables = self._instance.statistics.number_of_continuous_variables
        prob.number_of_objectives = self._instance.statistics.number_of_objectives

        from pyomo.core import maximize
        if self.problem.sense == maximize:
            prob.sense = pyomo.opt.ProblemSense.maximize
        else:
            prob.sense = pyomo.opt.ProblemSense.minimize

        sstatus = pyomo.opt.SolutionStatus.unknown

        if not sstatus in ( pyomo.opt.SolutionStatus.error, ):
            soln = pyomo.opt.Solution()
            soln.status = sstatus

            if type(self._ans.ff) in (list, tuple):
                oval = float(self._ans.ff[0])
            else:
                oval = float(self._ans.ff)
            if self.problem.sense == maximize:
                soln.objective[ self.problem._f_name[0] ].value = - oval
            else:
                soln.objective[ self.problem._f_name[0] ].value = oval

            id = 0
            for var_label in self._ans.xf.keys():
                if self._ans.xf[var_label].is_integer():
                    soln.variable[ var_label.name ] = {'Value': int(self._ans.xf[var_label]), 'Id':id}
                else:
                    soln.variable[ var_label.name ] = {'Value': float(self._ans.xf[var_label]), 'Id':id}
                id += 1

            results.solution.insert( soln )

        return results

