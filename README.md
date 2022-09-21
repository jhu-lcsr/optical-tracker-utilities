# Optical Tracker Utilities

Scripts used to generate tool definition files (i.e. relative positions of stray markers within a single rigid body) for optical trackers.  These scripts have been developped at the Johns Hopkins University and tested with the following optical tracking systems:
* [NDi](https://www.ndigital.com) (Northern Digital Inc) Polaris and Vicra using [**sawNDITracker**](https://github.com/jhu-saw/sawNDITracker)
* [Atracsys](https://www.atracsys-measurement.com) FusionTrack ft500 using [**sawAtracsysFusionTrack**](https://github.com/jhu-saw/sawAtracsysFusionTrack)

**sawNDITracker** and **sawAtracsysFusionTrack** are two C++ libraries interfacing with NDi and FusionTrack products.  These libraries provide a GUI as well as bridges to ROS 1, ROS 2 and OpenIGTLink.  These are not required to use the scripts in this repository.

# Scripts

## `tool_maker.py`

This script can be used to create a tool definition file from stray marker positions.  The script assumes the marker positions are provided using a ROS topic publishing the poses using a `geometry_msgs/PoseArray` message.  You can create the tool definition "live", i.e. while the optical tracker is running or you can record and replay a bag of stray marker poses.  When collecting the stray marker poses, the tool should be visible and static (i.e. do not move the tool nor the tracking system).  Make sure the stray markers on the tool are the only markers visible. 

The output format can be either the _Atracsys_ compatible `.ini` or our custom _SAW_ `.json` format.  The component **sawAtracsysFusionTrack** can load either. 

## `tool_converter.py`

Tool to convert tool definition files between the following formats:
* `.ini` text file from _Atracsys_.
* `.json` text file from **sawAtracsysFusionTrack**.  This format is based on the `.ini` format and was introduced for older Ubuntu distributions to avoid parsing `.ini` files.
* `.rom` binary files from _NDi_.
