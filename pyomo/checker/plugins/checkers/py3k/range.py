import ast
from pyomo.checker.plugins.checker import IterativeTreeChecker


class XRange(IterativeTreeChecker):
    def check(self, runner, script, info):
        if isinstance(info, ast.Name):
            if info.id == 'xrange':
                self.problem("'xrange' function was removed in Python 3.")

    def checkerDoc(self):
        return """\
        In Python 3, 'xrange' was removed in favor of 'range', which was
        reimplemented more efficiently. Please change your uses of 'xrange'
        into 'range', e.g.:
            xrange(1,10)       =>       range(1,10)
        """