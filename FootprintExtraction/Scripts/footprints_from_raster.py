import arcpy
from arcpy.sa import *
import os
import sys
import common_lib
from split_features import split

arcpy.env.overwriteOutput = True

in_raster = arcpy.GetParameterAsText(0)
min_area = arcpy.GetParameterAsText(1)
split_features = arcpy.GetParameterAsText(2)
output_poly = arcpy.GetParameterAsText(3)
reg_circles = arcpy.GetParameterAsText(4)
circle_min_area = arcpy.GetParameterAsText(5)
min_compactness = arcpy.GetParameter(6)
circle_tolerance = arcpy.GetParameterAsText(7)
lg_reg_method = arcpy.GetParameterAsText(8)
lg_min_area = arcpy.GetParameterAsText(9)
lg_tolerance = arcpy.GetParameterAsText(10)
med_reg_method = arcpy.GetParameterAsText(11)
med_min_area = arcpy.GetParameterAsText(12)
med_tolerance = arcpy.GetParameterAsText(13)
sm_reg_method = arcpy.GetParameterAsText(14)
sm_tolerance = arcpy.GetParameterAsText(15)


workspace = "in_memory"
aprx = arcpy.mp.ArcGISProject("CURRENT")
home_directory = aprx.homeFolder

if os.path.exists(os.path.join(home_directory, "p20")):  # it is a package
    home_directory = os.path.join(home_directory, "p20")

gdb = aprx.defaultGeodatabase
scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
ras_desc = arcpy.Describe(in_raster)
ras_sr = ras_desc.spatialReference
m_per_unit = ras_sr.metersPerUnit
fc_delete_list = []


# Check if field exists in fc
def FieldExist(featureclass, fieldname):
    fieldList = arcpy.ListFields(featureclass, fieldname)
    fieldCount = len(fieldList)
    if fieldCount == 1:
        return True
    else:
        return False

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


def get_area_field(fc):
    path = arcpy.Describe(fc).catalogPath
    path_name = os.path.dirname(path)
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


def delete_existing(fc_list):
    for fc in fc_list:
        if arcpy.Exists(fc):
            arcpy.Delete_management(fc)


try:
    # Get area inputs in map units
    m_min_area = get_metric_from_areal_unit(min_area)
    poly_min_area = m_min_area / (m_per_unit ** 2)
    if med_min_area is not None:
        min_area_med_m = get_metric_from_areal_unit(med_min_area)
        min_area_med = min_area_med_m / (m_per_unit ** 2)
    if lg_min_area is not None:
        min_area_lg_m = get_metric_from_areal_unit(lg_min_area)
        min_area_lg = min_area_lg_m / (m_per_unit ** 2)

    # Create output building feature class
    out_gdb = os.path.dirname(output_poly)
    out_name = os.path.basename(output_poly)
    arcpy.CreateFeatureclass_management(out_gdb, out_name, "POLYGON", spatial_reference=ras_sr)

    # Shrink grow
    arcpy.AddMessage("Shrinking and growing raster areas to remove slivers")
    bldg_shrink = Shrink(in_raster, 1, 6)
    bldg_grow = None
    if bldg_shrink.maximum > 0:
        bldg_grow = Expand(bldg_shrink, 1, 6)
    else:
        bldg_grow = in_raster

    # Raster to polygon
    arcpy.AddMessage("Converting raster to polygon")
    bldg_poly = os.path.join(scratch_ws, "bldg_poly")
    arcpy.RasterToPolygon_conversion(bldg_grow, bldg_poly, "NO_SIMPLIFY")

    # Delete non value features
    with arcpy.da.UpdateCursor(bldg_poly, "gridcode") as cursor:
        for row in cursor:
            if row[0] == 0:
                cursor.deleteRow()

    # Select large buildings
    bldg_area = get_area_field(bldg_poly)
    bldg_lg = "bldg_lg"
    arcpy.MakeFeatureLayer_management(bldg_poly, bldg_lg, "{0} >= {1}".format(bldg_area, str(poly_min_area)))

    # Eliminate polygon part
    arcpy.AddMessage("Eliminating small holes")
    bldg_elim = os.path.join(scratch_ws, "bldg_elim")
    fc_delete_list.append(bldg_elim)
    arcpy.EliminatePolygonPart_management(bldg_lg, bldg_elim, "AREA", min_area)

    # Split using split features (identity) plus multipart to single part
    multi_single_part = os.path.join(scratch_ws, "bldg_mp_sp")
    split_bldg = os.path.join(scratch_ws, "split_bldg")
    fc_delete_list.append(split_bldg)
    non_reg_bldg = "non_reg_bldg"
    if arcpy.Exists(split_features):
        arcpy.AddMessage("Splitting polygons by reference features")

        arcpy.AddMessage(scratch_ws)

        arcpy.AddMessage("Copying split features...")
        copy_split = os.path.join(scratch_ws, "copy_split")
        arcpy.CopyFeatures_management(split_features, copy_split)

        arcpy.AddMessage("Removing identical shapes in split features")
        arcpy.management.DeleteIdentical(copy_split, "Shape", "4 Feet", 0)

        split_bldg = os.path.join(scratch_ws, "split_bldg")

        # custom split.
        # arcpy.Identity_analysis(bldg_elim, copy_split, split_bldg)
        split_bldg = split(scratch_ws, bldg_elim, copy_split, poly_min_area, split_bldg, 0, False)

