#!/usr/bin/python3
import struct
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('in_file', nargs=1)
parser.add_argument('out_file', nargs=1)

parser.add_argument('-d', dest='patch_folders', type=str, nargs="*")

args = parser.parse_args()


in_file = args.in_file[0]
out_file = args.out_file[0]
patch_folders = args.patch_folders

data = None

try:
    with open(in_file, 'rb+') as file:
        data = bytearray(file.read())
except FileNotFoundError as e:
    print("Please supply a path to a gravity rush 2 save file.")
    exit(-1)

def get_varname(arr, chunkOffset):
    stringOffset = int.from_bytes(arr[chunkOffset: chunkOffset + 4], 'little')
    index = stringOffset
    while arr[index] != 0:
        index += 1
    return arr[stringOffset:index].decode('utf-8')
    
def get_type(arr, chunkOffset):
    return arr[chunkOffset + 0x4] % 8

def get_value_offset(arr, chunkOffset):
    return int.from_bytes(arr[chunkOffset + 4: chunkOffset + 8], 'little') >> 4

def read_vector(arr, vectorOffset):
    return struct.unpack_from('<ffff', arr, offset=vectorOffset)

def read_string(arr, stringOffset, length):
    start = stringOffset
    
    if length == 0:
        end = start
    else:
        end = stringOffset + length - 1 # remove one because null terminated

    strBytes = arr[start:end]
    try:
        return strBytes.decode('utf-8')
    except:
        pass
    return strBytes # Only so it can be converted to json

def parse_dict(parent, count, metadata):
    for _ in range(count):
        parse_chunk(parent, metadata)

def parse_chunk(root, metadata):
    metadata["count"] += 1
    
    chunkOffset = metadata["offset"]
    metadata["offset"] += 0x10
    arr = metadata["buffer"]
    
    varName = get_varname(arr, chunkOffset)
    dataType = get_type(arr, chunkOffset)
    valueOffset = get_value_offset(arr, chunkOffset)
    varBytesValue = arr[chunkOffset+0x8:chunkOffset+0xC]

    if arr[chunkOffset + 0x4] & 8 == 0:
        root[varName] = (dataType, None)
        return
    
    if dataType == 0:
        dictRoot = {}
        count = int.from_bytes(varBytesValue, 'little')
        parse_dict(dictRoot, count, metadata)
        root[varName] = dictRoot
        # dictionary
    elif dataType == 1:
        # float32
        root[varName] = struct.unpack('<f', varBytesValue)[0]
    elif dataType == 2:
        # vector
        root[varName] = read_vector(arr, valueOffset)
    elif dataType == 3:
        # string
        strLength = int.from_bytes(varBytesValue, 'little')
        root[varName] = read_string(arr, valueOffset, strLength)
    elif dataType == 4:
        # boolean
        root[varName] = arr[chunkOffset+0x8] > 0
    else:
        # unknown
        pass

def convert_to_dict(saveData):
    numOfData = int.from_bytes(saveData[0xC: 0x10], 'little')
    metadata = {
        "offset": 0x10,
        "buffer": saveData, 
        "count": 0
    }
    root = {}
    while metadata["count"] < numOfData:
        parse_chunk(root, metadata)
    return root

saveDict = convert_to_dict(data)

import json

def do_patch(dictionary, patches):
    for [path, value] in patches:
        subDict: dict = dictionary
        # from first to second to lest
        pathLength = len(path)
        pathLastIndex = max(pathLength - 1, 0)
        for keyIndex in range(pathLastIndex):
            key = path[keyIndex]
            if subDict.get(key) == None:
                subDict[key] = {}
                continue
            subDict = subDict[key]
        valueKey = path[pathLastIndex]
        if type(value) == list:
            value = tuple(value)
        subDict[valueKey] = value

import os

for patch_folder in patch_folders:
    for patch_fp in os.listdir(patch_folder):
        if not patch_fp.endswith(".json"):
            continue
        full_path = os.path.join(patch_folder, patch_fp)
        patch = json.load(open(full_path))
        do_patch(saveDict, patch)

import copy
import struct

def fnv1a_32(char_bytes):
    prime = 0x01000193
    offset_basis = 0x811c9dc5
    h = offset_basis

    for char_byte in char_bytes:
        h = h ^ char_byte
        h = (h * prime) % 0x100000000
    return h

def analyze_dict(dictionary, results): 
    for (key, value) in dictionary.items():
        results["stringTotalSize"] += len(key.encode("utf-8")) + 1
        results["entries"] += 1
        if type(value) == tuple:
            # If it is null then it is not contributing to anything
            if len(value) == 4: 
                results["vectors"] += 1
        if type(value) == bytearray:
            results["stringTotalSize"] += len(value) + 1
        elif type(value) == str:
            results["stringTotalSize"] += len(value.encode("utf-8")) + 1
        elif type(value) == dict:
            analyze_dict(value, results)

