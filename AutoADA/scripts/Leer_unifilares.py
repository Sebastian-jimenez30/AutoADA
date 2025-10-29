import os
import re
import glob
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.table import Table, TableStyleInfo
from collections import OrderedDict

symbol_key_descriptions = {
    'EQUIPOS_DE_MANIOBRA.LIB2 1': 'INTERRUPTOR',
    'EQUIPOS_DE_MANIOBRA.LIB2 2': 'SECCIONADOR',
    'EQUIPOS_DE_MANIOBRA.LIB2 3': 'TIERRA RIGHT',
    'EQUIPOS_DE_MANIOBRA.LIB2 4': 'BAHIA UP',
    'EQUIPOS_DE_MANIOBRA.LIB2 5': 'BOTON BAHIA',
    'EQUIPOS_DE_MANIOBRA.LIB2 8': 'BAHIA DOWN',
    'EQUIPOS_DE_MANIOBRA.LIB2 9': 'BAHIA RIGHT',
    'EQUIPOS_DE_MANIOBRA.LIB2 10': 'BAHIA LEFT',
    'EQUIPOS_DE_MANIOBRA.LIB2 11': 'TIERRA LEFT',
    'EQUIPOS_DE_MANIOBRA.LIB2 12': 'TIERRA UP',
    'EQUIPOS_DE_MANIOBRA.LIB2 13': 'TIERRA DOWN',
    'SELECTORES Y EQUIPOS ESPECIALES.LIB2 24': 'CMD',
    'SELECTORES Y EQUIPOS ESPECIALES.LIB2 80': 'SELECTOR',
    'SELECTORES Y EQUIPOS ESPECIALES.LIB2 37': 'SELECTOR',
}

