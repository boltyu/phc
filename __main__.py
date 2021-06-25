import pyHeader2Ctypes
import os
import sys

if __name__ == '__main__':

    dirname = './tests'
    try:
        dirname = sys.argv[1]
    except KeyError:
        pass
    celements = pyHeader2Ctypes.CElements(dirname)
    celements.ParseMembers()
    celements.DumpToFile('out.py')

    # 取消注释以输出typedict和items的json内容
    # with open('debug_typedict.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.typedict,jsonfile)
    # with open('debug_items.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.items,jsonfile)