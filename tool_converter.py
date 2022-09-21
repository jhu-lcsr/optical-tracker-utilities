#!/usr/bin/env python

"""
Author: Brendan Burkhart
Created on: 2022-7-22

(C) Copyright 2022 Johns Hopkins University (JHU), All Rights Reserved.

--- begin cisst license - do not edit ---

This software is provided "as is" under an open source license, with
no warranty.  The complete license can be found in license.txt and
http://www.cisst.org/cisst/license.txt.

--- end cisst license ---
"""

import argparse
import configparser
import datetime
import json
import pathlib

import numpy as np

import ndi_tool


class AtracsysToolDefinition:
    def __init__(self, markers, tool_id=None, pivot=None):
        self.id = tool_id
        self.markers = markers
        self.pivot = pivot

    @staticmethod
    def from_ini(ini):
        def point_to_array(point):
            return np.array([float(point["x"]), float(point["y"]), float(point["z"])])

        marker_count = int(ini["geometry"]["count"])
        markers = [point_to_array(ini[f"fiducial{i}"]) for i in range(marker_count)]
        pivot = point_to_array(ini["pivot"]) if "pivot" in ini else None
        tool_id = ini["geometry"].get("id", None)

        return AtracsysToolDefinition(markers, tool_id, pivot)

    def to_ini(self):
        def array_to_point(array):
            return {"x": str(array[0]), "y": str(array[1]), "z": str(array[2])}

        ini = configparser.ConfigParser()
        ini["geometry"] = {}
        ini["geometry"]["count"] = str(len(self.markers))

        if self.id is not None:
            ini["geometry"]["id"] = str(self.id)

        for i, marker in enumerate(self.markers):
            ini[f"fiducial{i}"] = array_to_point(marker)

        if self.pivot is not None:
            ini["pivot"] = array_to_point(self.pivot)

        return ini


class SAWToolDefinition:
    def __init__(self, tool_id, markers, pivot=None):
        self.id = tool_id
        self.markers = np.array(markers)
        self.pivot = pivot

    @staticmethod
    def from_json(json_dict):
        def point_to_array(point):
            return np.array([point["x"], point["y"], point["z"]])

        assert json_dict.get("count", 0) == len(json_dict["fiducials"])
        pivot = point_to_array(json_dict["pivot"]) if "pivot" in json_dict else None
        markers = [point_to_array(f) for f in json_dict["fiducials"]]

        tool_id = json_dict.get("id", None)

        return SAWToolDefinition(tool_id, markers, pivot)

    def to_json(self):
        def array_to_point(array):
            return {"x": array[0], "y": array[1], "z": array[2]}

        json_dict = {}

        if self.id is not None:
            json_dict["id"] = int(self.id)

        json_dict["count"] = len(self.markers)
        json_dict["fiducials"] = [array_to_point(m) for m in self.markers]

        if self.pivot is not None:
            json_dict["pivot"] = array_to_point(self.pivot)

        return json_dict


def read_rom(file_name: str) -> SAWToolDefinition:
    with open(file_name, "rb") as f:
        data = f.read()
        tool = ndi_tool.NDIToolDefinition.decode(data)

    saw_tool = SAWToolDefinition(None, tool.geometry.markers, None)

    return saw_tool


def write_rom(tool: SAWToolDefinition, file_name: str):
    tool = ndi_tool.NDIToolDefinition()
    tool.header.date = datetime.date.today()
    tool.geometry.markers = tool.markers
    if tool.pivot is not None:
        print(
            "NOTE: NDI .rom format doesn't support pivot, centering coordinate system on pivot instead"
        )
        tool.geometry.markers -= tool.pivot

    with open(file_name, "wb") as f:
        data = ndi_tool.NDIToolDefinition.encode(tool)
        f.write(data)


def read_saw(file_name) -> SAWToolDefinition:
    with open(file_name, "r") as f:
        json_dict = json.load(f)
        return SAWToolDefinition.from_json(json_dict)


def write_saw(tool: SAWToolDefinition, file_name: str):
    json_dict = tool.to_json()
    with open(file_name, "w") as f:
        json.dump(json_dict, f, indent=4)


def read_ini(file_name: str) -> SAWToolDefinition:
    ini = configparser.ConfigParser()
    ini.read(file_name)

    atracys_tool = AtracsysToolDefinition.from_ini(ini)
    return SAWToolDefinition(atracys_tool.id, atracys_tool.markers, atracys_tool.pivot)


def write_ini(tool: SAWToolDefinition, file_name: str):
    atracys_tool = AtracsysToolDefinition(tool.markers, tool.id, tool.pivot)

    ini = atracys_tool.to_ini()
    with open(file_name, "w") as f:
        ini.write(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input", type=str, help="Input file")
    parser.add_argument("-o", "--output", type=str, default="", help="Output file")
    args = parser.parse_args()

    input_extension = pathlib.Path(args.input).suffix
    output_extension = pathlib.Path(args.output).suffix

    if input_extension == ".rom":
        tool = read_rom(args.input)
    elif input_extension == ".json":
        tool = read_saw(args.input)
    elif input_extension == ".ini":
        tool = read_ini(args.input)
    else:
        raise ValueError(
            "Only NDI .rom, Atracsys .ini, and SAW .json formats are supported!"
        )

    if args.output == "":
        print(json.dumps(tool.to_json(), indent=4, default=str))
    elif output_extension == ".rom":
        write_rom(tool, args.output)
    elif output_extension == ".json":
        write_saw(tool, args.output)
    elif output_extension == ".ini":
        write_ini(tool, args.output)
    else:
        raise ValueError(
            "Only NDI .rom, Atracsys .ini, and SAW .json formats are supported!"
        )
