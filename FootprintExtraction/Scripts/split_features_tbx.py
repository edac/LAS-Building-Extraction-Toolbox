# -------------------------------------------------------------------------------
# Name:        split_features_tbx.py
# Purpose:     wrapper for split_features.py
#
# Author:      Gert van Maren
#
# Created:     04/12/2018
# Copyright:   (c) Esri 2018
# updated:
# updated:
# updated:

# Required:
#

# -------------------------------------------------------------------------------

import arcpy
import sys
import importlib
import os
import re
import split_features

if 'split_features' in sys.modules:
    importlib.reload(split_features)
import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)  # force reload of the module
import time
from common_lib import create_msg_body, msg, trace

# debugging switches
debugging = 0
if debugging == 1:
    enableLogging = True
    DeleteIntermediateData = False
    verbose = 1
    in_memory_switch = False
else:
    enableLogging = False
    DeleteIntermediateData = True
    verbose = 0
    in_memory_switch = False


# constants
TOOLNAME = "split_features"
WARNING = "warning"
ERROR = "error"


# error classes
class MoreThan1Selected(Exception):
    pass


class NoLayerFile(Exception):
    pass


class NoPointLayer(Exception):
    pass


class LicenseError3D(Exception):
    pass


class LicenseErrorSpatial(Exception):
    pass


class SchemaLock(Exception):
    pass


class NotSupported(Exception):
    pass


class FunctionError(Exception):

    """
    Raised when a function fails to run.
    """

    pass


# ----------------------------Main Function---------------------------- #

def main():
    try:
        # Get Attributes from User
        if debugging == 0:
            # User input
            input_layer = arcpy.GetParameter(0)
            split_layer = arcpy.GetParameter(1)
            minimum_area = arcpy.GetParameterAsText(2)
            output_name = arcpy.GetParameterAsText(3)

            # script variables
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            home_directory = aprx.homeFolder

        if os.path.exists(home_directory + "\\p20"):  # it is a package
            home_directory = home_directory + "\\p20"

        arcpy.AddMessage("Project Home Directory is: " + home_directory)

        # set directories
        layer_directory = home_directory + "\\layer_files"
        log_directory = home_directory + "\\Logs"
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)

        ##########  ensure numerical input is correct
        # fail safe for Europe's comma's
        minimum_area = float(re.sub("[,.]", ".", minimum_area))

        # rename layer files (for packaging)
        if os.path.exists(layer_directory):
            common_lib.rename_file_extension(layer_directory, ".txt", ".lyrx")

        ############# Create folders and intermediate gdb, if needed
        scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
        arcpy.env.workspace = scratch_ws
        arcpy.env.overwriteOutput = True

        start_time = time.clock()

        # check if input exists
        if arcpy.Exists(input_layer) and arcpy.Exists(split_layer):

            if common_lib.check_valid_input(input_layer, True, ["Polygon"], False, True):
                if common_lib.check_valid_input(split_layer, True, ["Polygon"], False, True):

                    # go to main function
                    out_put_features = split_features.split(scratch_ws=scratch_ws,
                                                                lc_input_features=input_layer,
                                                                lc_split_features=split_layer,
                                                                lc_minimum_area=minimum_area,
                                                                lc_output_name=output_name,
                                                                lc_debug=verbose,
                                                                lc_memory_switch=in_memory_switch)

                    if out_put_features:
                        if arcpy.Exists(out_put_features):

                            output_layer1 = common_lib.get_name_from_feature_class(out_put_features)
                            arcpy.MakeFeatureLayer_management(out_put_features, output_layer1)

                            arcpy.SetParameter(4, output_layer1)

                            end_time = time.clock()
                            msg_body = create_msg_body("split_features completed successfully.", start_time, end_time)
                            msg(msg_body)
                        else:
                            end_time = time.clock()
                            msg_body = create_msg_body("No split features created. Exiting...", start_time, end_time)
                            msg(msg_body, WARNING)

                    arcpy.ClearWorkspaceCache_management()

                    if DeleteIntermediateData:
                        fcs = common_lib.listFcsInGDB(scratch_ws)

                        msg_prefix = "Deleting intermediate data..."

                        msg_body = common_lib.create_msg_body(msg_prefix, 0, 0)
                        common_lib.msg(msg_body)

                        for fc in fcs:
                            arcpy.Delete_management(fc)

                    # end main code
                else:
                    arcpy.AddError("Input data is not valid. Check your data.")
            else:
                arcpy.AddError("Input data is not valid. Check your data.")

    except LicenseError3D:
        print("3D Analyst license is unavailable")
        arcpy.AddError("3D Analyst license is unavailable")

    except NoPointLayer:
        print("Can't find attachment points layer. Exiting...")
        arcpy.AddError("Can't find attachment points layer. Exiting...")

    except NoPointLayer:
        print("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")
        arcpy.AddError("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")

    except MoreThan1Selected:
        print("More than 1 line selected. Please select 1 guide line only. Exiting...")
        arcpy.AddError("More than 1 line selected. Please select 1 guide line only. Exiting...")

    except arcpy.ExecuteError:
        line, filename, synerror = trace()
        msg("Error on %s" % line, ERROR)
        msg("Error in file name:  %s" % filename, ERROR)
        msg("With error message:  %s" % synerror, ERROR)
        msg("ArcPy Error Message:  %s" % arcpy.GetMessages(2), ERROR)

    except FunctionError as f_e:
        messages = f_e.args[0]
        msg("Error in function:  %s" % messages["function"], ERROR)
        msg("Error on %s" % messages["line"], ERROR)
        msg("Error in file name:  %s" % messages["filename"], ERROR)
        msg("With error message:  %s" % messages["synerror"], ERROR)
        msg("ArcPy Error Message:  %s" % messages["arc"], ERROR)

    except:
        line, filename, synerror = trace()
        msg("Error on %s" % line, ERROR)
        msg("Error in file name:  %s" % filename, ERROR)
        msg("with error message:  %s" % synerror, ERROR)

    finally:
        arcpy.CheckInExtension("3D")

if __name__ == '__main__':

    main()