def write_buffer(buffer, index, byteArray):
    byteIndex = 0
    for byteValue in byteArray:
        buffer[index + byteIndex] = byteValue
        byteIndex += 1

def write_varname(buffer, varName, write_pointers):
    chunkOffset = write_pointers["data"]
    stringOffset = write_pointers["strings"]
    write_buffer(buffer, chunkOffset, stringOffset.to_bytes(4, 'little'))
    varNameBytes = varName.encode('utf-8')
    write_buffer(buffer, stringOffset, varNameBytes)
    write_pointers["strings"] += len(varNameBytes) + 1


def write_hash(buffer, varName, write_pointers):
    hash = fnv1a_32(varName.encode('utf-8'))
    chunkOffset = write_pointers["data"]
    write_buffer(buffer, chunkOffset + 12, hash.to_bytes(4, 'little'))

def serialize_dict(rootDict, buffer, write_pointers):
    for (key, value) in rootDict.items():
        serialize_chunk(value, key, buffer, write_pointers)
  
def serialize_chunk(value, varName, buffer, write_pointers):
    write_varname(buffer, varName, write_pointers)
    write_hash(buffer, varName, write_pointers)
    chunkOffset = write_pointers["data"]
    write_pointers["data"] += 0x10
    if type(value) == dict:
        write_buffer(buffer, chunkOffset + 4, b"\x08")
        write_buffer(buffer, chunkOffset + 8, len(value).to_bytes(4, 'little'))
        serialize_dict(value, buffer, write_pointers)
    elif type(value) == float:
        write_buffer(buffer, chunkOffset + 4, b"\x09")
        write_buffer(buffer, chunkOffset + 8, struct.pack("<f", value))
    elif type(value) == tuple:
        if len(value) == 4:
            vectorOffset = write_pointers["vectors"]
            typeValue = (vectorOffset << 4) + 0xA
            for floatValue in value:
                struct.pack_into("<f", buffer, vectorOffset, floatValue)
                vectorOffset += 4
            write_pointers["vectors"] += 0x10
            write_buffer(buffer, chunkOffset + 4, typeValue.to_bytes(4, 'little'))
            write_buffer(buffer, chunkOffset + 8, (16).to_bytes(4, 'little'))
        elif len(value) == 2:
            typeValue = value[0]
            write_buffer(buffer, chunkOffset + 4, typeValue.to_bytes(4, 'little'))
        else:
            raise Exception('Invalid tuple count!')
    elif type(value) == str:
        stringOffset = write_pointers["strings"]
        stringBytes = value.encode('utf-8')
        write_buffer(buffer, stringOffset, stringBytes)
        stringLength = len(stringBytes) + 1
        write_pointers["strings"] += stringLength
        typeValue = (stringOffset << 4) + 0xB
        write_buffer(buffer, chunkOffset + 4, typeValue.to_bytes(4, 'little'))
        write_buffer(buffer, chunkOffset + 8, (stringLength).to_bytes(4, 'little'))
    elif type(value) == bytearray:
        stringOffset = write_pointers["strings"]
        stringBytes = value
        write_buffer(buffer, stringOffset, stringBytes)
        stringLength = len(stringBytes) + 1
        write_pointers["strings"] += stringLength
        typeValue = (stringOffset << 4) + 0xB
        write_buffer(buffer, chunkOffset + 4, typeValue.to_bytes(4, 'little'))
        write_buffer(buffer, chunkOffset + 8, (stringLength).to_bytes(4, 'little'))
    elif type(value) == bool:
        write_buffer(buffer, chunkOffset + 4, b"\x0C")
        write_buffer(buffer, chunkOffset + 8, b"\x01" if value == True else b"\x00")
    else:
        raise Exception("Not implemented")
    

def dict_to_savebin(dictionary):
    magic = b"ggdL" + b"\x89\x06\x33\x01"
    info = {
        "entries": 0,
        "vectors": 0,
        "stringTotalSize": 0
    }
    analyze_dict(dictionary, info)
    
    totalFileSize = 0x10 + (info["entries"] + info["vectors"] ) * 0x10 + info["stringTotalSize"]
    buffer = bytearray(totalFileSize)
    write_buffer(buffer, 0, magic)
    write_buffer(buffer, 8, totalFileSize.to_bytes(4, 'little'))
    write_buffer(buffer, 12, info["entries"].to_bytes(4, 'little'))
    
    section_offsets = {
        "data": 16,
        "vectors": 16 * (info["entries"] + 1),
        "strings": 16 * (info["entries"] + info["vectors"]  + 1)
    }
    # This is to make it easier to not have
    # to keep track of the entry index
    write_pointers = copy.deepcopy(section_offsets)
    for (key, value) in dictionary.items():
        serialize_chunk(value, key, buffer, write_pointers)
    return buffer


saveBuffer = dict_to_savebin(saveDict)

with open(out_file, 'wb') as out:
    out.write(saveBuffer)

