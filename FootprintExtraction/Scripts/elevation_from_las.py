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

import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)

from common_lib import create_msg_body, msg

# Constants
WARNING = "warning"


def extract(lc_lasd, lc_ws, lc_cell_size, lc_ground_buildings, lc_output_elevation, lc_minimum_height,
            lc_maximum_height, lc_processing_extent, lc_noise, lc_log_dir, lc_debug, lc_memory_switch):

    try:
        dem = None
        dsm = None
        ndsm = None

        # create dem
        desc = arcpy.Describe(lc_lasd)
        l_unit = desc.spatialReference.linearUnitName
        #        if desc.spatialReference.linearUnitName in ['Foot_US', 'Foot']:
        if 'feet' in l_unit.lower() or 'foot' in l_unit.lower():
            unit = 'Feet'
        else:
            unit = 'Meters'

        # Classify overlap points
        # ptSpacing = desc.pointSpacing * 2.25
        # sampling = '{0} {1}'.format(ptSpacing, unit)
        # arcpy.ClassifyLasOverlap_3d(lc_lasd, sampling)

        # get lidar class code - TEMPORARY until Pro 2.3
        msg_body = create_msg_body("Looking for class codes: ", 0, 0)
        msg(msg_body)

        class_code_list = common_lib.get_las_class_codes(lc_lasd, lc_log_dir)

        if lc_ground_buildings and 6 in class_code_list:
            class_code_list = [2, 6]

        ground_code = 2

        # Generate DEM
        if ground_code in class_code_list:
            dem = arcpy.CreateUniqueName(lc_output_elevation + "_dtm")

            if arcpy.Exists(dem):
                arcpy.Delete_management(dem)

            msg_body = create_msg_body("Creating Ground Elevation using the following class codes: " +
                                   str(ground_code), 0, 0)
            msg(msg_body)

            ground_ld_layer = arcpy.CreateUniqueName('ground_ld_lyr')

            # Filter for ground points
            arcpy.management.MakeLasDatasetLayer(lc_lasd, ground_ld_layer, class_code=str(ground_code))

            arcpy.conversion.LasDatasetToRaster(ground_ld_layer, dem, 'ELEVATION',
                                                'BINNING MAXIMUM LINEAR',
                                                sampling_type='CELLSIZE',
                                                sampling_value=lc_cell_size)

            lc_max_neighbors = "#"
            lc_step_width = "#"
            lc_step_height = "#"

            if lc_noise:
                # Classify noise points
                msg_body = create_msg_body("Classifying points that are " + lc_minimum_height + " below ground and " +
                                           lc_maximum_height + " above ground as noise.", 0, 0)
                msg(msg_body)

                arcpy.ClassifyLasNoise_3d(lc_lasd, method='RELATIVE_HEIGHT', edit_las='CLASSIFY',
                                           withheld='WITHHELD', ground=dem,
                                           low_z=lc_minimum_height, high_z=lc_maximum_height,
                                           max_neighbors=lc_max_neighbors, step_width=lc_step_width, step_height=lc_step_height,
                                           extent=lc_processing_extent)
            else:
                # Classify noise points
                msg_body = create_msg_body("Noise will not be classified.", 0, 0)
                msg(msg_body)

            # create dsm
            dsm = arcpy.CreateUniqueName(lc_output_elevation + "_dsm")

            if arcpy.Exists(dsm):
                arcpy.Delete_management(dsm)

            msg_body = create_msg_body("Creating Surface Elevation using the following class codes: " +
                                       str(class_code_list), 0, 0)
            msg(msg_body)

            dsm_ld_layer = arcpy.CreateUniqueName('dsm_ld_lyr')
            arcpy.management.MakeLasDatasetLayer(lc_lasd, dsm_ld_layer, class_code=class_code_list, return_values=["Last return"])

            arcpy.conversion.LasDatasetToRaster(dsm_ld_layer, dsm, 'ELEVATION',
                                                'BINNING MAXIMUM LINEAR',
                                                sampling_type='CELLSIZE',
                                                sampling_value=lc_cell_size)

            # create ndsm
            msg_body = create_msg_body("Creating normalized Surface Elevation using " +
                                       common_lib.get_name_from_feature_class(dsm) + " and " +
                                       common_lib.get_name_from_feature_class(dem), 0, 0)
            msg(msg_body)

            ndsm = arcpy.CreateUniqueName(lc_output_elevation + "_ndsm")

            if arcpy.Exists(ndsm):
                arcpy.Delete_management(ndsm)

            arcpy.Minus_3d(dsm, dem, ndsm)
        else:
            msg_body = create_msg_body("Couldn't detect ground class code in las dataset. Exiting...", 0, 0)
            msg(msg_body, WARNING)

        return dem, dsm, ndsm

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))



