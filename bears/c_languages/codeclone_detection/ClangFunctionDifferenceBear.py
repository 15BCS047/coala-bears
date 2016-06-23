import functools
from itertools import combinations

from bears.c_languages.ClangBear import clang_available, ClangBear
from bears.c_languages.codeclone_detection.ClangCountingConditions import (
    condition_dict)
from bears.c_languages.codeclone_detection.ClangCountVectorCreator import (
    ClangCountVectorCreator)
from bears.c_languages.codeclone_detection.CloneDetectionRoutines import (
    compare_functions, get_count_matrices)
from coalib.bears.GlobalBear import GlobalBear
from coalib.collecting.Collectors import collect_dirs
from coalib.misc.StringConverter import StringConverter
from coalib.results.HiddenResult import HiddenResult
from coalib.settings.Setting import path_list, typed_ordered_dict

# counting_condition_dict is a function object generated by typed_dict. This
# function takes a setting and creates a dictionary out of it while it
# converts all keys to counting condition function objects (via the
# condition_dict) and all values to floats while unset values default to 1.
counting_condition_dict = typed_ordered_dict(
    lambda setting: condition_dict[str(setting).lower()],
    float,
    1)

default_cc_dict = counting_condition_dict(StringConverter(
    """
used: 0,
returned: 1.4,
is_condition: 0,
in_condition: 1.4,
in_second_level_condition: 1.4,
in_third_level_condition: 1.0,
is_assignee: 0,
is_assigner: 0.6,
loop_content: 0,
second_level_loop_content,
third_level_loop_content,
is_param: 2,
is_called: 1.4,
is_call_param: 0.0,
in_sum: 2.0,
in_product: 0,
in_binary_operation,
member_accessed"""))


def get_difference(function_pair,
                   count_matrices,
                   average_calculation,
                   poly_postprocessing,
                   exp_postprocessing):
    """
    Retrieves the difference between two functions using the munkres algorithm.

    :param function_pair:       A tuple containing both indices for the
                                count_matrices dictionary.
    :param count_matrices:      A dictionary holding CMs.
    :param average_calculation: If set to true the difference calculation
                                function will take the average of all variable
                                differences as the difference, else it will
                                normalize the function as a whole and thus
                                weighting in variables dependent on their size.
    :param poly_postprocessing: If set to true, the difference value of big
                                function pairs will be reduced using a
                                polynomial approach.
    :param exp_postprocessing:  If set to true, the difference value of big
                                function pairs will be reduced using an
                                exponential approach.
    :return:                    A tuple containing both function ids and their
                                difference.
    """
    function_1, function_2 = function_pair
    return (function_1,
            function_2,
            compare_functions(count_matrices[function_1],
                              count_matrices[function_2],
                              average_calculation,
                              poly_postprocessing,
                              exp_postprocessing))


class ClangFunctionDifferenceBear(GlobalBear):
    check_prerequisites = classmethod(clang_available)
    LANGUAGES = ClangBear.LANGUAGES
    REQUIREMENTS = ClangBear.REQUIREMENTS

    def run(self,
            counting_conditions: counting_condition_dict=default_cc_dict,
            average_calculation: bool=False,
            poly_postprocessing: bool=True,
            exp_postprocessing: bool=False,
            extra_include_paths: path_list=()):
        '''
        Retrieves similarities for code clone detection. Those can be reused in
        another bear to produce results.

        Postprocessing may be done because small functions are less likely to
        be clones at the same difference value than big functions which may
        provide a better refactoring opportunity for the user.

        :param counting_conditions: A comma seperated list of counting
                                    conditions. Possible values are: used,
                                    returned, is_condition, in_condition,
                                    in_second_level_condition,
                                    in_third_level_condition, is_assignee,
                                    is_assigner, loop_content,
                                    second_level_loop_content,
                                    third_level_loop_content, is_param,
                                    in_sum, in_product, in_binary_operation,
                                    member_accessed.
                                    Weightings can be assigned to each
                                    condition due to providing a dict
                                    value, i.e. having used weighted in
                                    half as much as other conditions would
                                    simply be: "used: 0.5, is_assignee".
                                    Weightings default to 1 if unset.
        :param average_calculation: If set to true the difference calculation
                                    function will take the average of all
                                    variable differences as the difference,
                                    else it will normalize the function as a
                                    whole and thus weighting in variables
                                    dependent on their size.
        :param poly_postprocessing: If set to true, the difference value of big
                                    function pairs will be reduced using a
                                    polynomial approach.
        :param extra_include_paths: A list containing additional include paths.
        :param exp_postprocessing:  If set to true, the difference value of big
                                    function pairs will be reduced using an
                                    exponential approach.
        '''
        self.debug("Using the following counting conditions:")
        for key, val in counting_conditions.items():
            self.debug(" *", key.__name__, "(weighting: {})".format(val))

        self.debug("Creating count matrices...")
        count_matrices = get_count_matrices(
            ClangCountVectorCreator(list(counting_conditions.keys()),
                                    list(counting_conditions.values())),
            list(self.file_dict.keys()),
            lambda prog: self.debug("{:2.4f}%...".format(prog)),
            self.section["files"].origin,
            collect_dirs(extra_include_paths))

        self.debug("Calculating differences...")

        differences = []
        function_count = len(count_matrices)
        # Thats n over 2, hardcoded to simplify calculation
        combination_length = function_count * (function_count-1) / 2
        partial_get_difference = functools.partial(
            get_difference,
            count_matrices=count_matrices,
            average_calculation=average_calculation,
            poly_postprocessing=poly_postprocessing,
            exp_postprocessing=exp_postprocessing)

        for i, elem in enumerate(
                map(partial_get_difference,
                    [(f1, f2) for f1, f2 in combinations(count_matrices, 2)])):
            if i % 50 == 0:
                self.debug("{:2.4f}%...".format(100*i/combination_length))
            differences.append(elem)

        yield HiddenResult(self, differences)
        yield HiddenResult(self, count_matrices)
