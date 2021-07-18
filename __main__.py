from pyHeader2Ctypes import CElements
import traceback
import os
import sys

if __name__ == '__main__':
    dirlist = {}
    dirindex = 0
    dirname = None
    for dir in os.listdir('tmp'):
        if os.path.isdir('tmp'+os.sep+dir) and dir != '.git' and dir[0:1] != '_' and dir != 'pyHeader2Ctypes' and dir[0:1] != '.' and dir != 'include' and dir != 'webfiles':
            dirlist[str(dirindex)] = dir
            dirindex += 1
    for i in range(0,len(dirlist)):
        print(str(i),':',dirlist[str(i)])
    print('choose a dir: ')
    a = str(input())
    try:
        dirname = dirlist[a]
    except KeyError:
        print('no such option:',a)
        exit(0)

    celements = CElements('tmp'+os.sep+dirname)
    result = celements.DumpToStr()
    filename = 'out.py'
    with open(filename,'w',encoding='utf-8') as outfile:
        outfile.write(result)
    
