import pickle
import copy
import struct
from fnvhash import fnv1a_32

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

saveDict = {}

saveBuffer = dict_to_savebin(saveDict)
with open('out.bin', 'wb') as out:
    out.write(saveBuffer)
