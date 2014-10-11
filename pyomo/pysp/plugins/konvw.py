import logging
from math import fabs

import pyomo.util.plugin
from pyomo.pysp import phextension
from pyomo.pysp.generators import scenario_tree_node_variables_generator_noinstances
from pyomo.pysp.phutils import indexToString

from operator import itemgetter

from pyomo.pysp.plugins.phboundextension import _PHBoundBase

logger = logging.getLogger('pyomo.pysp')


class phweightinspectextension(pyomo.util.plugin.SingletonPlugin, _PHBoundBase):

    pyomo.util.plugin.implements(phextension.IPHExtension)

    pyomo.util.plugin.alias("phweightinspectextension")

    def __init__(self):

        _PHBoundBase.__init__(self)
        self.wonly_file = "wonly.ssv"
        print ("konvw is creating W-only convergence file="+self.wonly_file)
        ofile = open(self.wonly_file, 'w')
        ofile.close()
        self._valid_weights_objective_relative_tolerance = 0.01

    def _inspect_variable_convergence(self, ph, ph_iter):

        # collect termdiff by node and variable so we can
        # report and possibly sort
        term_diff = dict((tree_node._name, {}) \
                         for stage in ph._scenario_tree._stages[:-1]
                         for tree_node in stage._tree_nodes)

        # Track these for reporting purposes
        node_fixed_cnt = dict((tree_node._name, 0) \
                              for stage in ph._scenario_tree._stages[:-1]
                              for tree_node in stage._tree_nodes)
        total_fixed_cnt = 0

        for stage, tree_node, variable_id, variable_values, is_fixed, is_stale \
            in scenario_tree_node_variables_generator_noinstances(
                ph._scenario_tree,
                includeDerivedVariables=False,
                includeLastStage=False):

            if is_fixed:
                node_fixed_cnt[tree_node._name] += 1
                total_fixed_cnt += 1

            # Depending on preprocessing options, stale may indicate
            # fixed or unused in the model, either way we can skip it
            if (not is_stale):

                var_node_avg = 0.0
                for var_value, scenario_probability in variable_values:
                    var_node_avg += scenario_probability * var_value

                var_term_diff = 0.0
                for var_value, scenario_probability in variable_values:
                    var_term_diff += \
                        scenario_probability * \
                        fabs(var_value - var_node_avg)

                term_diff[tree_node._name][variable_id] = var_term_diff


        # Print individual variable term diffs by node
        # and sorted highest to lowest
        # skip the leaf stage
        ofile = open(self.wonly_file, 'a')
        for stage in ph._scenario_tree._stages[:-1]:

            for tree_node in stage._tree_nodes:

                for variable_id, var_term_diff in sorted(term_diff[tree_node._name].items(),
                                                         key=itemgetter(1),
                                                         reverse=True):
                    variable_name, index = tree_node._variable_ids[variable_id]
                    ofile.write(str(ph_iter)+"; "+tree_node._name+"; "+variable_name+indexToString(index)+"; "+str(var_term_diff)+'\n')
        ofile.close()

    def _iteration_k_solves(self,ph, storage_key):

        # Caching the current set of ph solutions so we can restore
        # the original results. We modify the scenarios and re-solve -
        # which messes up the warm-start, which can seriously impact
        # the performance of PH. plus, we don't want lower bounding to
        # impact the primal PH in any way - it should be free of any
        # side effects.
        self.CachePHSolution(ph)

        #
        #
        #
        #
        # **** NOTE WE ARE LEAVING VARIABLES FIXED FOR NOW ****
        #            THIS IS STILL EXPERIMENTAL
        #
        #
        #

        # Assuming the weight terms are already active but proximal
        # terms need to be deactivated deactivate all proximal terms
        # and activate all weight terms
        self.DeactivatePHObjectiveProximalTerms(ph)

        # Weights have not been pushed to instance parameters (or
        # transmitted to the phsolverservers) at this point
        ph._push_w_to_instances()

        ph.solve_subproblems(warmstart=not ph._disable_warmstarts)

        print("Successfully completed PH weight inspection extension "
              "iteration %s solves\n"
              "- solution statistics:\n" % (storage_key))
        if ph._scenario_tree.contains_bundles():
            ph._report_bundle_objectives()
        ph._report_scenario_objectives()

        weight_only_ph_objective = {}
        for scenario in ph._scenario_tree._scenarios:
            weight_only_ph_objective[scenario._name] = scenario._objective

        #
        # Fix variables to XBAR and solve again
        #

        self.FixPHVariablesToXbar(ph)

        ph.solve_subproblems(warmstart=not ph._disable_warmstarts)

        print("Successfully completed PH weight inspection extension "
              "iteration %s solves (FIXED TO XBAR)\n"
              "- solution statistics:\n" % (storage_key))
        if ph._scenario_tree.contains_bundles():
            ph._report_bundle_objectives()
        ph._report_scenario_objectives()

        fixed_xbar_ph_objective = {}
        for scenario in ph._scenario_tree._scenarios:
            fixed_xbar_ph_objective[scenario._name] = scenario._objective

        print("")
        print("Weight Inspection Results: (Using relative tolerance: "+repr(self._valid_weights_objective_relative_tolerance)+")")
        failure = False
        for scenario in ph._scenario_tree._scenarios:
            error = fabs(fixed_xbar_ph_objective[scenario._name] - \
                         weight_only_ph_objective[scenario._name]) / fabs(fixed_xbar_ph_objective[scenario._name])
            if error > self._valid_weights_objective_relative_tolerance:
                print("\t"+str(scenario._name)+": FAIL (relative error: "+repr(error)+")")
                failure = True
            else:
                print("\t"+str(scenario._name)+": OKAY (relative error: "+repr(error)+")")
        if failure:
            print("******************************")
            print("  Weight Inspection Failed!   ")
            print("******************************")
        else:
            print("")
            print("Weight Inspection Okay")
            print("")
        print("")
        self._inspect_variable_convergence(ph, storage_key)

        # Restore ph to its state prior to entering this method
        # (e.g., fixed variables, scenario solutions, proximal terms)
        self.RestorePH(ph)

    ############ Begin Callback Functions ##############

    def pre_ph_initialization(self,ph):
        """
        Called before PH initialization.
        """
        pass

    def post_instance_creation(self, ph):
        """
        Called after PH initialization has created the scenario
        instances, but before any PH-related
        weights/variables/parameters/etc are defined!
        """
        pass

    def post_ph_initialization(self, ph):
        """
        Called after PH initialization
        """

        if ph._verbose:
            print("Invoking post initialization callback in phboundextension")

    def post_iteration_0_solves(self, ph):
        """
        Called after the iteration 0 solves
        """
        pass

    def post_iteration_0(self, ph):
        """
        Called after the iteration 0 solves, averages computation, and weight computation
        """
        pass

    def pre_iteration_k_solves(self, ph):
        """
        Called immediately before the iteration k solves
        """
        pass

    def post_iteration_k_solves(self, ph):
        """
        Called after the iteration k solves!
        """
        pass

    def post_iteration_k(self, ph):
        """
        Called after the iteration k is finished, after weights have been updated!
        """
        if ph._verbose:
            print("Invoking post iteration k callback in phboundextension")

        if ph._converger.isConverged(ph):
            ph_iter = ph._current_iteration
            self._iteration_k_solves(ph, ph_iter)

    def post_ph_execution(self, ph):
        """
        Called after PH has terminated!
        """
        pass

