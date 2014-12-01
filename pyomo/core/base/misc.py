#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008 Sandia Corporation.
#  This software is distributed under the BSD License.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  For more information, see the Pyomo README.txt file.
#  _________________________________________________________________________

__all__ = ['display']

import logging
import sys

from six import itervalues

logger = logging.getLogger('pyomo.core')


def display(obj, ostream=None):
    """ Display data in a Pyomo object"""
    if ostream is None:
        ostream = sys.stdout
    try:
        display_fcn = obj.display
    except AttributeError:
        raise TypeError(
            "Error trying to display values for object of type %s:\n"
            "\tObject does not support the 'display()' method"
            % (type(obj), ) )
    try:
        display_fcn(ostream=ostream)
    except Exception:
        err = sys.exc_info()[1]
        logger.error(
            "Error trying to display values for object of type %s:\n\t%s"
            % (type(obj), err) )
        raise 


def create_name(name, ndx):
    if ndx is None:
        return name
    if type(ndx) is tuple:
        tmp = str(ndx).replace(', ',',')
        return name+"["+tmp[1:-1]+"]"
    return name+"["+str(ndx)+"]"


def apply_indexed_rule(obj, rule, model, index, options=None):
    try:
        if options is None:
            if index.__class__ is tuple:
                return rule(model, *index)
            elif index is None:
                return rule(model)
            else:
                return rule(model, index)
        else:
            if index.__class__ is tuple:
                return rule(model, *index, **options)
            elif index is None:
                return rule(model, **options)
            else:
                return rule(model, index, **options)
    except TypeError:
        try:
            if options is None:
                return rule(model)
            else:
                return rule(model, **options)
        except:
            # Nothing appears to have matched... re-trigger the original
            # TypeError
            if options is None:
                if index.__class__ is tuple:
                    return rule(model, *index)
                elif index is None:
                    return rule(model)
                else:
                    return rule(model, index)
            else:
                if index.__class__ is tuple:
                    return rule(model, *index, **options)
                elif index is None:
                    return rule(model, **options)
                else:
                    return rule(model, index, **options)

def apply_parameterized_indexed_rule(obj, rule, model, param, index):
    if index.__class__ is tuple:
        return rule(model, param, *index)
    if index is None:
        return rule(model, param)
    return rule(model, param, index)

def _safe_to_str(obj):
    try:
        return str(obj)
    except:
        return "None"

def tabular_writer(ostream, prefix, data, header, row_generator):
    _rows = {}
    #_header = ("Key","Initial Value","Lower Bound","Upper Bound",
    #           "Current Value","Fixed","Stale")
    # NB: _width is a list because we will change these values
    if header:
        _width = [len(x) for x in header]
    else:
        _width = None

    for _key, _val in data:
        try:
            _rows[_key] = tuple( _safe_to_str(x) 
                                 for x in row_generator(_key, _val) )
        except:
            _rows[_key] = None
            continue

        if not _width:
            _width = [0]*len(_rows[_key])
        for _id, x in enumerate(_rows[_key]):
            _width[_id] = max(_width[_id], len(x))

    # NB: left-justify header
    if header:
        # Note: do not right-pad the last header with unnecessary spaces
        tmp = _width[-1]
        _width[-1] = 0
        ostream.write(prefix
                      + " : ".join( "%%-%ds" % _width[i] % x 
                                    for i,x in enumerate(header) )
                      + "\n")
        _width[-1] = tmp

    # If there is no data, we are done...
    if not _rows:
        return

    # right-justify data, except for the last column if there are spaces
    # in the data (probably an expression or vector)
    _width = ["%"+str(i)+"s" for i in _width]

    if sum(1 for x in itervalues(_rows) if x is not None and ' ' in x[-1]):
        _width[-1] = '%s'
    for _key in sorted(_rows):
        _data = _rows[_key]
        if not _data:
            _data = [_key] + [None]*(len(_width)-1)
        ostream.write(prefix
                      + " : ".join( _width[i] % x for i,x in enumerate(_data) )
                      + "\n")
