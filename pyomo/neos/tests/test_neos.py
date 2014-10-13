#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008 Sandia Corporation.
#  This software is distributed under the BSD License.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  For more information, see the FAST README.txt file.
#  _________________________________________________________________________

#
# Test NEOS solver interface
#

try:
    import new
except:
    import types as new
import os
import sys
import unittest
from os.path import abspath, dirname, normpath, join

currdir = dirname(abspath(__file__))

from six import iteritems
import re
import pyutilib.services
import pyutilib.subprocess
import pyutilib.common
import pyutilib.th as unittest
from pyutilib.misc import setup_redirect, reset_redirect
try:
    import yaml
    yaml_available=True
except ImportError:
    yaml_available=False

import pyomo.environ
import pyomo.opt
import pyomo.scripting.pyomo_command as main
from pyomo.scripting.util import cleanup
from pyomo.util.plugin import ExtensionPoint
from pyomo.core import *

from pyomo.neos.kestrel import kestrelAMPL
try:
    kestrel = kestrelAMPL()
except:
    kestrel = None
if kestrel is None or kestrel.neos is None:
    using_neos = False
else:
    using_neos = True
kestrel = None


class CommonTests:

    def pyomo(self, *args, **kwds):
        args=list(args)
        args.append('--solver-manager=neos')
        args.append('-c')
        if 'solver' in kwds:
            args.append('--solver='+kwds['solver'])
        args.append('--symbolic-solver-labels')
        args.append('--save-results=result.yml')
        #args.append('--tempdir='+currdir)
        #args.append('--keepfiles')
        #args.append('--debug')
        #args.append('--verbose')
        os.chdir(currdir)

        print('***')
        print(' '.join(args))
        try:
            output = main.run(args)
        except:
            output = None
        cleanup()
        print('***')
        return output

    def check(self, problem, solver):
        pass


class Solver(unittest.TestCase):

    def referenceFile(self, problem, solver):
        return join(currdir, problem+'.txt')

    def getObjective(self, fname):
        FILE = open(fname)
        data = yaml.load(FILE)
        FILE.close()
        solutions = data.get('Solution', [])
        ans = []
        for x in solutions:
            ans.append(x.get('Objective', {}))
        return ans

    def check(self, problem, solver):
        refObj = self.getObjective(self.referenceFile(problem,solver))
        ansObj = self.getObjective(join(currdir,'result.yml'))
        self.assertEqual(len(refObj), len(ansObj))
        for i in range(len(refObj)):
            self.assertEqual(len(refObj[i]), len(ansObj[i]))
            for key,val in iteritems(refObj[i]):
                self.assertEqual(val, ansObj[i].get(key,None))


@unittest.category('expensive')
@unittest.skipIf(not yaml_available, "YAML is not available")
@unittest.skipIf(not using_neos, "NEOS is not available")
class Solve_CBC(Solver, CommonTests):

    def pyomo(self,  *args, **kwds):
        kwds['solver'] = 'cbc'
        return CommonTests.pyomo(self, *args, **kwds)

    def test_t1(self):
        self.problem='test_t1'
        self.pyomo( join(currdir,'t1.py') )
        self.check( 't1', 'linear_dual' )


@unittest.category('expensive')
@unittest.skipIf(not using_neos, "NEOS is not available")
class Misc(unittest.TestCase, CommonTests):

    def test_bad_solver(self):
        self.problem='test_t1'
        ans = self.pyomo( join(currdir,'t1.py'), solver='foo')
        if not ans is None:
            self.fail("Expected failure because solver is not defined.")




if __name__ == "__main__":
    unittest.main()
