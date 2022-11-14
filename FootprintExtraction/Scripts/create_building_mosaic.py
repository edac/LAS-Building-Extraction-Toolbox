# -------------------------------------------------------------------------------
# Name:        create_building_mosaic.py
# Purpose:     Process for creating a 8 bit unsigned mosaic raster from tiles
# Authors:     Dan Hedges | 3D Product Engineer | Esri (Updates for Solution integration)
#              Geoff Taylor | 3D Solutions Engineer | Esri (Framework)
#              Arthur Crawford | Content Product Engineer | Esri (Concept and improvement using raster functions)
#              Andrew Watson | 2017 Esri TWI Program 
# Created:     04/19/2017
# Copyright:   (c) Esri 2017
# Licence:
# Modified:    Paul Neville | Concept
#              Hays Barrett | Converting for ArcGIS Pro 3.0 functionality
# -------------------------------------------------------------------------------

import arcpy
import os
import time
import sys
import csv

arcpy.env.overwriteOutput = True

in_lasd = arcpy.GetParameterAsText(0)
out_folder = arcpy.GetParameterAsText(1)
out_mosaic = arcpy.GetParameterAsText(2)
spatial_ref = arcpy.GetParameterAsText(3)
cell_size = arcpy.GetParameterAsText(4)
las_desc = arcpy.Describe(in_lasd)
las_sr = las_desc.spatialReference


def get_metric_from_linear_unit(linear_unit):
    unit_split = linear_unit.split(' ')
    value = float(unit_split[0])
    unit = unit_split[1]
    unit_dict = {
        "Kilometers": .001,
        "Meters": 1,
        "Decimeters": 10,
        "Centimeters": 100,
        "Millimeters": 1000,
        "Feet": 3.28084,
        "Inches": 39.3701,
        "Miles": 0.000621371,
        "Yards": 1.09361,
        "NauticalMiles": 0.000539957
    }
    metric_value = value / unit_dict[unit]
    return metric_value


def create_las_rasters(tileList, count, spatialRef, cellSize, scratchFolder):
    # Check to ensure that scratch folder exists:
    if not os.path.exists(scratchFolder):
        os.mkdir(scratchFolder)
    # Recursively process LiDAR Tiles
    iteration = 0
    arcpy.SetProgressor("step", "Percent Complete...", 0, count, iteration)
    for file in tileList:
        try:
            arcpy.SetProgressor("step", "{0} Percent Complete...".format(round((100/count)*iteration, 1)), 0, count,
                                iteration)
            fullFileName = os.path.join(scratchFolder, file)
            # Obtain file name without extension and add .las:
            #fileName = "{0}".format(os.path.splitext(file)[0])
            fileName=os.path.basename(file).split('.')[0]+"_las_dataset_layer"
            file_basename = os.path.basename(fileName)
            # Create Las Dataset Layers in scratch folder
            inLASD = os.path.join(scratchFolder, "{0}.lasd".format(os.path.splitext(file)[0]))

            arcpy.CreateLasDataset_management(fullFileName, inLASD, False, "", spatialRef, "COMPUTE_STATS")

            # arcpy.MakeLasDatasetLayer_management(inLASD, fileName, 6,
            #                                      "'Last Return'",
            #                                      "INCLUDE_UNFLAGGED", "INCLUDE_SYNTHETIC", "INCLUDE_KEYPOINT",
            #                                      "EXCLUDE_WITHHELD", None, "INCLUDE_OVERLAP")
            arcpy.management.MakeLasDatasetLayer(inLASD,fileName, "6", "LAST", "INCLUDE_UNFLAGGED", "INCLUDE_SYNTHETIC", "INCLUDE_KEYPOINT", "EXCLUDE_WITHHELD", None, "INCLUDE_OVERLAP")

            bldgPtRaster = os.path.join(out_folder, "{0}.tif".format(file_basename))
            arcpy.LasPointStatsAsRaster_management(fileName, bldgPtRaster, "PREDOMINANT_CLASS", "CELLSIZE", cellSize)

            # Delete Intermediate Data
            arcpy.Delete_management(fileName)
            arcpy.Delete_management(inLASD)
            iteration += 1
            arcpy.SetProgressorPosition()

        except Exception as e:
            arcpy.AddMessage(str(e))
            iteration += 1
            arcpy.SetProgressorPosition()
            errorMessage = "{0} failed @ {1} : Check if building class codes exist".format(file, time.strftime("%H:%M:%S"))
            arcpy.AddMessage(errorMessage)
            #logMessage(logFile, errorMessage)
            inLASD = os.path.join(scratchFolder, "{0}.lasd".format(os.path.splitext(file)[0]))
            if arcpy.Exists(inLASD):
                arcpy.Delete_management(inLASD)
            pass


