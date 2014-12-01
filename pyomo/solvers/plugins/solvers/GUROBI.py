#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008 Sandia Corporation.
#  This software is distributed under the BSD License.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  For more information, see the Pyomo README.txt file.
#  _________________________________________________________________________

import os
import sys
import re
import string
import re
import xml.dom.minidom
import time

import pyutilib.services
import pyutilib.common
import pyutilib.misc

import pyomo.util.plugin
from pyomo.opt.base import *
from pyomo.opt.base.solvers import _extract_version
from pyomo.opt.results import *
from pyomo.opt.solver import *
from pyomo.core.base.blockutil import has_discrete_variables
from pyomo.core.base import active_components_data

import logging
logger = logging.getLogger('pyomo.solvers')

from six import iteritems, StringIO

try:
    unicode
except:
    basestring = str

class GUROBI(OptSolver):
    """The GUROBI LP/MIP solver
    """

    pyomo.util.plugin.alias('gurobi', doc='The GUROBI LP/MIP solver')

    def __new__(cls, *args, **kwds):
        try:
            mode = kwds['solver_io']
            if mode is None:
                mode = 'lp'
            del kwds['solver_io']
        except KeyError:
            mode = 'lp'
        #
        if mode  == 'lp':
            return SolverFactory('_gurobi_shell', **kwds)
        if mode == 'python':
            opt = SolverFactory('_gurobi_direct', **kwds)
            if opt is None:
                logger.error('Python API for GUROBI is not installed')
                return
            return opt
        #
        if mode == 'os':
            opt = SolverFactory('_ossolver', **kwds)
        elif mode == 'nl':
            opt = SolverFactory('asl', **kwds)
        else:
            logger.error('Unknown IO type: %s' % mode)
            return
        opt.set_options('solver=gurobi')
        return opt


