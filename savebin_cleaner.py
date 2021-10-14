file_path = r""
file_path_out = r""
def clean_savebin_bools(bindata):
    numOfData = int.from_bytes(bindata[12:16], byteorder='little')
    
    for index in range(1, numOfData + 1):
        offset = index * 0x10
        typeOffset = offset + 0x4
        valueOffset = offset + 0x8
        typeId = bindata[typeOffset] % 8
        if typeId == 4:
            bindata[valueOffset + 1] = 0
            bindata[valueOffset + 2] = 0
            bindata[valueOffset + 3] = 0

data = None
with open(file_path, mode='rb+') as file:
    data = bytearray(file.read())
clean_savebin_bools(data)

with open(file_path_out, mode='wb+') as file:
    file.write(data)