#        arcpy.MakeFeatureLayer_management(split_bldg, non_reg_bldg)
        arcpy.MultipartToSinglepart_management(split_bldg, multi_single_part)
    else:
#        arcpy.MakeFeatureLayer_management(bldg_elim, non_reg_bldg)
        arcpy.MultipartToSinglepart_management(bldg_elim, multi_single_part)

    arcpy.AddMessage("Converting Multipart to singleparts")

    arcpy.MakeFeatureLayer_management(multi_single_part, non_reg_bldg)

    # add unique identifier
    non_reg_fc = arcpy.Describe(non_reg_bldg).catalogPath
    oid = arcpy.Describe(non_reg_fc).OIDFieldName
    unique_id = "unique_id"
    if not FieldExist(non_reg_fc, unique_id):
        arcpy.AddField_management(non_reg_fc, unique_id, "LONG")
    arcpy.CalculateField_management(non_reg_fc, unique_id, "!{}!".format(oid))

    area_field = get_area_field(non_reg_bldg)
    # Regularize circles
    if reg_circles:
        # Delete status field if it exists
        if FieldExist(non_reg_bldg, "STATUS"):
            arcpy.DeleteField_management(non_reg_bldg, "STATUS")

        # calculate compactness
        comp_field = "compactness"
        if not FieldExist(non_reg_bldg, comp_field):
            arcpy.AddField_management(non_reg_bldg, comp_field, "FLOAT")
        arcpy.CalculateField_management(non_reg_bldg, comp_field,
                                        "(4 * 3.14159 * !shape.area!) / (!shape.length! ** 2)", "PYTHON_9.3")
        # Select circle-like features
        arcpy.AddMessage("Selecting compact features")
        min_area_circle_m = get_metric_from_areal_unit(circle_min_area)
        min_area_circle = min_area_circle_m / (m_per_unit ** 2)

        expression = "{0} > {1} AND {2} > {3}".format(area_field, str(min_area_circle), comp_field, str(min_compactness))
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, "NEW_SELECTION", expression)

        # Get tolerance in map units
        circle_tolerance_m = get_metric_from_linear_unit(circle_tolerance)
        circle_tolerance_map = circle_tolerance_m / m_per_unit

        # Regularize
        arcpy.AddMessage("Regularizing circles")
        circle_reg = os.path.join(workspace, "circle_reg")
        fc_delete_list.append(circle_reg)
        arcpy.RegularizeBuildingFootprint_3d(non_reg_bldg, circle_reg, "CIRCLE", circle_tolerance_map, min_radius=1,
                                             max_radius=1000000000)

        # Select circles that successfully regularized
        my_status = "STATUS"
        circle_list = []
        with arcpy.da.UpdateCursor(circle_reg, [unique_id, my_status]) as cursor:
            for row in cursor:
                if row[1] == 0:
                    circle_list.append(row[0])
                else:
                    cursor.deleteRow()

        # Delete circle features from draft polygons
        with arcpy.da.UpdateCursor(non_reg_bldg, unique_id) as cursor:
            for row in cursor:
                if row[0] in circle_list:
                    cursor.deleteRow()

        # Append circles to output fc
        arcpy.Append_management(circle_reg, output_poly, "NO_TEST")
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, "CLEAR_SELECTION")


    # Regularize large buildings
    if lg_reg_method != "NONE":
        # Select large buildings
        arcpy.AddMessage("Selecting large building areas")
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, "NEW_SELECTION", '{0} >= {1}'.format(area_field, str(min_area_lg)))

        # Get tolerance in map units
        lg_tolerance_m = get_metric_from_linear_unit(lg_tolerance)
        lg_tolerance_map = lg_tolerance_m / m_per_unit



        # Regularize
        arcpy.AddMessage("Regularizing large buildings")
        lg_bldg_reg = os.path.join(workspace, "lg_bldg_reg")
        arcpy.RegularizeBuildingFootprint_3d(non_reg_bldg, lg_bldg_reg, lg_reg_method, lg_tolerance_map)

        # Simplify buildings
        lg_bldg_simp = os.path.join(workspace, "lg_bldg_simp")
        arcpy.SimplifyBuilding_cartography(lg_bldg_reg, lg_bldg_simp, lg_tolerance)

        # Append to output
        arcpy.Append_management(lg_bldg_simp, output_poly, "NO_TEST")
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, "SWITCH_SELECTION")

    # Regularize medium buildings
    if med_reg_method != "NONE":
        # Select medium buildings
        arcpy.AddMessage("Selecting medium building areas")
        if lg_reg_method != "NONE":
            selection = "SUBSET_SELECTION"
        else:
            selection = "NEW_SELECTION"
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, selection, '{0} >= {1}'.format(area_field, str(min_area_med)))

        # Get tolerance in map units
        med_tolerance_m = get_metric_from_linear_unit(med_tolerance)
        med_tolerance_map = med_tolerance_m / m_per_unit

        # Regularize
        arcpy.AddMessage("Regularizing medium buildings")
        med_bldg_reg = os.path.join(workspace, "med_bldg_reg")
        arcpy.RegularizeBuildingFootprint_3d(non_reg_bldg, med_bldg_reg, med_reg_method, med_tolerance_map)

        # Simplify buildings
        med_bldg_simp = os.path.join(workspace, "med_bldg_simp")
        arcpy.SimplifyBuilding_cartography(med_bldg_reg, med_bldg_simp, med_tolerance, min_area)

        # Append to output
        arcpy.Append_management(med_bldg_simp, output_poly, "NO_TEST")
        arcpy.SelectLayerByAttribute_management(non_reg_bldg, "CLEAR_SELECTION")

    # Regularize small buildings
    if sm_reg_method != "NONE":
        # Select small buildings
        arcpy.AddMessage("Selecting small building areas")
        if med_reg_method != "NONE":
            arcpy.SelectLayerByAttribute_management(non_reg_bldg, "NEW_SELECTION", '{0} < {1}'
                                                    .format(area_field, str(min_area_med)))
        else:
            if lg_reg_method != "NONE":
                arcpy.SelectLayerByAttribute_management(non_reg_bldg, "NEW_SELECTION", '{0} < {1}'
                                                        .format(area_field, str(min_area_lg)))

        # Get tolerance in map units
        sm_tolerance_m = get_metric_from_linear_unit(sm_tolerance)
        sm_tolerance_map = sm_tolerance_m / m_per_unit

        # Regularize
        arcpy.AddMessage("Regularizing small buildings")
        sm_bldg_reg = os.path.join(workspace, "sm_bldg_reg")
        arcpy.RegularizeBuildingFootprint_3d(non_reg_bldg, sm_bldg_reg, sm_reg_method, sm_tolerance_map)

        # Simplify buildings
        sm_bldg_simp = os.path.join(workspace, "sm_bldg_simp")
        arcpy.SimplifyBuilding_cartography(sm_bldg_reg, sm_bldg_simp, sm_tolerance, min_area)

        # Append to output
        arcpy.Append_management(sm_bldg_simp, output_poly, "NO_TEST")

except arcpy.ExecuteWarning:
    print(arcpy.GetMessages(1))
    arcpy.AddWarning(arcpy.GetMessages(1))

except arcpy.ExecuteError:
    print(arcpy.GetMessages(2))
    arcpy.AddError(arcpy.GetMessages(2))

# Return any other type of error
except:
    # By default any other errors will be caught here
    #
    e = sys.exc_info()[1]
    print((e.args[0]))
    arcpy.AddError(e.args[0])