class GUROBISHELL(ILMLicensedSystemCallSolver):
    """Shell interface to the GUROBI LP/MIP solver
    """

    pyomo.util.plugin.alias('_gurobi_shell',  doc='Shell interface to the GUROBI LP/MIP solver')

    def __init__(self, **kwds):
        #
        # Call base class constructor
        #
        kwds['type'] = 'gurobi'
        ILMLicensedSystemCallSolver.__init__(self, **kwds)

        # NOTE: eventually both of the following attributes should be migrated to a common base class.
        # is the current solve warm-started? a transient data member to communicate state information
        # across the _presolve, _apply_solver, and _postsolve methods.
        self.warm_start_solve = False
        # related to the above, the temporary name of the MST warm-start file (if any).
        self.warm_start_file_name = None

        #
        # Define valid problem formats and associated results formats
        #
        self._valid_problem_formats=[ProblemFormat.cpxlp, ProblemFormat.mps]
        self._valid_result_formats={}
        self._valid_result_formats[ProblemFormat.cpxlp] = [ResultsFormat.soln]
        self._valid_result_formats[ProblemFormat.mps] = [ResultsFormat.soln]
        self.set_problem_format(ProblemFormat.cpxlp)

        # Note: Undefined capabilities default to 'None'
        self._capabilities = pyutilib.misc.Options()
        self._capabilities.linear = True
        self._capabilities.quadratic_objective = True
        self._capabilities.quadratic_constraint = True
        self._capabilities.integer = True
        self._capabilities.sos1 = True
        self._capabilities.sos2 = True

    def _default_results_format(self, prob_format):
        return ResultsFormat.soln

    def warm_start_capable(self):
        return True

    #
    # write a warm-start file in the GUROBI MST format, which is *not* the same as the CPLEX MST format.
    #
    def warm_start(self, instance):

        from pyomo.core.base import Var

        mst_file = open(self.warm_start_file_name,'w')

        # for each variable in the symbol_map, add a child to the
        # variables element.  Both continuous and discrete are accepted
        # (and required, depending on other options), according to the
        # CPLEX manual.
        # **Note**: This assumes that the symbol_map is "clean", i.e., 
        # contains only references to the variables encountered in constraints
        output_index = 0
        byObject = self._symbol_map.byObject
        for block in instance.all_blocks():
            for var in active_components_data(block, Var):
                if (var.value is not None) and (id(var) in byObject):
                    name = byObject[id(var)]
                    mst_file.write("%s %s\n" % (name, str(var.value)))

        mst_file.close()

    # over-ride presolve to extract the warm-start keyword, if specified.
    def _presolve(self, *args, **kwds):

        # create a context in the temporary file manager for 
        # this plugin - is "pop"ed in the _postsolve method.
        pyutilib.services.TempfileManager.push()

        # if the first argument is a string (representing a filename),
        # then we don't have an instance => the solver is being applied
        # to a file.
        self.warm_start_solve = kwds.pop( 'warmstart', False )
        self.warm_start_file_name = None

        # the input argument can currently be one of two things: an instance or a filename.
        # if a filename is provided and a warm-start is indicated, we go ahead and
        # create the temporary file - assuming that the user has already, via some external
        # mechanism, invoked warm_start() with a instance to create the warm start file.
        if (self.warm_start_solve is True) and (isinstance(args[0],basestring) is True):
            pass # we assume the user knows what they are doing...
        elif (self.warm_start_solve is True) and (isinstance(args[0], basestring) is False):
           # assign the name of the warm start file *before* calling the base class
           # presolve - the base class method ends up creating the command line,
           # and the warm start file-name is (obviously) needed there.
           self.warm_start_file_name = pyutilib.services.TempfileManager.create_tempfile(suffix = '.gurobi.mst')

        # let the base class handle any remaining keywords/actions.
        ILMLicensedSystemCallSolver._presolve(self, *args, **kwds)

        # NB: we must let the base class presolve run first so that the
        # symbol_map is actually constructed!

        if (len(args) > 0) and (isinstance(args[0],basestring) is False):

            # write the warm-start file - currently only supports MIPs.
            # we only know how to deal with a single problem instance.
            if self.warm_start_solve is True:

                if len(args) != 1:
                    raise ValueError(
                        "GUROBI _presolve method can only handle a single "
                        "problem instance - %s were supplied" % (len(args),))

                start_time = time.time()
                self.warm_start(args[0])
                end_time = time.time()
                if self._report_timing is True:
                    print("Warm start write time=%.2f seconds" % (end_time-start_time))

    def executable(self):

        if sys.platform == 'win32':
            executable = pyutilib.services.registered_executable("gurobi.bat")
        else:
            executable = pyutilib.services.registered_executable("gurobi.sh")
        if executable is None:
            logger.warning("Could not locate the 'gurobi' executable, which is required for solver %s" % self.name)
            self.enable = False
            return None
        return executable.get_path()

    def version(self):
        """
        Returns a tuple describing the solver executable version.
        """
        solver_exec = self.executable()
        if solver_exec is None:
            return _extract_version('')
        outname = pyutilib.services.TempfileManager.create_tempfile(suffix = '.gurobi.version')
        with open(outname,'w') as f:
            # **Note, adding a 'timelimit' keyword here results in empty output for some reason
            results = pyutilib.subprocess.run( [solver_exec], stdin='from gurobipy import *; print(gurobi.version()); exit()', ostream=f) 
        tmp = None
        try:
            with open(outname,'r') as f:
                tmp = tuple(eval(f.read().strip()))
            while(len(tmp) < 4):
                tmp += (0,)
        except SyntaxError:
            tmp = None
        if tmp is None:
            return _extract_version('')
        
        return tmp[:4]

    def create_command_line(self,executable,problem_files):

        #
        # Define log file
        # The log file in CPLEX contains the solution trace, but the solver status can be found in the solution file.
        #
        self.log_file = pyutilib.services.TempfileManager.create_tempfile(suffix = '.gurobi.log')

        #
        # Define solution file
        # As indicated above, contains (in XML) both the solution and solver status.
        #
        self.soln_file = pyutilib.services.TempfileManager.create_tempfile(suffix = '.gurobi.txt')
        self.results_file = self.soln_file

        #
        # Write the GUROBI execution script
        #

        problem_filename = self._problem_files[0]
        solution_filename = self.soln_file
        warmstart_filename = self.warm_start_file_name
        if sys.platform == 'win32':
            problem_filename  = problem_filename.replace('\\', r'\\')
            solution_filename = solution_filename.replace('\\', r'\\')
            if self.warm_start_solve is True:
                warmstart_filename = warmstart_filename.replace('\\', r'\\')

        # translate the options into a normal python dictionary, from a
        # pyutilib SectionWrapper - the
        # gurobi_run function doesn't know about pyomo, so the translation
        # is necessary.
        options_dict = {}
        for key in self.options:
            options_dict[key] = self.options[key]

        # NOTE: the gurobi shell is independent of Pyomo python virtualized environment, so any
        #       imports - specifically that required to get GUROBI_RUN - must be handled explicitly.
        # NOTE: The gurobi plugin (GUROBI.py) and GUROBI_RUN.py live in the same directory.
        script  = "import sys\n"
        script += "from gurobipy import *\n"
        script += "sys.path.append('%s')\n" % os.path.dirname(__file__)
        script += "from GUROBI_RUN import *\n"
        script += "gurobi_run%s\n" % str((problem_filename, warmstart_filename, solution_filename, self.options.mipgap, options_dict, self.suffixes))
        script += "quit()\n"

        # dump the script and warm-start file names for the
        # user if we're keeping files around.
        if self.keepfiles:
            script_fname = pyutilib.services.TempfileManager.create_tempfile(suffix = '.gurobi.script')
            script_file = open(script_fname, 'w')
            script_file.write( script )
            script_file.close()

            print("Solver script file: '%s'" % script_fname)
            if (self.warm_start_solve is True) and (self.warm_start_file_name is not None):
                print("Solver warm-start file: " + self.warm_start_file_name)

        #
        # Define command line
        #
        cmd = [executable]
        if self._timer:
            cmd.insert(0, self._timer)
        return pyutilib.misc.Bunch( cmd=cmd, script=script, 
                                    log_file=self.log_file, env=None )

    def process_logfile(self):

        return ILMLicensedSystemCallSolver.process_logfile(self)

    def process_soln_file(self,results):


        # the only suffixes that we extract from CPLEX are
        # constraint duals, constraint slacks, and variable
        # reduced-costs. scan through the solver suffix list
        # and throw an exception if the user has specified
        # any others.
        extract_duals = False
        extract_slacks = False
        extract_rc = False
        for suffix in self.suffixes:
            flag=False
            if re.match(suffix,"dual"):
                extract_duals = True
                flag=True
            if re.match(suffix,"slack"):
                extract_slacks = True
                flag=True
            if re.match(suffix,"rc"):
                extract_rc = True
                flag=True
            if not flag:
                raise RuntimeError("***The GUROBI solver plugin cannot extract solution suffix="+suffix)

        # check for existence of the solution file
        # not sure why we just return - would think that we
        # would want to indicate some sort of error
        if not os.path.exists(self.soln_file):
            return

        soln = Solution()

        # caching for efficiency
        soln_variables = soln.variable
        soln_constraints = soln.constraint

        num_variables_read = 0

        # string compares are too expensive, so simply introduce some section IDs.
        # 0 - unknown
        # 1 - problem
        # 2 - solution
        # 3 - solver

        section = 0 # unknown

        solution_seen = False
        
        range_duals = {}
        range_slacks = {}

        INPUT = open(self.soln_file,"r")
        for line in INPUT:
            line = line.strip()
            tokens = [token.strip() for token in line.split(":")]
            if (tokens[0] == 'section'):
                if (tokens[1] == 'problem'):
                    section = 1
                elif (tokens[1] == 'solution'):
                    section = 2
                    solution_seen = True
                elif (tokens[1] == 'solver'):
                    section = 3
            else:
                if (section == 2):
                    if (tokens[0] == 'var'):
                        if tokens[1] != "ONE_VAR_CONSTANT":
                            soln_variables[tokens[1]] = {"Value" : float(tokens[2]), "Id" : num_variables_read}
                            num_variables_read += 1
                    elif (tokens[0] == 'status'):
                        soln.status = getattr(SolutionStatus, tokens[1])
                    elif (tokens[0] == 'gap'):
                        soln.gap = float(tokens[1])
                    elif (tokens[0] == 'objective'):
                        soln.objective['__default_objective__'].value=float(tokens[1])
                        if results.problem.sense == ProblemSense.minimize:
                            results.problem.upper_bound = float(tokens[1])
                        else:
                            results.problem.lower_bound = float(tokens[1])
                    elif (tokens[0] == 'constraintdual'):
                        name = tokens[1]
                        if name != "c_e_ONE_VAR_CONSTANT":
                            if name.startswith('c_'):
                                soln_constraints.setdefault(tokens[1],{"Id" : len(soln_constraints)})["Dual"] = float(tokens[2])
                            elif name.startswith('r_l_'):
                                range_duals.setdefault(name[4:],[0,0])[0] = float(tokens[2])
                            elif name.startswith('r_u_'):
                                range_duals.setdefault(name[4:],[0,0])[1] = float(tokens[2])
                    elif (tokens[0] == 'constraintslack'):
                        name = tokens[1]
                        if name != "c_e_ONE_VAR_CONSTANT":
                            if name.startswith('c_'):
                                soln_constraints.setdefault(tokens[1],{"Id" : len(soln_constraints)})["Slack"] = float(tokens[2])
                            elif name.startswith('r_l_'):
                                range_slacks.setdefault(name[4:],[0,0])[0] = float(tokens[2])
                            elif name.startswith('r_u_'):
                                range_slacks.setdefault(name[4:],[0,0])[1] = float(tokens[2])
                    elif (tokens[0] == 'varrc'):
                        if tokens[1] != "ONE_VAR_CONSTANT":
                            soln_variables[tokens[1]]["Rc"] = float(tokens[2])
                    else:
                        setattr(soln, tokens[0], tokens[1])
                elif (section == 1):
                    if tokens[0] == 'sense':
                        if tokens[1] == 'minimize':
                            results.problem.sense = ProblemSense.minimize
                        elif tokens[1] == 'maximize':
                            results.problem.sense = ProblemSense.maximize
                    else:
                        try:
                            val = eval(tokens[1])
                        except:
                            val = tokens[1]
                        setattr(results.problem, tokens[0], val)
                elif (section == 3):
                    if (tokens[0] == 'status'):
                        results.solver.status = getattr(SolverStatus, tokens[1])
                    elif (tokens[0] == 'termination_condition'):
                        try:
                            results.solver.termination_condition = getattr(TerminationCondition, tokens[1])
                        except AttributeError:
                            results.solver.termination_condition = TerminationCondition.unknown
                    else:
                        setattr(results.solver, tokens[0], tokens[1])

        INPUT.close()
        
        # For the range constraints, supply only the dual with the largest
        # magnitude (at least one should always be numerically zero)
        for key,(ld,ud) in iteritems(range_duals):
            if abs(ld) > abs(ud):
                soln_constraints['r_l_'+key] = {"Dual" : ld, "Id" : len(soln_constraints)}
            else:
                soln_constraints['r_u_'+key] = {"Dual" : ud, "Id" : len(soln_constraints)}
        # slacks
        for key,(ls,us) in iteritems(range_slacks):
            if abs(ls) > abs(us):
                soln_constraints.setdefault('r_l_'+key,{"Id" : len(soln_constraints)})["Slack"] = ls
            else:
                soln_constraints.setdefault('r_u_'+key,{"Id" : len(soln_constraints)})["Slack"] = us

        if solution_seen is True:
            results.solution.insert(soln)

    def _postsolve(self):

        # take care of the annoying GUROBI log file in the current directory.
        # this approach doesn't seem overly efficient, but python os module functions 
        # doesn't accept regular expression directly.
        filename_list = os.listdir(".")
        for filename in filename_list:
            # IMPT: trap the possible exception raised by the file not existing.
            #       this can occur in pyro environments where > 1 workers are
            #       running GUROBI, and were started from the same directory.
            #       these logs don't matter anyway (we redirect everything),
            #       and are largely an annoyance.
            try:
                if  re.match('gurobi\.log', filename) != None:
                    os.remove(filename)
            except OSError:
                pass

        # let the base class deal with returning results.
        results = ILMLicensedSystemCallSolver._postsolve(self)

        # finally, clean any temporary files registered with the temp file
        # manager, created populated *directly* by this plugin. does not
        # include, for example, the execution script. but does include 
        # the warm-start file. 
        pyutilib.services.TempfileManager.pop(remove=not self.keepfiles)

        return results

if sys.platform == 'win32':
    pyutilib.services.register_executable(name='gurobi.bat')
else:
    pyutilib.services.register_executable(name='gurobi.sh')