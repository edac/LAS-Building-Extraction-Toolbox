import arcpy
import os
import tempfile
import glob
import time


toolbox_dir=os.path.dirname(os.path.realpath(__file__))


class Toolbox(object):
    def __init__(self):
        self.label = "Building Extraction Toolbox"
        self.alias = "ArcGIS Building Extraction Toolbox"

        # List of tool classes associated with this toolbox
        self.tools = [Building_Extractor]#, NDVIBuilding_Filter, Building_Filter ]
class Building_Extractor(object):
    def __init__(self):
        self.label = "LIDAR Building Extraction Tool"
        self.description = "LIDAR Building Extraction Tool"
        self.canRunInBackground = False

    def getParameterInfo(self):
        lasdir = arcpy.Parameter(displayName="LAS Input Directory", name="LAS Input Directory", datatype="DEFolder", parameterType="Required", direction="Input") 
        min_height = arcpy.Parameter(displayName="Building Minimum Height", name="Building Minimum Height", datatype="GPLinearUnit", parameterType="Required", direction="Input",category="Classify LAS Buildings Options")
        min_height.value="2 Meters"
        min_area = arcpy.Parameter(displayName="Building Minimum Area", name="Building Minimum Area", datatype="GPArealUnit", parameterType="Required", direction="Input",category="Classify LAS Buildings Options")
        min_area.value="50 SquareMeters"
        cell_size = arcpy.Parameter(displayName="Raster Cell Size", name="Raster Cell Size", datatype="GPLinearUnit", parameterType="Required", direction="Input",category="Classify LAS Buildings Options")
        cell_size.value="0.8 Meters"
       
        minimum_building_area = arcpy.Parameter(displayName="Minimum Building Area", name="Minimum Building Area", datatype="GPArealUnit", parameterType="Required", direction="Input",category="Footprints From Raster Options")
        minimum_building_area.value="500 SquareFeet"
        minimum_circle_area = arcpy.Parameter(displayName="Minimum Circle Area", name="Minimum Circle Area", datatype="GPArealUnit", parameterType="Required", direction="Input",category="Footprints From Raster Options")
        minimum_circle_area.value="5000 SquareFeet"   
        
        largeregularization_method = arcpy.Parameter(displayName="Large Regularization Method",name="Large Regularization Method",datatype="GPString",parameterType="Required",direction="Input",category="Large Building Options")
        largeregularization_method.value = 'ANY_ANGLE'
        largeregularization_method.filter.list = ['RIGHT_ANGLES_AND_DIAGONALS','RIGHT_ANGLES','ANY_ANGLE']
        minimum_lg_area = arcpy.Parameter(displayName="Minimum Area", name="Minimum Area (Large Building Option)", datatype="GPArealUnit", parameterType="Required", direction="Input",category="Large Building Options")
        minimum_lg_area.value="25000 SquareFeet" 
        largetolerance = arcpy.Parameter(displayName="Minimum Tolerance", name="Minimum Tolerance (Large Building Option)", datatype="GPLinearUnit", parameterType="Required", direction="Input",category="Large Building Options")
        largetolerance.value="6 Feet"


        mediumregularization_method = arcpy.Parameter(displayName="Medium Regularization Method",name="Medium Regularization Method",datatype="GPString",parameterType="Required",direction="Input",category="Medium Building Options")
        mediumregularization_method.value = 'RIGHT_ANGLES_AND_DIAGONALS'
        mediumregularization_method.filter.list = ['RIGHT_ANGLES_AND_DIAGONALS','RIGHT_ANGLES','ANY_ANGLE']
        minimum_md_area = arcpy.Parameter(displayName="Minimum Area", name="Minimum Area  (Medium Building Option)", datatype="GPArealUnit", parameterType="Required", direction="Input",category="Medium Building Options")
        minimum_md_area.value="5000 SquareFeet" 
        mediumtolerance = arcpy.Parameter(displayName="Minimum Tolerance", name="Minimum Tolerance  (Medium Building Option)", datatype="GPLinearUnit", parameterType="Required", direction="Input",category="Medium Building Options")
        mediumtolerance.value="3 Feet"

        smallregularization_method = arcpy.Parameter(displayName="Small Regularization Method",name="Small Regularization Method",datatype="GPString",parameterType="Required",direction="Input",category="Small Building Options")
        smallregularization_method.value = 'RIGHT_ANGLES'
        smallregularization_method.filter.list = ['RIGHT_ANGLES_AND_DIAGONALS','RIGHT_ANGLES','ANY_ANGLE']
        smalltolerance = arcpy.Parameter(displayName="Minimum Tolerance", name="Minimum Tolerance (Small Building Option)", datatype="GPLinearUnit", parameterType="Required", direction="Input",category="Small Building Options")
        smalltolerance.value="3 Feet"
       
        outputdir = arcpy.Parameter(displayName="Output Directory", name="Output Directory", datatype="DEFolder", parameterType="Required", direction="Input")
        
        parameters = [lasdir,outputdir,min_height,min_area,cell_size,minimum_building_area,minimum_circle_area,largeregularization_method,minimum_lg_area,largetolerance,mediumregularization_method,minimum_md_area,mediumtolerance,smallregularization_method,smalltolerance]
        return parameters

    def execute(self, parameters, messages):
        
        arcpy.CheckOutExtension("3D")
        lasdir = parameters[0].valueAsText
        outputdir = parameters[1].valueAsText
        lasdir_basename=os.path.basename(lasdir)
        min_height = parameters[2].valueAsText
        min_area=parameters[3].valueAsText
        cell_size = parameters[4].valueAsText
        minimum_building_area = parameters[5].valueAsText
        minimum_circle_area= parameters[6].valueAsText
        
        largeregularization_method=parameters[7].valueAsText
        minimum_lg_area=parameters[8].valueAsText
        largetolerance=parameters[9].valueAsText
        mediumregularization_method=parameters[10].valueAsText
        minimum_md_area=parameters[11].valueAsText
        mediumtolerance=parameters[12].valueAsText
        smallregularization_method=parameters[13].valueAsText
        smalltolerance=parameters[14].valueAsText

        timestr = time.strftime("%Y%m%d-%H%M%S")
        out_name=lasdir_basename+"_building_footprints_"+timestr+".gdb"
        arcpy.management.CreateFileGDB(outputdir, out_name)

        raster_input = os.path.join(outputdir,out_name,lasdir_basename)
       
        files=glob.glob(os.path.join(lasdir,"*.LAS"))

       


        ScriptTest01_lasd=os.path.join(tempfile.gettempdir(),"tempfile.lasd")
        arcpy.AddMessage("Creating LAS Dataset")
        arcpy.management.CreateLasDataset(input=files, out_las_dataset=ScriptTest01_lasd, folder_recursion="NO_RECURSION", in_surface_constraints=[], compute_stats="COMPUTE_STATS", relative_paths="RELATIVE_PATHS", create_las_prj="NO_FILES")
        arcpy.AddMessage("Running 3d Classify")
        # Process: Classify LAS Building (Classify LAS Building) (3d)
        ScriptTest01_lasd_2_ = arcpy.ddd.ClassifyLasBuilding(in_las_dataset=ScriptTest01_lasd, min_height=min_height, min_area=min_area, compute_stats="COMPUTE_STATS", extent="DEFAULT", boundary="", process_entire_files="PROCESS_EXTENT", point_spacing="", reuse_building="RECLASSIFY_BUILDING", photogrammetric_data="NOT_PHOTOGRAMMETRIC_DATA", method="STANDARD", classify_above_roof="NO_CLASSIFY_ABOVE_ROOF", above_roof_height="", above_roof_code=None, classify_below_roof="NO_CLASSIFY_BELOW_ROOF", below_roof_code=None, update_pyramid="UPDATE_PYRAMID")[0]
        arcpy.AddMessage("3d Classification Complete")
        arcpy.AddMessage("Creating Draft Footprint Raster")
        # Process: Create Draft Footprint Raster (Create Draft Footprint Raster) (FootprintExtraction)
        arcpy.ImportToolbox(os.path.join(toolbox_dir,'FootprintExtraction',"FootprintExtraction.tbx"))
        arcpy.FootprintExtraction.CreateDraftFootprintRaster(Input_LAS_Dataset=ScriptTest01_lasd_2_, Out_Raster_Folder=os.path.join(toolbox_dir,"scratch"), Output_Mosaic_Dataset=raster_input, Cell_Size=cell_size)

        # Process: Footprints from Raster (Footprints from Raster) (FootprintExtraction)
        bldgfootprints2 = os.path.join(outputdir,out_name,lasdir_basename+"_bldgfootprints2")
        arcpy.FootprintExtraction.FootprintsFromRaster(Input_Raster=raster_input, Minimum_Building_Area=minimum_building_area, Output_Footprints=bldgfootprints2, Regularize_Circles=True, Minimum_Circle_Area=minimum_circle_area, Minimum_Compactness=0.85, Circle_Tolerance="10 Feet", LargeRegularization_Method=largeregularization_method, Minimum_Lg_Area=minimum_lg_area, LargeTolerance=largetolerance, Medium_Regularization_Method=mediumregularization_method, Minimum_Med_Area=minimum_md_area, Medium_Tolerance=mediumtolerance, Small_Regularization_Method=smallregularization_method, Small_Tolerance=smalltolerance)
        arcpy.AddMessage("Complete")
        arcpy.AddMessage("Output file: "+bldgfootprints2)




        return

