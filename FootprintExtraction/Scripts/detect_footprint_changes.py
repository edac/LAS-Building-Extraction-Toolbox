__author__ = 'dani7858'


import arcpy
from arcpy.sa import *
import os
import sys
import common_lib
import csv
import re

lasd = arcpy.GetParameterAsText(0)
buildings = arcpy.GetParameterAsText(1)
threshold = arcpy.GetParameterAsText(2)
cell_size = arcpy.GetParameterAsText(3)
minimum_area = arcpy.GetParameterAsText(4)
aoi = arcpy.GetParameterAsText(5)
replace_changes = arcpy.GetParameterAsText(6)
output_fps = arcpy.GetParameterAsText(7)

aprx = arcpy.mp.ArcGISProject("CURRENT")
gdb = aprx.defaultGeodatabase
workspace = "in_memory"
home_folder = aprx.homeFolder
update_field = "Update_Status"
iou_field = "IoU"

class NoChange(Exception):
    pass


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


def get_metric_from_areal_unit(areal_unit):
    unit_split = areal_unit.split(' ')
    value = float(unit_split[0])
    unit = unit_split[1]
    unit_dict = {
        "SquareKilometers": .000001,
        "Hectares": 0.0001,
        "SquareMeters": 1,
        "SquareDecimeters": 100,
        "SquareCentimeters": 10000,
        "SquareMillimeters": 1000000,
        "SquareFeet": 10.7639,
        "Inches": 1550,
        "Miles": 0.0000003861013863,
        "Yards": 1.19599,
        "Acres": 0.000247105
    }
    metric_value = value / unit_dict[unit]
    return metric_value


def get_files_from_lasd(las_dataset, outputdir):
    try:
        # Get LiDAR class codes
        las_files = []

        lasStats = os.path.join(outputdir, 'lasStats_stats.csv')

        if arcpy.Exists(lasStats):
            arcpy.Delete_management(lasStats)

        arcpy.LasDatasetStatistics_management(las_dataset, "OVERWRITE_EXISTING_STATS", lasStats, "LAS_FILES", "COMMA",
                                              "DECIMAL_POINT")

        with open(lasStats, 'r') as f:
            reader = csv.reader(f)

            for row in reader:

                if len(row) > 1 and row[0] != 'File_Name' and row[0] not in las_files:

                    las_files.append(row[0])

        arcpy.AddMessage('LAS Files found: {}'.format(str(len(las_files))))

        arcpy.Delete_management(lasStats)

        return las_files

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))


def get_lasd_extent(lasd, output_extent, work_folder, spatial_ref):
    if not os.path.exists(work_folder):
        os.mkdir(work_folder)

    las_list = get_files_from_lasd(lasd, work_folder)

    arcpy.PointFileInformation_3d(las_list, output_extent, "LAS", input_coordinate_system=spatial_ref)

    return output_extent


def get_area_field(fc):
    path_name = os.path.dirname(fc)
    if path_name == "in_memory":
        area_field = "geom_area"
        fields = arcpy.ListFields(fc)
        if area_field in [f.name for f in fields]:
            arcpy.DeleteField_management(fc, area_field)
        arcpy.AddField_management(fc, "geom_area", "FLOAT")
        arcpy.CalculateField_management(fc, "geom_area", "!shape.area!", "PYTHON_9.3")

    else:
        area_field = arcpy.Describe(fc).areaFieldName

    return area_field


cell_size = re.sub("[,.]", ".", cell_size)
min_area = re.sub("[,.]", ".", minimum_area)
threshold = re.sub("[,.]", ".", threshold)
m_cell_size = get_metric_from_linear_unit(cell_size)
m_min_area = get_metric_from_areal_unit(minimum_area)
m_threshold = get_metric_from_linear_unit(threshold)

# Check for building classification
# If building classification exists, create surface from building points and ground
# If no building points exist, clip DSM
las_desc = arcpy.Describe(lasd)
mp_desc = arcpy.Describe(buildings)
aoi_spatial_ref = None
if arcpy.Exists(aoi):
    aoi_desc = arcpy.Describe(aoi)
    aoi_spatial_ref = aoi_desc.spatialReference
update_stats = las_desc.needsUpdateStatistics
las_spatial_ref = las_desc.spatialReference
mp_spatial_ref = mp_desc.spatialReference

