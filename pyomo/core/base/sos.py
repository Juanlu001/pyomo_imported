#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

__all__ = ['SOSConstraint']

import weakref
import sys
import logging
import six
from six.moves import zip

from pyomo.core.base.component import ActiveComponentData, register_component
from pyomo.core.base.indexed_component import ActiveIndexedComponent
from pyomo.core.base.set_types import PositiveIntegers
from pyomo.core.base.sets import Set

logger = logging.getLogger('pyomo.core')
weakref_ref = weakref.ref


class _SOSConstraintData(ActiveComponentData): 
    """
    This class defines the data for a single special ordered set.

    Constructor arguments:
        owner           The Constraint object that owns this data.

    Public class attributes:
        active          A boolean that is true if this objective is active in the model.
        component       The constraint component.

    Private class attributes:
        _variables       SOS variables.
        _weights         SOS variable weights.
        _level           SOS level (Positive Integer)
    """

    __pickle_slots__ = ( '_variables', '_weights', '_level')
    __slots__ = __pickle_slots__ + ( '__weakref__', )

    def __init__(self, owner):
        """ Constructor """
        self._level = None
        self._variables = {}
        self._weights = {}
        ActiveComponentData.__init__(self, owner)

    def __getstate__(self):
        """
        This method must be defined because this class uses slots.
        """
        result = super(_SOSConstraintData, self).__getstate__()
        for i in _SOSConstraintData.__pickle_slots__:
            result[i] = getattr(self, i)
        return result

    # Since this class requires no special processing of the state
    # dictionary, it does not need to implement __setstate__()

    def num_variables(self):
        return len(self._variables)

    @property
    def level(self):
        """
        Return the SOS level
        """
        return self._level

    @level.setter
    def level(self, level):
        if level not in PositiveIntegers:
            raise ValueError("SOS Constraint level must be a positive integer")
        self._level = level

    def get_variables(self):
        for val in six.itervalues(self._variables):
            yield val()

    def get_items(self):
        assert len(self._variables) == len(self._weights)
        for id_ in self._variables:
            yield self._variables[id_](), self._weights[id_]

    def set_variable(self, vardata, weight=None):
        if weight is None:
            if len(self._weights) == 0:
                weight = 1
            else:
                weight = max(self._weights)+1
        #
        idx = id(vardata)
        self._variables[idx] = weakref_ref(vardata)
        self._weights[idx] = weight

    def remove_variable(self, vardata):
        idx = id(vardata)
        if not idx in self._variables:
            raise ValueError("Variable '%s' is not a variable in SOSConstraint '%s'" \
                                 % (vardata.cname(True), self.cname(True)))
        del self._variables[idx]
        del self._weights[idx]


