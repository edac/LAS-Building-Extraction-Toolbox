# -------------------------------------------------------------------------------
# Name:         merge_features
# Purpose:      merges 1 feature class into another based on intersection

# Author:      Gert van Maren
#
# Created:     08/05/19
# Copyright:   (c) Esri 2019
# updated:
# updated:
# updated:

# Required:
#

# -------------------------------------------------------------------------------

import arcpy
import os
import sys
import common_lib
from common_lib import create_msg_body, msg

# Constants
WARNING = "warning"


def merge_features(scratch_ws, lc_input_features, lc_merge_features, select_field, lc_output_name):

    try:
        merged_fc = None

        # merge features
        if lc_input_features and lc_merge_features:
            arcpy.AddMessage("Setting merge date on merge features...")
            date_field = "merge_date"
            common_lib.delete_add_field(lc_merge_features, date_field, "DATE")
            arcpy.CalculateField_management(lc_merge_features, date_field,
                                            "time.strftime('%d/%m/%Y')", "PYTHON_9.3", "")

            # create point feature class showing
            point_fc = os.path.join(scratch_ws, "temp_point")
            if arcpy.Exists(point_fc):
                arcpy.Delete_management(point_fc)

            # create 3D point feature class showing
            point_fc_3d = lc_output_name + "_points"
            if arcpy.Exists(point_fc):
                arcpy.Delete_management(point_fc)

            arcpy.AddZInformation_3d(lc_merge_features, "Z_MIN;Z_MAX", None)
            arcpy.FeatureToPoint_management(lc_merge_features, point_fc, "INSIDE")

            point_field = "point_elevation"
            common_lib.delete_add_field(point_fc, point_field, "DOUBLE")

            z_unit = common_lib.get_z_unit(point_fc, 0)

            if z_unit == "Feet":
                offset = 30
            else:
                offset = 10

            expression = "round(float(!Z_Max!), 2) + " + str(offset)
            arcpy.CalculateField_management(point_fc, point_field, expression, "PYTHON_9.3", None)

            arcpy.FeatureTo3DByAttribute_3d(point_fc, point_fc_3d, point_field, None)

            # select in the base layer the features that don't intersect
            arcpy.AddMessage("Finding all features that don't intersect, this may take some time...")
            non_intersect_lyr = arcpy.SelectLayerByLocation_management(lc_input_features, "INTERSECT",
                                                                       lc_merge_features,
                                                                       None, "NEW_SELECTION", "INVERT")

            input_selectbyloc_layer = os.path.join(scratch_ws, "input_selectbyloc_layer")
            if arcpy.Exists(input_selectbyloc_layer):
                arcpy.Delete_management(input_selectbyloc_layer)

            arcpy.CopyFeatures_management(non_intersect_lyr, input_selectbyloc_layer)
            common_lib.delete_add_field(input_selectbyloc_layer, select_field, "TEXT")
            arcpy.CalculateField_management(input_selectbyloc_layer, select_field, "'Unchanged'", "PYTHON_9.3", "")

            # select features that are not "Demolished in merge layer and only merge those"
            no_demol_lyr = "no_demol_lyr"
            arcpy.MakeFeatureLayer_management(lc_merge_features, no_demol_lyr)
            expression = """{} <> 'Demolished'""".format(arcpy.AddFieldDelimiters(no_demol_lyr, select_field))
            arcpy.SelectLayerByAttribute_management(no_demol_lyr, "NEW_SELECTION", expression, None)

            # merge
            merged_fc = lc_output_name + "_merged"
            if arcpy.Exists(merged_fc):
                arcpy.Delete_management(merged_fc)

            arcpy.Merge_management([input_selectbyloc_layer, no_demol_lyr], merged_fc)

        else:
            msg_body = create_msg_body("No output name detected. Exiting...", 0, 0)
            msg(msg_body, WARNING)

        return merged_fc, point_fc_3d

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))










