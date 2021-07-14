from pyHeader2Ctypes import CElements
import os
import sys

if __name__ == '__main__':

    dirlist = {}
    dirindex = 0
    dirname = None
    try:
        dirname = sys.argv[1]
    except IndexError:
        pass
    if dirname == None:
        for dir in os.listdir():
            if os.path.isdir(dir) and dir != '.git' and dir[0:1] != '_' and dir != 'pyHeader2Ctypes' and dir[0:1] != '.' and dir != 'include' and dir != 'webfiles':
                dirlist[str(dirindex)] = dir
                dirindex += 1
        for i in range(0,len(dirlist)):
            print(str(i),':',dirlist[str(i)])
        print('choose a dir: ')
        # a = str(input())
        # try:
        #     dirname = dirlist[a]
        # except KeyError:
        #     print('no such option:',a)
        #     exit(0)
    dirname = 'venc'
    celements = CElements(dirname)
    celements.DumpToFile('out.py')

    # 取消注释以输出typedict和items的json内容
    # with open('debug_typedict.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.typedict,jsonfile)
    # with open('debug_items.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.items,jsonfile)