class SOSConstraint(ActiveIndexedComponent):
    """
    Represents an SOS-n constraint.

    Usage:
    model.C1 = SOSConstraint(
                             [...],
                             var=VAR,
                             [set=SET OR index=SET],
                             [sos=N OR level=N]
                             [weights=WEIGHTS]
                             )
        [...]   Any number of sets used to index SET
        VAR     The set of variables making up the SOS. Indexed by SET.
        SET     The set used to index VAR. SET is optionally indexed by
                the [...] sets. If SET is not specified, VAR is indexed
                over the set(s) it was defined with.
        N       This constraint is an SOS-N constraint. Defaults to 1.
        WEIGHTS A Param representing the variables weights in the SOS sets.
                A simple counter is used to generate weights when this keyword
                is not used.

    Example:

      model = AbstractModel()
      model.A = Set()
      model.B = Set(A)
      model.X = Set(B)

      model.C1 = SOSConstraint(model.A, var=model.X, set=model.B, sos=1)

    This constraint actually creates one SOS-1 constraint for each
    element of model.A (e.g., if |A| == N, there are N constraints).
    In each constraint, model.X is indexed by the elements of
    model.B[a], where 'a' is the current index of model.A.

      model = AbstractModel()
      model.A = Set()
      model.X = Var(model.A)

      model.C2 = SOSConstraint(var=model.X, sos=2)

    This produces exactly one SOS-2 constraint using all the variables
    in model.X.
    """

    def __new__(cls, *args, **kwds):
        if cls != SOSConstraint:
            return super(SOSConstraint, cls).__new__(cls)
        if args == ():
            return SimpleSOSConstraint.__new__(SimpleSOSConstraint)
        else:
            return IndexedSOSConstraint.__new__(IndexedSOSConstraint)

    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        #
        # The 'var' argument
        #
        sosVars = kwargs.pop('var', None)
        if sosVars is None:
            raise TypeError("SOSConstraint() requires the 'var' keyword " \
                  "be specified")
        #
        # The 'weights' argument
        #
        sosWeights = kwargs.pop('weights', None)
        #
        # The 'index' argument
        #
        sosSet = kwargs.pop('index', None)
        #
        # The 'sos' or 'level' argument
        #
        if 'sos' in kwargs and 'level' in kwargs:
            raise TypeError("Specify only one of 'sos' and 'level' -- " \
                  "they are equivalent keyword arguments")
        sosLevel = kwargs.pop('sos', None)
        sosLevel = kwargs.pop('level', sosLevel)
        if sosLevel is None:
            raise TypeError("SOSConstraint() requires that either the " \
                  "'sos' or 'level' keyword arguments be set to indicate " \
                  "the type of SOS.")
        #
        # Set attributes
        #
        self._sosVars = sosVars
        self._sosWeights = sosWeights
        self._sosSet = sosSet
        self._sosLevel = sosLevel
        #
        # Construct the base class
        #
        kwargs.setdefault('ctype', SOSConstraint)
        ActiveIndexedComponent.__init__(self, *args, **kwargs)

    def construct(self, data=None):
        """
        Construct this component
        """
        assert data is None # because I don't know why it's an argument
        generate_debug_messages = __debug__ and logger.isEnabledFor(logging.DEBUG)

        if generate_debug_messages:     #pragma:nocover
            logger.debug("Constructing SOSConstraint %s",self.cname(True))

        if self._constructed is True:   #pragma:nocover
            return
        self._constructed = True

        for index in self._index:
            if generate_debug_messages:     #pragma:nocover
                logger.debug("  Constructing "+self.cname(True)+" index "+str(index))
            self.add(index)

    def add(self, index):
        """
        Add a component data for the specified index.
        """
        if index is None:
            # because SimpleSOSConstraint already makes an _SOSConstraintData instance
            soscondata = self
        else:
            soscondata = _SOSConstraintData(self)

        soscondata.level = self._sosLevel

        if (self._sosSet is None):
            sosSet = self._sosVars.index_set()
        else:
            if index is None:
                sosSet = self._sosSet
            else:
                sosSet = self._sosSet[index]

        weights = None
        if index is None:
            vars = [self._sosVars[idx] for idx in sosSet]
            if self._sosWeights is not None:
                weights = [self._sosWeights[idx] for idx in sosSet]
            else:
                # WEH - Using range seems a lot simpler.
                #weights = list(i for i,idx in enumerate(sosSet,1))
                weights = list(range(1,len(vars)+1))
        else:
            vars = [self._sosVars[idx] for idx in sosSet]
            if self._sosWeights is not None:
                weights = [self._sosWeights[idx] for idx in sosSet]
            else:
                # WEH - Using range seems a lot simpler.
                #weights = list(i for i,idx in enumerate(sosSet,1))
                weights = list(range(1,len(vars)+1))

        for var, weight in zip(vars,weights):
            soscondata.set_variable(var, weight)

        self._data[index] = soscondata

    # NOTE: the prefix option is ignored
    def pprint(self, ostream=None, verbose=False, prefix=""):
        """TODO"""
        if ostream is None:
            ostream = sys.stdout
        ostream.write("   "+self.cname()+" : ")
        if not self.doc is None:
            ostream.write(self.doc+'\n')
            ostream.write("  ")
        ostream.write("\tSize="+str(len(self._data.keys()))+' ')
        if isinstance(self._index,Set):
            ostream.write("\tIndex= "+self._index.cname(True)+'\n')
        else:
            ostream.write("\n")
        for val in self._data:
            if not val is None:
                ostream.write("\t"+str(val)+'\n')
            ostream.write("\t\tType="+str(self._data[val].level)+'\n')
            ostream.write("\t\tWeight : Variable\n")
            for var, weight in self._data[val].get_items():
                ostream.write("\t\t"+str(weight)+' : '+var.cname(True)+'\n')


# Since this class derives from Component and Component.__getstate__
# just packs up the entire __dict__ into the state dict, there s
# nothing special that we need to do here.  We will just defer to the
# super() get/set state.  Since all of our get/set state methods
# rely on super() to traverse the MRO, this will automatically pick
# up both the Component and Data base classes.

class SimpleSOSConstraint(SOSConstraint, _SOSConstraintData):

    def __init__(self, *args, **kwd):
        _SOSConstraintData.__init__(self, self)
        SOSConstraint.__init__(self, *args, **kwd)


class IndexedSOSConstraint(SOSConstraint):

    def __init__(self, *args, **kwds):
        super(IndexedSOSConstraint,self).__init__(*args, **kwds)


register_component(SOSConstraint, "SOS constraint expressions.")