def display_name(line, datos):
    match = re.search(r"DisplayName\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos.setdefault('DisplayName', []).append(match.group(1))

def display_type(line, datos):
    match = re.search(r"DisplayType\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos.setdefault('DisplayType', []).append(match.group(1))

def display_size(line, datos):
    match = re.search(r"DisplaySize\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos.setdefault('DisplaySize', []).append(match.group(1))

def library_list(line, datos):
    if 'LibraryList' in line:
        datos['LibraryList'] = {}
        datos['lib_count'] = 1
    elif 'LibraryList' in datos and 'lib_count' in datos:
        match = re.search(rf"\t{datos['lib_count']}:\s*Name\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['LibraryList'][datos['lib_count']] = match.group(1)
            datos['lib_count'] += 1
        elif 'BackgroundColor' in line or not line.startswith('\t'):
            del datos['lib_count']

def background_color(line, datos):
    match = re.search(r"BackgroundColor\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos.setdefault('BackgroundColor', []).append(match.group(1))

def wallpaper_style(line, datos):
    match = re.search(r"WallpaperStyle\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos.setdefault('WallpaperStyle', []).append(match.group(1))

def page_list(line, datos):
    if 'PageList' in line:
        datos['PageList'] = {}
        datos['page_count'] = 1
    elif 'PageList' in datos and 'page_count' in datos:
        if not line.startswith('\t'):
            del datos['page_count']
            return
        match = re.search(rf"\t{datos['page_count']}:\s*Name\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['PageList'].setdefault(datos['page_count'], {})['Name'] = match.group(1)
            datos['page_count'] += 1
        else:
            for key in ['Center', 'ZoomPercent', 'AspectRatio', 'HelpFilesKey']:
                match = re.search(rf"\t{key}\s*\[\d+\]\:\s*(.+)", line)
                if match:
                    datos['PageList'].setdefault(datos['page_count'] - 1, {})[key] = match.group(1)

def line_scale_max(line, datos):
    match = re.search(r"LineScaleMax\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['LineScaleMax'] = match.group(1)

def flow_speed_max(line, datos):
    match = re.search(r"FlowSpeedMax\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['FlowSpeedMax'] = match.group(1)

def flow_space_max(line, datos):
    match = re.search(r"FlowSpaceMax\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['FlowSpaceMax'] = match.group(1)

def gps_upper_left(line, datos):
    match = re.search(r"GPSUpperLeft\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['GPSUpperLeft'] = match.group(1)

def gps_lower_right(line, datos):
    match = re.search(r"GPSLowerRight\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['GPSLowerRight'] = match.group(1)

def wcs_upper_left(line, datos):
    match = re.search(r"WCSUpperLeft\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['WCSUpperLeft'] = match.group(1)

def wcs_lower_right(line, datos):
    match = re.search(r"WCSLowerRight\s*\[\d+\]\:\s*(.+)", line)
    if match:
        datos['WCSLowerRight'] = match.group(1)

def declutter_range_list(line, datos):
    if 'DeclutterRangeList' in line:
        datos['DeclutterRangeList'] = {}
        datos['range_count'] = 1
    elif 'DeclutterRangeList' in datos and 'range_count' in datos:
        if not line.startswith('\t'):
            if 'EndPercent' not in line:
                del datos['range_count']
            return
        match = re.search(rf"\t{datos['range_count']}:\s*StartPercent\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['DeclutterRangeList'].setdefault(datos['range_count'], {})['StartPercent'] = match.group(1)
        match = re.search(rf"\tEndPercent\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['DeclutterRangeList'].setdefault(datos['range_count'], {})['EndPercent'] = match.group(1)
            datos['range_count'] += 1

def layers(line, datos):
    if 'Layers' in line:
        datos['Layers'] = {}
        datos['layer_count'] = 1
    elif 'Layers' in datos and 'layer_count' in datos:
        if not line.startswith('\t'):
            del datos['layer_count']
            return
        match = re.search(rf"\t{datos['layer_count']}:\s*Name\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['Layers'].setdefault(datos['layer_count'], {})['Name'] = match.group(1)
            datos['layer_count'] += 1
        else:
            match = re.search(rf"\tGroupFlags\s*\[\d+\]\:\s*(.+)", line)
            if match:
                datos['Layers'].setdefault(datos['layer_count'] - 1, {})['GroupFlags'] = match.group(1)

def overlays(line, datos):
    if 'Overlays' in line:
        datos['Overlays'] = {}
        datos['overlay_count'] = 1
    elif 'Overlays' in datos and 'overlay_count' in datos:
        if not line.startswith('\t'):
            del datos['overlay_count']
            return
        match = re.search(rf"\t{datos['overlay_count']}:\s*Name\s*\[\d+\]\:\s*(.+)", line)
        if match:
            datos['Overlays'].setdefault(datos['overlay_count'], {})['Name'] = match.group(1)
            datos['overlay_count'] += 1
        else:
            for key in ['Enabled', 'Locked']:
                match = re.search(rf"\t{key}\s*\[\d+\]\:\s*(.+)", line)
                if match:
                    datos['Overlays'].setdefault(datos['overlay_count'] - 1, {})[key] = match.group(1)

def object_list(line, datos):
    if 'ObjectList' not in datos:
        datos['ObjectList'] = {}
    if 'ObjectList' in line:
        datos['object_count'] = 1
    elif 'ObjectList' in datos and 'object_count' in datos:
        if not line.startswith('\t'):
            if 'next_line' in datos:
                del datos['next_line']
            del datos['object_count']
            return
        # Handle continuation lines for multi-line fields first
        if 'next_line' in datos and datos['next_line']:
            datos['ObjectList'][datos['object_count']-1][datos['next_key']] = line.strip()
            del datos['next_line']
            del datos['next_key']
            return
        # Be resilient to numbering by matching any object index rather than the expected counter
        match = re.search(r"\t\d+:\s*(\w+)\s*\[\d+\]\:", line)
        if match:
            tipo = match.group(1)
            datos['ObjectList'][datos['object_count']] = {'Type': tipo}
            datos['object_count'] += 1
        else:
            for key in ['Location','Size','ZDepth','Layer','Overlay','Rotation','Blinking','Enterable','Selectable',
                        'PickListDataEntry','SingleClickProcessing','FixedLocation','FixedSize','CoordinateType',
                        'Color Base','Color Link','Color State','Symbol Key','Symbol Flags','Variables','DefinedVariables','Data Link',
                        'Data State','Line Width','Line Width Type','Line Style','Font Key','Font Size',
                        'Format String','Default Arrow Direction','String']:
                match = re.search(rf"\t{key}\s*\[\d+\]\:\s*(.+)", line)
                if match:
                    value = match.group(1)
                    # Fields that use '~' have their content on the next line; capture as continuation
                    if key in ('Color Link', 'Data Link', 'Variables', 'DefinedVariables') and value.startswith('~'):
                        datos['next_line'] = True
                        datos['next_key'] = key
                    else:
                        datos['ObjectList'][datos['object_count']-1][key] = value
                        if key == 'Symbol Key':
                            descripcion = symbol_key_descriptions.get(value, 'DESCONOCIDO')
                            datos['ObjectList'][datos['object_count']-1]['Symbol_Description'] = descripcion

def leer_archivo(archivo):
    datos = OrderedDict()
    funciones = OrderedDict([
        ('DisplayName', display_name),
        ('DisplayType', display_type),
        ('DisplaySize', display_size),
        ('LibraryList', library_list),
        ('BackgroundColor', background_color),
        ('WallpaperStyle', wallpaper_style),
        ('PageList', page_list),
        ('LineScaleMax', line_scale_max),
        ('FlowSpeedMax', flow_speed_max),
        ('FlowSpaceMax', flow_space_max),
        ('GPSUpperLeft', gps_upper_left),
        ('GPSLowerRight', gps_lower_right),
        ('WCSUpperLeft', wcs_upper_left),
        ('WCSLowerRight', wcs_lower_right),
        ('DeclutterRangeList', declutter_range_list),
        ('Layers', layers),
        ('Overlays', overlays),
        ('ObjectList', object_list)
    ])

    with open(archivo, encoding='utf-8') as f:
        for line in f:
            for _, fn in funciones.items():
                fn(line, datos)
    return datos
