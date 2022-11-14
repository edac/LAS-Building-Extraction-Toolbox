# -------------------------------------------------------------------------------
# Name:        merge_features_tbx.py
# Purpose:     wrapper for merge_features.py
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
import merge_features
import common_lib
import time
from common_lib import create_msg_body, msg, trace

UPDATE_STATUS_FIELD = "Update_Status"

if 'merge_features' in sys.modules:
    importlib.reload(merge_features)

if 'common_lib' in sys.modules:
    importlib.reload(common_lib)  # force reload of the module

enableLogging = False
DeleteIntermediateData = True
verbose = 0
in_memory_switch = False

# constants
TOOLNAME = "merge_features"
WARNING = "warning"
ERROR = "error"


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
            # User input
        input_layer = arcpy.GetParameter(0)
        merge_layer = arcpy.GetParameter(1)
        output_name = arcpy.GetParameterAsText(2)

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

        # rename layer files (for packaging)
        if os.path.exists(layer_directory):
            common_lib.rename_file_extension(layer_directory, ".txt", ".lyrx")

        # Create folders and intermediate gdb, if needed
        scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")

        start_time = time.clock()

        # check if input exists
        if arcpy.Exists(input_layer) and arcpy.Exists(merge_layer):

            # check update attribute in merge layer
            if common_lib.check_fields(merge_layer, [UPDATE_STATUS_FIELD], True, verbose) == 1:
                msg_body = create_msg_body("Merging all features.", 0, 0)
                msg(msg_body, WARNING)
            else:
                msg_body = create_msg_body("Merging new and modified features.", 0, 0)
                msg(msg_body)

            # copy in case layers because layers always fail later on.
            copy_input_layer = os.path.join(scratch_ws, "copy_input_layer")
            if arcpy.Exists(copy_input_layer):
                arcpy.Delete_management(copy_input_layer)

            arcpy.CopyFeatures_management(input_layer, copy_input_layer)

            copy_merge_layer = os.path.join(scratch_ws, "copy_merge_layer")
            if arcpy.Exists(copy_merge_layer):
                arcpy.Delete_management(copy_merge_layer)

            arcpy.CopyFeatures_management(merge_layer, copy_merge_layer)

            # go to main function
            out_put_features, points = merge_features.merge_features(scratch_ws=scratch_ws,
                                                                     lc_input_features=copy_input_layer,
                                                                     lc_merge_features=copy_merge_layer,
                                                                     select_field=UPDATE_STATUS_FIELD,
                                                                     lc_output_name=output_name)

            if out_put_features and points:
                if arcpy.Exists(out_put_features):
                    # create layer, set layer file
                    # apply transparency here // checking if symbology layer is present
                    z_unit = common_lib.get_z_unit(out_put_features, verbose)

                    if z_unit == "Feet":
                        change_point_SymbologyLayer = layer_directory + "\\change_point_color_feet.lyrx"
                        change_mp_SymbologyLayer = layer_directory + "\\change_mp_color_feet.lyrx"
                    else:
                        change_point_SymbologyLayer = layer_directory + "\\change_point_color_meters.lyrx"
                        change_mp_SymbologyLayer = layer_directory + "\\change_mp_color_meters.lyrx"

                    output_layer1 = common_lib.get_name_from_feature_class(out_put_features)
                    arcpy.MakeFeatureLayer_management(out_put_features, output_layer1)
                    output_layer2 = common_lib.get_name_from_feature_class(points)
                    arcpy.MakeFeatureLayer_management(points, output_layer2)

                    if arcpy.Exists(change_mp_SymbologyLayer):
                        arcpy.ApplySymbologyFromLayer_management(output_layer1, change_mp_SymbologyLayer)
                    else:
                        msg_body = create_msg_body("Can't find" + change_mp_SymbologyLayer +
                                                   " in " + layer_directory, 0, 0)
                        msg(msg_body, WARNING)

                    if arcpy.Exists(change_point_SymbologyLayer):
                        arcpy.ApplySymbologyFromLayer_management(output_layer2, change_point_SymbologyLayer)
                    else:
                        msg_body = create_msg_body("Can't find" + change_point_SymbologyLayer + " in " + layer_directory, 0, 0)
                        msg(msg_body, WARNING)

                    arcpy.SetParameter(3, output_layer1)
                    arcpy.SetParameter(4, output_layer2)

                    end_time = time.clock()
                    msg_body = create_msg_body("merge_features completed successfully.", start_time, end_time)
                    msg(msg_body)
                else:
                    end_time = time.clock()
                    msg_body = create_msg_body("No merge features created. Exiting...", start_time, end_time)
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

    except LicenseError3D:
        print("3D Analyst license is unavailable")
        arcpy.AddError("3D Analyst license is unavailable")

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
