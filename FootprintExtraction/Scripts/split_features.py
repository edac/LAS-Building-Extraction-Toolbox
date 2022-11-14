# -------------------------------------------------------------------------------
# Name:         elevation_from_las
# Purpose:      Creates 3 elevation surface from a input las dataset

# Author:      Gert van Maren
#
# Created:     27/10/18
# Copyright:   (c) Esri 2018
# updated:
# updated:
# updated:

# Required:
#

# -------------------------------------------------------------------------------

import arcpy
import sys
import time
import importlib
import os
import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)

from common_lib import create_msg_body, msg

# Constants
WARNING = "warning"


def split(scratch_ws, lc_input_features, lc_split_features, lc_minimum_area, lc_output_name, lc_debug, lc_memory_switch):

    try:
        out_features = None

        # split features
        if lc_input_features and lc_split_features:

            SHAPEAREAFIELD = "Shape_Area"
            PRESPLITFIELD = "PRESPLIT_FID"

            # Keep original input feature OBJECTID as TEXT. copy to PRESPLITFIELD.
            common_lib.delete_add_field(lc_input_features, PRESPLITFIELD, "LONG")
            arcpy.CalculateField_management(lc_input_features, PRESPLITFIELD, "!OBJECTID!", "PYTHON_9.3", None)

            # use Identity to split the input features
            # copy feature class to capture selection
            identity_fc = os.path.join(scratch_ws, "identity_split")
            if arcpy.Exists(identity_fc):
                arcpy.Delete_management(identity_fc)

            arcpy.AddMessage("Splitting features, this may take some time...")

            # Process: Use the Identity function
            arcpy.Identity_analysis(lc_input_features, lc_split_features, identity_fc, "ONLY_FID")

            # check for area attribute
            if not common_lib.check_fields(identity_fc, [SHAPEAREAFIELD], True, lc_debug) == 0:
                arcpy.AddField_management(identity_fc, "Shape_Area", "DOUBLE")
                exp = "!shape.area!"
                arcpy.CalculateField_management(identity_fc, "Shape_Area", exp, "PYTHON_9.3")

            # select / delete  all features with area < lc_minimum_area
            arcpy.AddMessage("Selecting features with an area < " + str(lc_minimum_area) + "...")
            expression = """{} < {}""".format(arcpy.AddFieldDelimiters(identity_fc, SHAPEAREAFIELD), lc_minimum_area)

            local_layer = common_lib.get_name_from_feature_class(identity_fc) + "_lyr"
            arcpy.MakeFeatureLayer_management(identity_fc, local_layer)
            arcpy.SelectLayerByAttribute_management(local_layer, "NEW_SELECTION", expression)

            num_selected = int(arcpy.GetCount_management(local_layer).getOutput(0))

            if num_selected > 0:
                arcpy.DeleteFeatures_management(local_layer)
                arcpy.AddMessage("Removed " + str(num_selected) + " features with an area < " + str(lc_minimum_area)+ " from the input feature class.")

            arcpy.SelectLayerByAttribute_management(local_layer, "CLEAR_SELECTION")

            # select / delete  all features that have no intersection to get rid of slivers
            arcpy.AddMessage("Selecting features with no intersection...")
            split_FID_field = "FID_" + common_lib.get_name_from_feature_class(lc_split_features)
            expression = """{} = {}""".format(arcpy.AddFieldDelimiters(local_layer, split_FID_field), -1)

            arcpy.SelectLayerByAttribute_management(local_layer, "NEW_SELECTION", expression)

            num_selected = int(arcpy.GetCount_management(local_layer).getOutput(0))

            if num_selected > 0:
                arcpy.DeleteFeatures_management(local_layer)
                arcpy.AddMessage("Removing slivers...")

            arcpy.SelectLayerByAttribute_management(local_layer, "CLEAR_SELECTION")

            num_selected = int(arcpy.GetCount_management(lc_input_features).getOutput(0))

            # add features from input that don't intersect with the resulting fc
            if common_lib.is_layer(lc_input_features) == 0:
                input_layer = common_lib.get_name_from_feature_class(lc_input_features) + "_lyr"
                arcpy.MakeFeatureLayer_management(lc_input_features, input_layer)
                arcpy.SelectLayerByLocation_management(input_layer, "INTERSECT", local_layer,
                                                       invert_spatial_relationship="INVERT")
            else:
                input_layer = lc_input_features

                if common_lib.get_num_selected(input_layer) > 0:
                    arcpy.SelectLayerByLocation_management(input_layer, "INTERSECT", local_layer,
                                                       selection_type="REMOVE_FROM_SELECTION")
                else:
                    arcpy.SelectLayerByLocation_management(input_layer, "INTERSECT", local_layer,
                                                       invert_spatial_relationship="INVERT")

            arcpy.AddMessage("Adding original features with no intersection...")

            # copy layer to preserve selection
            copy_fc = os.path.join(scratch_ws, "copy_selection")
            if arcpy.Exists(copy_fc):
                arcpy.Delete_management(copy_fc)

            # Copy selection to output
            arcpy.CopyFeatures_management(input_layer, copy_fc)

            # merge
            merged_fc = lc_output_name + "_split"
            if arcpy.Exists(merged_fc):
                arcpy.Delete_management(merged_fc)

            arcpy.Merge_management([copy_fc, local_layer], merged_fc)

            # delete PRESPLITFIELD from input features
#            common_lib.delete_fields(lc_input_features, [PRESPLITFIELD])

            arcpy.SelectLayerByAttribute_management(input_layer, "CLEAR_SELECTION")

            return merged_fc

        else:
            msg_body = create_msg_body("No output name detected. Exiting...", 0, 0)
            msg(msg_body, WARNING)

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))










