# -------------------------------------------------------------------------------
# Name:        Extract_Elevation_from_LAS.py
# Purpose:     wrapper for Elevation_from_LAS.py
#
# Author:      Gert van Maren
#
# Created:     04/10/12/2018
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
import elevation_from_las
import os
import re

if 'elevation_from_las' in sys.modules:
    importlib.reload(elevation_from_las)
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
TOOLNAME = "extract_elevation_from_las"
WARNING = "warning"
ERROR = "error"


# error classes
class MoreThan1Selected(Exception):
    pass


class NoLayerFile(Exception):
    pass


class NoPointLayer(Exception):
    pass


class NoCatenaryLayer(Exception):
    pass


class NoCatenaryOutput(Exception):
    pass


class NoSwaySurfaceOutput(Exception):
    pass


class NoGuideLinesLayer(Exception):
    pass


class NoGuideLinesOutput(Exception):
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
            input_las_dataset = arcpy.GetParameterAsText(0)
            cell_size = arcpy.GetParameterAsText(1)
            only_ground_buildings = arcpy.GetParameter(2)
            output_elevation_raster = arcpy.GetParameterAsText(3)
            classify_noise = arcpy.GetParameter(4)
            minimum_height = arcpy.GetParameterAsText(5)
            maximum_height = arcpy.GetParameterAsText(6)
            processing_extent = arcpy.GetParameterAsText(7)

            # script variables
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            home_directory = aprx.homeFolder
            project_ws = aprx.defaultGeodatabase

        if os.path.exists(os.path.join(home_directory, "p20")):  # it is a package
            home_directory = os.path.join(home_directory, "p20")

        arcpy.AddMessage("Project Home Directory is: " + home_directory)

        # set directories
        layer_directory = os.path.join(home_directory, "layer_files")
        log_directory = os.path.join(home_directory, "Logs")
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)

        ##########  ensure numerical input is correct
        # fail safe for Europe's comma's
        cell_size = float(re.sub("[,.]", ".", cell_size))

        # rename layer files (for packaging)
        if os.path.exists(layer_directory):
            common_lib.rename_file_extension(layer_directory, ".txt", ".lyrx")

        ############# Create folders and intermediate gdb, if needed
        scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
        arcpy.env.workspace = scratch_ws
        arcpy.env.overwriteOutput = True

        start_time = time.clock()

        # check if input exists
        if arcpy.Exists(input_las_dataset):

            # check if projected coordinates
            cs_name, cs_vcs_name, is_projected = common_lib.get_cs_info(input_las_dataset, 0)

            if is_projected:
                # extract the elevation layers
                dem, dsm, ndsm = elevation_from_las.extract(lc_lasd=input_las_dataset,
                                                            lc_ws=project_ws,
                                                            lc_cell_size=float(cell_size),
                                                            lc_ground_buildings=only_ground_buildings,
                                                            lc_output_elevation=output_elevation_raster,
                                                            lc_minimum_height=minimum_height,
                                                            lc_maximum_height=maximum_height,
                                                            lc_processing_extent=processing_extent,
                                                            lc_noise=classify_noise,
                                                            lc_log_dir=log_directory,
                                                            lc_debug=verbose,
                                                            lc_memory_switch=in_memory_switch)

                if dem and dsm and ndsm:
                    if arcpy.Exists(dem) and arcpy.Exists(dsm) and arcpy.Exists(ndsm):
                        arcpy.AddMessage("Adding Surfaces")

                        output_layer1 = common_lib.get_name_from_feature_class(dem) + "_surface"
                        arcpy.MakeRasterLayer_management(dem, output_layer1)

                        output_layer2 = common_lib.get_name_from_feature_class(dsm) + "_surface"
                        arcpy.MakeRasterLayer_management(dsm, output_layer2)

                        output_layer3 = common_lib.get_name_from_feature_class(ndsm) + "_surface"
                        arcpy.MakeRasterLayer_management(ndsm, output_layer3)

                        arcpy.SetParameter(10, output_layer1)
                        arcpy.SetParameter(11, output_layer2)
                        arcpy.SetParameter(12, output_layer3)

                        end_time = time.clock()
                        msg_body = create_msg_body("extract_elevation_from_las completed successfully.", start_time, end_time)
                        msg(msg_body)
                    else:
                        end_time = time.clock()
                        msg_body = create_msg_body("No elevation surfaces created. Exiting...", start_time, end_time)
                        msg(msg_body, WARNING)

                arcpy.ClearWorkspaceCache_management()

                if DeleteIntermediateData:
                    fcs = common_lib.listFcsInGDB(scratch_ws)

                    msg_prefix = "Deleting intermediate data..."

                    msg_body = common_lib.create_msg_body(msg_prefix, 0, 0)
                    common_lib.msg(msg_body)

                    for fc in fcs:
                        arcpy.Delete_management(fc)
            else:
                arcpy.AddError("Input data is not valid. Check your data.")
                arcpy.AddMessage("Only projected coordinate systems are supported.")
            # end main code

    except LicenseError3D:
        print("3D Analyst license is unavailable")
        arcpy.AddError("3D Analyst license is unavailable")

    except NoPointLayer:
        print("Can't find attachment points layer. Exiting...")
        arcpy.AddError("Can't find attachment points layer. Exiting...")

    except NoPointLayer:
        print("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")
        arcpy.AddError("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")

    except NoCatenaryLayer:
        print("Can't find Catenary layer. Exiting...")
        arcpy.AddError("Can't find Catenary layer. Exiting...")

    except NoCatenaryOutput:
        print("Can't create Catenary output. Exiting...")
        arcpy.AddError("Can't create Catenary output. Exiting...")

    except NoSwaySurfaceOutput:
        print("Can't find SwaySurface output. Exiting...")
        arcpy.AddError("Can't find SwaySurface. Exiting...")

    except NoGuideLinesLayer:
        print("Can't find GuideLines output. Exiting...")
        arcpy.AddError("Can't find GuideLines. Exiting...")

    except MoreThan1Selected:
        print("More than 1 line selected. Please select 1 guide line only. Exiting...")
        arcpy.AddError("More than 1 line selected. Please select 1 guide line only. Exiting...")

    except NoGuideLinesOutput:
        print("Can't create GuideLines output. Exiting...")
        arcpy.AddError("Can't create GuideLines. Exiting...")

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