if update_stats:
    arcpy.AddMessage("Updating LAS Dataset Statistics")
    arcpy.LasDatasetStatistics_management(lasd, "OVERWRITE_EXISTING_STATS")
class_codes = las_desc.classCodes
arcpy.AddMessage("Class codes detected: " + str(class_codes))
class_list = [int(code) for code in class_codes.split(';')]
try:
    if os.path.exists(home_folder + "\\p20"):      # it is a package
        home_folder = home_folder + "\\p20"

    arcpy.AddMessage("Project Home Directory is: " + home_folder)

    layerDirectory = home_folder + "\\layer_files"

    if os.path.exists(layerDirectory):
        common_lib.rename_file_extension(layerDirectory, ".txt", ".lyrx")

    if las_spatial_ref.type == "Geographic":
        arcpy.AddError("LAS Dataset is in a geographic coordinate system."
                       " Please use the Extract LAS tool to re-project and try again")
    if mp_spatial_ref.type == "Geographic":
        arcpy.AddError("Multipatch feature class is in a geographic coordinate system."
                       " Please use the Project tool to re-project and try again")

    las_extent = os.path.join(workspace, "las_extent")
    get_lasd_extent(lasd, las_extent, home_folder, las_spatial_ref)
    aoi_proj = os.path.join(gdb, "aoi_proj")
    mp_bldg_lyr = "mp_bldg_lyr"
    arcpy.MakeFeatureLayer_management(buildings, mp_bldg_lyr)
    if arcpy.Exists(aoi):
        aoi_int = os.path.join(workspace, "aoi_int")
        if aoi_spatial_ref != las_spatial_ref:
            arcpy.Project_management(aoi, aoi_proj, las_spatial_ref)
            arcpy.Intersect_analysis([aoi_proj, las_extent], aoi_int)
            arcpy.env.mask = aoi_int
        else:
            arcpy.Intersect_analysis([aoi, las_extent], aoi_int)
            arcpy.env.mask = aoi_int
        arcpy.SelectLayerByLocation_management(mp_bldg_lyr, "INTERSECT", aoi_int)
    else:
        arcpy.env.mask = las_extent
        arcpy.SelectLayerByLocation_management(mp_bldg_lyr, "INTERSECT", las_extent)
    mp_m_per_unit = mp_spatial_ref.metersPerUnit
    las_m_per_unit = las_spatial_ref.metersPerUnit

    # Create multipatch footprints
    mp_footprints = os.path.join(workspace, "mp_footprints")
    arcpy.MultiPatchFootprint_3d(mp_bldg_lyr, mp_footprints)
    fp_desc = arcpy.Describe(mp_footprints)
    fp_oid = fp_desc.OIDFieldName

    if 6 in class_list and 2 in class_list:
        # Add update status and IoU field
        arcpy.AddFields_management(mp_footprints, [[update_field, "TEXT"], [iou_field, "FLOAT"]])

        # Create output fc
        out_path = os.path.dirname(output_fps)
        out_name = os.path.basename(output_fps)
        arcpy.CreateFeatureclass_management(out_path, out_name, "POLYGON", mp_footprints)

        # Create ground layer
        arcpy.AddMessage("Creating las building surface")
        las_bldg_lyr = "las_bldg_lyr"
        arcpy.MakeLasDatasetLayer_management(lasd, las_bldg_lyr, [6])
        
        las_ground_layer = "las_ground_layer"
        arcpy.MakeLasDatasetLayer_management(lasd, las_ground_layer, 2)

        las_cell_size = round(m_cell_size / las_m_per_unit)

        las_bldg_ras = os.path.join(workspace, "las_bldg_ras")
        arcpy.LasDatasetToRaster_conversion(las_bldg_lyr, las_bldg_ras, "ELEVATION", 'BINNING MAXIMUM SIMPLE',
                                            sampling_type='CELLSIZE',
                                            sampling_value=las_cell_size)

        las_ground_ras = os.path.join(workspace, "las_ground_ras")
        arcpy.LasDatasetToRaster_conversion(las_ground_layer, las_ground_ras, "ELEVATION", 'BINNING MAXIMUM LINEAR',
                                            sampling_type='CELLSIZE',
                                            sampling_value=las_cell_size)

        # convert vertical units to meter
        bldg_ras = os.path.join(workspace, "bldg_ras")
        ground_ras = os.path.join(workspace, "ground_ras")
        if las_m_per_unit != 1:
            arcpy.Times_3d(las_bldg_ras, las_m_per_unit, bldg_ras)
            arcpy.Times_3d(las_ground_ras, las_m_per_unit, ground_ras)
        else:
            bldg_ras = las_bldg_ras
            ground_ras = las_ground_ras

        # Rasterize buildings
        arcpy.AddMessage("Rasterizing 3D Buildings")
        arcpy.env.snapRaster = bldg_ras
        arcpy.env.cellSize = bldg_ras
        mp_bldg_ras = os.path.join(workspace, "mp_bldg_ras")
        arcpy.MultipatchToRaster_conversion(buildings, mp_bldg_ras)
        mp_ras = os.path.join(workspace, "mp_ras")
        if mp_m_per_unit != 1:
            arcpy.Times_3d(mp_bldg_ras, mp_m_per_unit, mp_ras)
        else:
            mp_ras = mp_bldg_ras

        # Combine building and ground rasters
        las_bldg_null = IsNull(bldg_ras)
        las_combined_ras = Con(las_bldg_null, ground_ras, bldg_ras, "VALUE = 1")

        # Create comparison raster
        arcpy.AddMessage("Creating comparison raster")
        bldg_null_save = os.path.join(workspace, "bldgNull")
        bldg_null = IsNull(mp_bldg_ras)
        bldg_null.save(bldg_null_save)
        combined_ras_save = os.path.join(workspace, "combined_ras")
        combined_ras = Con(bldg_null, ground_ras, mp_ras, "VALUE = 1")
        combined_ras.save(combined_ras_save)

        # Subtract from reference raster
        compare_ras_save = os.path.join(workspace, "compare_ras")
        compare_ras = Minus(las_combined_ras, combined_ras)
        abs_error = Abs(compare_ras)

        # Compare las bldg raster to ground raster
        ground_compare = Minus(las_combined_ras, ground_ras)

        # Find area where no buildings exist in lidar
        arcpy.AddMessage("Checking for demolished structures")
        no_bldg_area = Con(ground_compare < 1, 1)
        no_bldg_poly = os.path.join(gdb, "no_bldg_poly")

        arcpy.RasterToPolygon_conversion(no_bldg_area, no_bldg_poly, "NO_SIMPLIFY")

        # Select all mp footprints completely contained by no building area
        footprint_lyr = "fp_lyr"
        arcpy.MakeFeatureLayer_management(mp_footprints, footprint_lyr)
        arcpy.SelectLayerByLocation_management(footprint_lyr, "COMPLETELY_WITHIN", no_bldg_poly)

        poly_min_area = m_min_area / (las_m_per_unit ** 2)
        if common_lib.get_fids_for_selection(footprint_lyr)[1] > 0:
            # TODO: check Dan
            demol_area = get_area_field(mp_footprints)
            arcpy.SelectLayerByAttribute_management(footprint_lyr, "REMOVE_FROM_SELECTION",
                                                    "{0} < {1}".format(demol_area, str(poly_min_area)))

            arcpy.AddMessage("{0} demolished structures found"
                             .format(str(common_lib.get_fids_for_selection(footprint_lyr)[1])))
            arcpy.CalculateField_management(footprint_lyr, update_field, "'Demolished'")
            arcpy.CopyFeatures_management(footprint_lyr, output_fps)
            arcpy.DeleteField_management(output_fps, demol_area)
            arcpy.DeleteFeatures_management(footprint_lyr)
            # arcpy.MakeFeatureLayer_management(mp_footprints, footprint_lyr)

        # Find partially demolished portions of buildings
        partial_demo = os.path.join(workspace, "partial_demo")
        arcpy.Clip_analysis(no_bldg_poly, mp_footprints, partial_demo)
        arcpy.Delete_management(no_bldg_poly)
        partial_demo_sp = os.path.join(workspace, "partial_demo_sp")
        arcpy.MultipartToSinglepart_management(partial_demo, partial_demo_sp)

        # Select large demo areas
        poly_min_area = m_min_area / (las_m_per_unit ** 2)
        demo_area = get_area_field(partial_demo_sp)
        partial_demo_lg = os.path.join(workspace, "partial_demo_lg")

        arcpy.Select_analysis(partial_demo_sp, partial_demo_lg, "{0} > {1}".format(demo_area, str(poly_min_area)))

        # remove slivers
        partial_demo_shrink = os.path.join(workspace, "demo_shrink")
        arcpy.Buffer_analysis(partial_demo_lg, partial_demo_shrink, "-" + cell_size)
        partial_demo_grow = os.path.join(workspace, "demo_grow")
        arcpy.Buffer_analysis(partial_demo_shrink, partial_demo_grow, cell_size)
        demo_grow_lg = os.path.join(workspace, "demo_grow_lg")
        arcpy.Select_analysis(partial_demo_grow, demo_grow_lg, "{0} > {1}".format(demo_area, str(poly_min_area)))
        partial_demo_lyr = "partial_demo_lyr"
        arcpy.MakeFeatureLayer_management(partial_demo_lg, partial_demo_lyr)
        arcpy.SelectLayerByLocation_management(partial_demo_lyr, "INTERSECT", demo_grow_lg,
                                               invert_spatial_relationship="INVERT")
        if common_lib.get_fids_for_selection(partial_demo_lyr)[1] > 0:
            arcpy.DeleteFeatures_management(partial_demo_lyr)

        # Find new areas
        arcpy.AddMessage("Checking for new structures")
        new_bldg_area = Con(((ground_compare > 0) & (bldg_null == 1)), 1)
        new_bldg_shrink = Shrink(new_bldg_area, 1, 1)
        new_bldg_grow = Expand(new_bldg_shrink, 1, 1)
        new_bldg_poly = os.path.join(workspace, "new_bldg_poly")
        if new_bldg_grow.maximum == 1:
            arcpy.RasterToPolygon_conversion(new_bldg_grow, new_bldg_poly, "NO_SIMPLIFY")
            new_bldg_area_field = get_area_field(new_bldg_poly)

            # Select new areas that do not intersect existing footprints
            new_bldg_lyr = "new_bldg_lyr"
            arcpy.MakeFeatureLayer_management(new_bldg_poly, new_bldg_lyr)
            arcpy.SelectLayerByAttribute_management(new_bldg_lyr, "NEW_SELECTION",
                                                    "{0} < {1}".format(new_bldg_area_field, str(poly_min_area)))
            if common_lib.get_fids_for_selection(new_bldg_lyr)[1] > 0:
                arcpy.DeleteFeatures_management(new_bldg_lyr)
                arcpy.SelectLayerByAttribute_management(new_bldg_lyr, "CLEAR_SELECTION")

            new_bldg_reg = os.path.join(workspace, "new_bldg_reg")
            arcpy.SelectLayerByLocation_management(new_bldg_lyr, "INTERSECT", mp_footprints,
                                                   invert_spatial_relationship="INVERT")

            if common_lib.get_fids_for_selection(new_bldg_lyr)[1] > 0:
                arcpy.AddMessage("{0} new structures detected"
                                 .format(str(common_lib.get_fids_for_selection(new_bldg_lyr)[1])))
                # Eliminate holes from new buildings
                new_bldg_elim = os.path.join(workspace, "new_bldg_elim")
                arcpy.EliminatePolygonPart_management(new_bldg_lyr, new_bldg_elim, "AREA", minimum_area,
                                                      part_option="CONTAINED_ONLY")
                # Regularize new footprints
                arcpy.RegularizeBuildingFootprint_3d(new_bldg_elim, new_bldg_reg, 'RIGHT_ANGLES_AND_DIAGONALS',
                                                     tolerance=(las_cell_size * 2))
                arcpy.DeleteFeatures_management(new_bldg_lyr)
                arcpy.AddField_management(new_bldg_reg, update_field, "TEXT")
                arcpy.CalculateField_management(new_bldg_reg, update_field, "'New'")
                new_bldg_append = os.path.join(gdb, "new_bldg_append")
                arcpy.CopyFeatures_management(new_bldg_reg, new_bldg_append)
                arcpy.Append_management(new_bldg_append, output_fps, "NO_TEST")
                arcpy.Delete_management(new_bldg_append)

        # Select all buildings that intersect new or demolished areas
        arcpy.AddMessage("Checking for structures with changed extents")
        if arcpy.Exists(new_bldg_poly):
            arcpy.SelectLayerByLocation_management(footprint_lyr, "INTERSECT", new_bldg_poly)
        if arcpy.Exists(partial_demo_lg):
            arcpy.SelectLayerByLocation_management(footprint_lyr, "INTERSECT", partial_demo_lg,
                                                   selection_type="ADD_TO_SELECTION")

        if common_lib.get_fids_for_selection(footprint_lyr)[1] > 0:
            arcpy.AddMessage("{0} structures with changed extents detected"
                             .format(str(common_lib.get_fids_for_selection(footprint_lyr)[1])))
            if replace_changes == "true":
                arcpy.AddMessage("Replacing changed footprints")
                change_fps = os.path.join(workspace, "change_fps")
                arcpy.CopyFeatures_management(footprint_lyr, change_fps)
                change_region = os.path.join(workspace, "change_region")
                arcpy.CopyFeatures_management(footprint_lyr, change_region)
                arcpy.DeleteFeatures_management(footprint_lyr)
                if arcpy.Exists(new_bldg_poly):
                    arcpy.Append_management(new_bldg_poly, change_region, "NO_TEST")
                arcpy.env.mask = change_region
                change_areas = Con((ground_compare > 1), 1)
                # polygonize change areas
                if change_areas.maximum > 0:
                    change_poly = os.path.join(workspace, "change_poly")
                    arcpy.RasterToPolygon_conversion(change_areas, change_poly)
                    change_area_field = get_area_field(change_poly)
                    change_poly_lyr = "change_poly_lyr"
                    arcpy.MakeFeatureLayer_management(change_poly, change_poly_lyr)
                    arcpy.SelectLayerByAttribute_management(change_poly_lyr, "NEW_SELECTION",
                                                            "{0} > {1}".format(change_area_field, poly_min_area))
                    if common_lib.get_fids_for_selection(change_poly_lyr)[1] > 0:
                        change_poly_elim = os.path.join(workspace, "change_poly_elim")
                        arcpy.EliminatePolygonPart_management(change_poly_lyr, change_poly_elim, "AREA", minimum_area,
                                                              part_option="CONTAINED_ONLY")
                        change_poly_reg = os.path.join(workspace, "change_poly_reg")
                        arcpy.RegularizeBuildingFootprint_3d(change_poly_elim, change_poly_reg,
                                                             'RIGHT_ANGLES_AND_DIAGONALS', tolerance=(las_cell_size * 2))
                        arcpy.AddFields_management(change_poly_reg, [[update_field, "TEXT"], [iou_field, "FLOAT"]])
                        arcpy.CalculateField_management(change_poly_reg, update_field, "'Changed_Extent'")
                        change_poly_local = os.path.join(gdb, "change_poly_loc")
                        arcpy.CopyFeatures_management(change_poly_reg, change_poly_local)
                        # Calculate change poly id
                        change_poly_oid = arcpy.Describe(change_poly_local).OIDFieldName
                        join_field = "cp_id"
                        arcpy.AddField_management(change_poly_local, join_field, "LONG")
                        arcpy.CalculateField_management(change_poly_local, join_field, "!{0}!".format(change_poly_oid))
                        # Spatial Join change poly id to change footprints
                        change_fp_join = os.path.join(workspace, "change_fp_join")
                        arcpy.SpatialJoin_analysis(change_fps, change_poly_local, change_fp_join, "JOIN_ONE_TO_MANY")
                        arcpy.DeleteField_management(change_poly_local, join_field)
                        # Intersect change poly with change fps
                        change_poly_int = os.path.join(gdb, "change_poly_int")
                        arcpy.Intersect_analysis([change_poly_local, change_fp_join], change_poly_int)
                        # union change poly with change fps
                        change_poly_union = os.path.join(gdb, "change_poly_union")
                        arcpy.Union_analysis([change_poly_local, change_fp_join], change_poly_union)
                        # Create dictionary of IoU
                        int_area_dict = {}
                        union_area_dict = {}
                        iou_dict = {}
                        area_field = get_area_field(change_poly_int)
                        change_fid_field = "FID_change_poly_loc"
                        with arcpy.da.SearchCursor(change_poly_int, [change_fid_field, area_field]) as i_cur:
                            for row in i_cur:
                                if row[0] not in int_area_dict.keys():
                                    int_area_dict[row[0]] = row[1]
                                else:
                                    int_area_dict[row[0]] = int_area_dict[row[0]] + row[1]
                        with arcpy.da.SearchCursor(change_poly_union, [change_fid_field, area_field, join_field]) as u_cur:
                            for row in u_cur:
                                fid = row[0]
                                if fid == -1:
                                    fid = row[2]
                                if fid not in union_area_dict.keys():
                                    union_area_dict[fid] = row[1]
                                else:
                                    union_area_dict[fid] = union_area_dict[fid] + row[1]

                        for i in int_area_dict.keys():
                            if i in union_area_dict.keys():
                                iou = int_area_dict[i] / union_area_dict[i]
                                iou_dict[i] = iou
                        # Apply IoU values to change polys
                        iou_limit = 0.9
                        with arcpy.da.UpdateCursor(change_poly_local, [change_poly_oid, iou_field]) as u_cur:
                            for row in u_cur:
                                if row[0] in iou_dict.keys():
                                    val = iou_dict[row[0]]
                                    if val > iou_limit:
                                        arcpy.AddMessage("Deleting feature: " + str(row[0]))
                                        u_cur.deleteRow()
                                    else:
                                        row[1] = val
                                        u_cur.updateRow(row)



                        arcpy.Append_management(change_poly_local, output_fps, "NO_TEST")
                        arcpy.Delete_management(change_poly_local)
                        arcpy.Delete_management(change_poly_int)
                        arcpy.Delete_management(change_poly_union)
            else:
                arcpy.CalculateField_management(footprint_lyr, update_field, "'Changed_Extent'")
                change_poly_local = os.path.join(gdb, "change_poly_loc")
                arcpy.CopyFeatures_management(footprint_lyr, change_poly_local)
                arcpy.Append_management(change_poly_local, output_fps, "NO_TEST")
                arcpy.DeleteFeatures_management(footprint_lyr)
                arcpy.Delete_management(change_poly_local)

        # Identify remaining footprints that fall outside of accuracy tolerance
        # Extract to building footprints
        arcpy.AddMessage("Determining RMSE of remaining footprints")
        mse_avg = ZonalStatistics(mp_footprints, fp_oid, abs_error, "MEAN")

        rmse_field = "RMSE_new"
        rmse_id = "RMSE_id"
        if common_lib.field_exist(mp_footprints, rmse_field):
            arcpy.DeleteField_management(mp_footprints, rmse_field)
        if common_lib.field_exist(mp_footprints, rmse_id):
            arcpy.DeleteField_management(mp_footprints, rmse_id)
        arcpy.AddField_management(mp_footprints, rmse_id, "LONG")
        arcpy.CalculateField_management(mp_footprints, rmse_id, "!{0}!".format(fp_oid))

        fp_points = os.path.join(workspace, "fp_points")
        arcpy.FeatureToPoint_management(mp_footprints, fp_points, "INSIDE")

        rmse_points = os.path.join(workspace, "rmse_points")
        arcpy.sa.ExtractValuesToPoints(fp_points, mse_avg, rmse_points, "NONE", "VALUE_ONLY")

        arcpy.AddField_management(rmse_points, rmse_field, "FLOAT")
        arcpy.CalculateField_management(rmse_points, rmse_field, "!RASTERVALU!", "PYTHON_9.3", None)

        arcpy.JoinField_management(mp_footprints, rmse_id, rmse_points, rmse_id, rmse_field)
        arcpy.DeleteField_management(mp_footprints, rmse_id)

        # Select buildings with error above threshold and append to output
        arcpy.SelectLayerByAttribute_management(footprint_lyr, "NEW_SELECTION",
                                                "{0} > {1}".format(rmse_field, str(m_threshold)))

        if common_lib.get_fids_for_selection(footprint_lyr)[1] > 0:
            arcpy.AddMessage("{0} footprints found with RMSE outside threshold parameter"
                             .format(str(common_lib.get_fids_for_selection(footprint_lyr)[1])))
            arcpy.CalculateField_management(footprint_lyr, update_field, "'Changed_Vertical'")
            change_vert = os.path.join(gdb, "changed_vertical")
            arcpy.CopyFeatures_management(footprint_lyr, change_vert)
            arcpy.Append_management(change_vert, output_fps, "NO_TEST")
            arcpy.Delete_management(change_vert)
        else:
            arcpy.AddMessage("No remaining footprints found with RMSE outside threshold")
    else:

        arcpy.AddError("Input LAS Dataset must contain both Ground (2), and Building (6) class codes.")
        # omitClassCodes = [7, 12, 13, 14, 15, 16, 18]
        # filter_list = []
        # for row in class_list:
        #     if row not in omitClassCodes:
        #         filter_list.append(row)
        #
        # las_lyr = "las_lyr"
        # arcpy.MakeLasDatasetLayer_management(lasd, las_lyr, filter_list)
        #
        # mp_cell_size = round(m_cell_size / mp_m_per_unit)
        #
        # # Rasterize buildings
        # arcpy.AddMessage("Rasterizing 3D Buildings")
        # mp_bldg_ras = os.path.join(workspace, "bldg_ras")
        # arcpy.MultipatchToRaster_conversion(buildings, mp_bldg_ras)
        # mp_ras = os.path.join(workspace, "mp_ras")
        # if mp_m_per_unit != 1:
        #     arcpy.Times_3d(mp_bldg_ras, mp_m_per_unit, mp_ras)
        # else:
        #     mp_ras = mp_bldg_ras
        #
        # arcpy.env.snapRaster = mp_ras
        # arcpy.env.cellSize = mp_ras
        # arcpy.env.mask = mp_ras
        #
        # arcpy.AddMessage("Creating lidar surface")
        # las_bldg_ras = os.path.join(workspace, "las_bldg_ras")
        # arcpy.LasDatasetToRaster_conversion(las_lyr, las_bldg_ras, "ELEVATION", 'BINNING MAXIMUM LINEAR')
        #
        # # convert vertical units to meter
        # bldg_ras = os.path.join(workspace, "bldg_ras")
        # if las_m_per_unit != 1:
        #     arcpy.Times_3d(las_bldg_ras, las_m_per_unit, bldg_ras)
        # else:
        #     bldg_ras = las_bldg_ras
        #
        # # Subtract from reference raster
        # arcpy.AddMessage("Comparing surfaces")
        # compare_ras_save = os.path.join(workspace, "compare_ras")
        # compare_ras = Minus(bldg_ras, mp_ras)
        # compare_ras.save(compare_ras_save)
        #
        # # Square the result
        # mse_ras = compare_ras * compare_ras
        #
        # # Exract to building footprints
        # arcpy.AddMessage("Determining RMSE")
        # mse_avg = ZonalStatistics(mp_footprints, fp_oid, mse_ras, "MEAN")
        # rmse_id = "RMSE_id"
        # if common_lib.field_exist(mp_footprints, rmse_id):
        #     arcpy.DeleteField_management(mp_footprints, rmse_id)
        # arcpy.AddField_management(mp_footprints, rmse_id, "LONG")
        # arcpy.CalculateField_management(mp_footprints, rmse_id, "!{0}!".format(fp_oid))
        #
        # fp_points = os.path.join(workspace, "fp_points")
        # arcpy.FeatureToPoint_management(mp_footprints, fp_points, "INSIDE")
        #
        # rmse_points = os.path.join(workspace, "rmse_points")
        # arcpy.sa.ExtractValuesToPoints(fp_points, mse_avg, rmse_points, "NONE", "VALUE_ONLY")
        #
        # rmse_field = "RMSE_new"
        # arcpy.AddField_management(rmse_points, rmse_field, "FLOAT")
        # arcpy.CalculateField_management(rmse_points, rmse_field, "math.sqrt(!RASTERVALU!)", "PYTHON_9.3", None)
        #
        # if common_lib.field_exist(mp_footprints, rmse_field):
        #     arcpy.DeleteField_management(mp_footprints, rmse_field)
        #
        # arcpy.JoinField_management(mp_footprints, rmse_id, rmse_points, rmse_id, rmse_field)
        # arcpy.DeleteField_management(mp_footprints, rmse_id)
        #
        # # Select footprints outside threshold
        # arcpy.Select_analysis(mp_footprints, output_fps, "{0} > {1}".format(rmse_field, str(m_threshold)))

    if arcpy.Exists(aoi_proj):
        arcpy.Delete_management(aoi_proj)


except arcpy.ExecuteWarning:
    print(arcpy.GetMessages(1))
    arcpy.AddWarning(arcpy.GetMessages(1))

except NoChange:
    arcpy.AddWarning("No areas of change detected. Ensure the vertical tolerance and minimum area thresholds are within"
                     " your requirements")

except arcpy.ExecuteError:
    print(arcpy.GetMessages(2))
    arcpy.AddError(arcpy.GetMessages(2))

# Return any other type of error
except:
    # By default any other errors will be caught here
    #
    e = sys.exc_info()[1]
    print(e.args[0])
    arcpy.AddError(e.args[0])
