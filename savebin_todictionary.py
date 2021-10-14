import struct
filename = r""
data = None
with open(filename, 'rb+') as file:
    data = bytearray(file.read())

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
import pickle
with open('out.pickle', 'wb') as serialize:
    pickle.dump(saveDict, serialize)
