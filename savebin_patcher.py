import pickle
import json
saveDict = None
with open('sample/out.pickle', 'rb') as pickleData:
    saveDict = pickle.load(pickleData)

patches = None
with open('patches/online.json', 'rb') as patchOnline:
    patches = json.load(patchOnline)


def patch(dictionary, patches):
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
print("Before", saveDict["Talisman"]["Slot997"])
patch(saveDict, patches)
print("After", saveDict["Talisman"]["Slot997"])