def get_files_from_lasd(las_dataset, outputdir):
    try:
        # Check LAS Spatial Reference
        if las_sr.name == "Unknown":
            arcpy.AddError("LAS Dataset has an unknown coordinate system."
                           " Please use the Extract LAS tool to re-project and try again")
            exit()
        if las_sr.type == "Geographic":
            arcpy.AddError("LAS Dataset is in a geographic coordinate system."
                           " Please re-create the LAS dataset, selecting the correct coordinate system and checking "
                           "'Create PRJ for LAS Files' and try again")
            exit()

        # Get LiDAR file names
        las_files = []

        lasStats = os.path.join(outputdir, 'lasStats_stats.csv')

        if arcpy.Exists(lasStats):
            arcpy.Delete_management(lasStats)
        arcpy.LasDatasetStatistics_management(las_dataset, "OVERWRITE_EXISTING_STATS", lasStats, "LAS_FILES", "COMMA",
                                              "DECIMAL_POINT")
        with open(lasStats, 'r') as f:
            reader = csv.reader(f)

            for row in reader:

                if len(row) > 1 and row[0] != 'File_Name' and row[0] not in las_files and row[1] == "6_Building":

                    las_files.append(row[0])

        arcpy.AddMessage('LAS Files with Building (6) class codes found: {}'.format(str(len(las_files))))

        # arcpy.Delete_management(lasStats)

        return las_files

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))

# Create LAS rasters
lasd_path = arcpy.Describe(in_lasd).path
# las_folder = os.path.dirname(lasd_path)
las_list = get_files_from_lasd(in_lasd, lasd_path)
las_count = len(las_list)
metric_cell_size = get_metric_from_linear_unit(cell_size)
las_m_per_unit = las_sr.metersPerUnit
cell_size_conv = metric_cell_size / las_m_per_unit

if las_count > 0:
    create_las_rasters(tileList=las_list, count=las_count, spatialRef=spatial_ref, cellSize=cell_size_conv,
                       scratchFolder=out_folder)
else:
    arcpy.AddError("No LAS files found containing Building (6) class codes. Classify building points and try again")
    exit()

# Create mosaic dataset
arcpy.AddMessage(out_mosaic)
if not arcpy.Exists(out_mosaic):
    out_gdb = os.path.dirname(out_mosaic)
    mosaic_name = os.path.basename(out_mosaic)
    arcpy.CreateMosaicDataset_management(out_gdb, out_mosaic, spatial_ref, None, "8_BIT_UNSIGNED", "CUSTOM", None)
    arcpy.AddMessage('Mosaic dataset {} created...'.format(out_mosaic))

# Add rasters to mosaic and set cell size
arcpy.AddMessage('Adding rasters to mosaic dataset...')
arcpy.AddRastersToMosaicDataset_management(out_mosaic, "Raster Dataset", out_folder,
                                           "UPDATE_CELL_SIZES", "UPDATE_BOUNDARY", "NO_OVERVIEWS", None, 0, 1500,
                                           None, None, "SUBFOLDERS", "ALLOW_DUPLICATES", "NO_PYRAMIDS", "NO_STATISTICS",
                                           "NO_THUMBNAILS", None, "NO_FORCE_SPATIAL_REFERENCE", "NO_STATISTICS", None)

# Update mosaic cell size
arcpy.AddMessage('Updating mosaic cell size...')
cellSize = arcpy.GetRasterProperties_management(out_mosaic, "CELLSIZEX")
newSize = float(float(cellSize.getOutput(0))/2)
arcpy.SetMosaicDatasetProperties_management(out_mosaic, cell_size=newSize)


arcpy.AddMessage("Process complete")

