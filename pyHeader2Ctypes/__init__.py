import re
import random
import os
import copy

indentStr = '    ' # 缩进字符默认使用四个空格

class CElements:
    __typedict =  {   # 类型转换字典
        'VIM_U32':'c_uint', 'VIM_BOOL':'c_uint', 'VIM_U8':'c_byte', 'VIM_CHAR':'c_byte', 'VIM_S32':'c_int', 'VIM_FR32':'c_uint', 'VIM_VOID*':'c_void_p',
        'VIM_DOUBLE':'c_double', 'VIM_FLOAT':'c_float', 'VIM_U64':'c_longlong','VIM_U16':'c_short',
        'unsigned long':'c_long',
        'unsigned int': 'c_uint',
        'VI_CHN':'c_uint', '__u32':'c_uint', '__s32':'c_uint',
        'VB_POOL':'c_uint',
        'VIM_CHAR*':'c_char_p',
        'VIM_U8*':'c_char_p',
        'VIM_S8':'c_ubyte',
        'VIM_S16':'c_short',
        'void*':'c_void_p',
        'char':'c_byte'
    }
    __convertdict = {}
    __items = [] # items包含了从指定文件中查找到的所有struct union enum
    __unknow_items = set() # 类型未知或定义未找到的struct union enum的名称
    __anonymous_items = set()
    __tbd_items = set() 

    __warn_msg = ''

    def __WarnMsgAppend(self,*arg):
        for i in arg:
            if type(i) == str:
                self.__warn_msg += i
            else:
                self.__warn_msg += i.strerror
        self.__warn_msg += '\n'

    def __FormatDocument(self,text):
        if text is None:
            return None
        pattern_comment = re.compile('#.*\n')
        comments = pattern_comment.findall(text)
        for comment in comments:
            text = text.replace(comment,'')
        newText = ''
        text = text.replace('\t',' ')
        for t in text.split(' '):       # replace multi-space with one space
            if t != '':
                newText = newText + t + ' '
        return newText
    def __LoadFromDir(self,directory):
        headerText = ''
        filecount = 0
        cmd_preprocess = 'clang -E '
        includestr = ''
        for filename in os.listdir(directory):
            if filename[-2:] == '.h':           # 删除此行将不筛选.h文件
                filename = directory + os.sep + filename
                if filename[-5:] == 'vim.h':
                    includestr = '#include "'+filename+'"\n' + includestr
                else:
                    includestr = includestr + '#include "'+filename+'"\n'
                filecount += 1
        with open('all.h', 'w') as includefile:
            includefile.write(includestr)
        cmd_preprocess += ' all.h > total.h'
        if filecount == 0 :
            self.__WarnMsgAppend("没有找到.h文件")
            return None
        os.system(cmd_preprocess)
        try:
            with open('total.h','r',encoding='utf-8') as f:
                headerText += f.read(1024*1000*10)
        except UnicodeDecodeError as e:
            with open('total.h','r',encoding='gbk') as f:
                headerText += f.read(1024*1000*10)
            # exit(self.__warn_msg)
        return self.__FormatDocument(headerText)

    # 在初始化函数中，首先查找其所有顶级元素，并保存在item中
    def __init__(self,directory):
        self.__convertdict = copy.copy(self.__typedict)
        self.__items = []
        self.__unknow_items = set()
        self.__tbd_items = set() 
        self.__anonymous_items = set()
        self.__warn_msg = ''
        headerText = self.__LoadFromDir(directory)
        if headerText is not None:
            self.__FindElements(headerText)

    def __FindElements(self,headerText):
        pattern_element_type = re.compile('(?:typedef)? *(?:enum|struct|union)')
        pattern_element_keychar = re.compile('[{};]')
        pattern_element_type_name = re.compile('(enum|struct|union) +(\w*) +([\w,]*) *;')
        pattern_element_type_type = re.compile('(enum|struct|union) *(\w*)')
        resultlist = []
        replaceList = []
        start,a,b,t = 0,0,0,0
        def __FormatElements(resultlist):
            for result in resultlist:
                item = {}
                text_type = result.get('type')
                if text_type is None:   # a instant announced element
                    try:
                        t,tn,n= pattern_element_type_name.findall(result['name'])[0]
                    except IndexError:
                        self.__WarnMsgAppend('error occured while parsing: ',result['name'])
                        continue
                    if ',' in n:
                        namelist = n.split(',')
                        for name in namelist:
                            self.__convertdict[name.replace('\t','').strip()] = self.__convertdict[tn]
                    else:
                        self.__convertdict[n] = self.__convertdict[tn]
                    continue
                item['name'] = result['name']
                t,tn = '',''
                if 'anony' in result: # a anonymous element
                    item['type'] = result['type']
                    try:
                        item['typename'] = result['typename']
                    except KeyError:
                        pass
                else:
                    try:
                        t,tn = pattern_element_type_type.findall(result['type'])[0]
                        item['type'] = t
                    except IndexError:
                        self.__WarnMsgAppend('error occured while parsing: ', result['type'])
                        continue
                newtype = ''
                if item['type'] == 'enum':
                    newtype = 'c_uint'
                else:
                    newtype = 'PY_' + item['name']
                if tn != '':
                    item['typename'] = tn
                    self.__convertdict[item['typename']] = newtype
                    self.__convertdict[item['name']] = newtype
                else:
                    try:
                        self.__convertdict[item['typename']] = 'PY_' + item['typename']
                        if len(item['type']) > 6:
                            self.__convertdict[item['type']] = 'PY_' + item['typename']
                    except KeyError:
                        self.__convertdict[item['name']] = newtype
                if item['type'] == 'enum':
                    item['members'] = self.__ParseEnum(result['content'])
                else:
                    item['members'] = self.__ParseStruct(result['content'])
                try:
                    if 'anony' in result:
                        self.__anonymous_items.add(self.__convertdict[item['typename']])
                        self.__unknow_items.remove(item['type'])
                    self.__unknow_items.remove(item['name'])
                except KeyError:
                    pass
                if item['type'] == 'enum':
                    self.__items.insert(0,item)
                else:
                    self.__items.append(item)
        while True:
            un_flag = 0
            deepth = 0
            findmode = 0 # 0=start 1=found{ 2=found} 3=found; 4=end
            try:
                a,b = pattern_element_type.search(headerText,b).regs[0] # find a new element header
            except AttributeError as e:
                # print(e,', NoneType means nothing found or reach the end of file')
                break
            start = a
            item = {}
            while True:
                t = b
                a,b = pattern_element_keychar.search(headerText,b).regs[0]
                keychar = headerText[a:b]
                if keychar == '{':
                    if findmode == 0:
                        findmode = 1
                        item['type'] = headerText[start:a].replace('\n',' ').strip()
                        start_content = b
                    elif findmode == 1:
                        deepth += 1
                    else:
                        print('err occured while parsing:\n'+headerText[start:b])
                        # exit(self.__warn_msg) #
                elif keychar == '}':
                    if findmode == 0:
                        print('err occured while parsing:\n'+headerText[start:b])
                        # exit(self.__warn_msg) # } without {
                    elif findmode == 1:
                        if deepth == 0:
                            item['content'] = headerText[start_content:a]
                            findmode = 2
                        else:
                            deepth = deepth - 1
                elif keychar == ';':
                    if findmode == 2:
                        item['name'] = headerText[t:a].replace('\n',' ').strip()
                        findmode = 4
                        break
                    elif findmode == 0:
                        item['name'] = headerText[start:b].replace('\n','')
                        break
                    else:
                        un_flag += 1
                        if un_flag > 10000:
                            print('find element excced max tries')
                            # exit(self.__warn_msg)
            typestr = item.get('type','')
            if item['name'] == '' or typestr == 'struct' or typestr == 'union':  # a anonymouns element
                if item['name'] == '':
                    newname = ''
                    while newname == '':
                        newname = item['type'][0:1] + '_' + str(random.random())[2:8]
                        if newname.upper() in self.__convertdict:
                            newname = ''
                    item['name'] = newname
                item['typename'] = item['name'].upper()
                item['anony'] = True
                replaceList.append((headerText[start:b],item['typename'] + ' ' + item['name'] + ';'))
            resultlist.append(item)
        for old,new in replaceList:
            headerText = headerText.replace(old, new)
        __FormatElements(resultlist)
        return headerText
    # 解析一个Struct或Union元素中的内容，即解析其成员。
    def __ParseStruct(self,text): # also works for Union
        if '{' in text:
            text = self.__FindElements(text)
        patter_type_name_number = re.compile('((?:struct|enum|union|unsigned)? *[\w]*[ \*]*) *(\w*) *([\[\]\(\)\w \+\-\*\/:]*) *;') 
        patter_type_typename = re.compile('(struct|enum|union|unsigned)? *([\w]*[ \*]*)') 
        pattern_number = re.compile('[\(\[] *(\w+) *[\)\]]')
        memberlist = []
        members = text.split('\n')
        for member in members:
            member = member.strip()
            if member.isspace() == False and member != '':
                item = {}
                basetype,typename,name,number = '','','',''
                try:
                    typename,name,number = patter_type_name_number.findall(member)[0]
                    basetype,typename = patter_type_typename.findall(typename)[0] # unpack typename like 'struct XXXX xxxx;'
                except IndexError:
                    pass
                if ':' in number:
                    item['bit'] = number.replace(':','').strip()
                else:
                    numberlist = pattern_number.findall(number.replace(' ',''))
                    if len(numberlist) > 0:
                        for number in numberlist:
                            try:
                                int(number,base=16)
                            except ValueError:
                                self.__tbd_items.add(number)
                        item['number'] = numberlist
                
                item['name'] = name.replace(' ','')
                item['type'] = typename.replace(' ','')
                if basetype != '':
                    item['type'] = basetype.replace(' ','') + ' ' + item['type']
                if item['name'] == '' and item['type'] == '':
                    continue
                if item['type'] not in self.__convertdict:
                    if '*' in item['type']:  # 是否因为星号导致类型没找到
                        typestr = item['type'].replace('*','')
                        typename = self.__convertdict.get(typestr)
                        if typename is not None:
                            self.__convertdict[item['type']] = 'POINTER(' + typename + ')'
                        else:
                            self.__unknow_items.add(item['type'])
                        # item['type'] = item['type'].replace('*','').strip()
                    else:                       # 如果不是，则认定为未知类型
                        self.__unknow_items.add(item['type'])
               
                memberlist.append(item)
        return memberlist 

    # 解析一个Enum中的所有元素
    def __ParseEnum(self,text):
        pattern_name_val = re.compile('([A-Za-z_]\w*)[ =]*(\w*) *,')
        __item_no__ = 0
        members = text.split('\n')
        memberlist = []
        for member in members:
            member = member.strip()
            if member.isspace() == False and member != '':
                item = {}
                try:
                    name,val = pattern_name_val.findall(member)[0]
                except IndexError:
                    continue
                item['name'] = name
                try:
                    if 'x' in val:
                        item['val'] = int(val, base=16)
                    else:
                        item['val'] = int(val)
                    __item_no__ = item['val']
                except ValueError:
                    item['val'] = __item_no__
                memberlist.append(item)
                __item_no__ += 1
        return memberlist
    
    # 将items内容输出为.py文件
    def DumpToStr(self):
        if len(self.__unknow_items) > 0 or len(self.__tbd_items) > 0 or self.__warn_msg != '':
            self.__WarnMsgAppend('【未找到定义】')
            for unknow_item in self.__unknow_items:
                self.__WarnMsgAppend(unknow_item)
            self.__WarnMsgAppend('\n\n【不确定的值】')
            for tbd_item in self.__tbd_items:
                self.__WarnMsgAppend(tbd_item)
            return '\'\'\'\n' + self.__warn_msg  + '\n\'\'\'\n\n'
        else:
            # https://www.python.org/dev/peps/pep-0263/
            result = '#!/usr/bin/python\n# -*- coding: <utf-8> -*-\n\nfrom ctypes import *\n\n' 
            for item in self.__items:
                if item['type'] == 'enum':
                    result = result + 'class ' + 'PY_' + item['name'] + '():\n'
                    memberliststr = indentStr + 'list = iter([ '
                    for member in item['members']:
                        result = result + indentStr + member['name'] + ' = ' + str(member['val']) 
                        memberliststr = memberliststr + '(\'' + member['name'] + '\',' + str(member['val']) +'), '
                        comment =  member.get('comment')
                        if comment is not None:
                            result = result + '    # ' + comment
                        result += '\n'
                    result = result + memberliststr + '])\n' + indentStr + 'def __iter__(self):\n' + indentStr*2 + 'return self.__list\n\n'
                elif item['type'] == 'struct' or item['type'] == 'union':
                    parentclass = 'Structure'
                    if item['type'] == 'union':
                        parentclass = 'Union'
                    try:
                        result = result + 'class ' + self.__convertdict[item['name']] + '(' + parentclass +'):\n'
                    except KeyError:
                        result = result + 'class ' + self.__convertdict[item['typename']] + '(' + parentclass +'):\n'
                    anonystr = indentStr + '_anonymous_=('
                    memberstr = indentStr + '_fields_=[\n'
                    memberno = 0
                    anonyno = 0
                    for member in item['members']:
                        if member['name'] == '' or member['type'] == '':
                            continue
                        member['name'] = member['name'].replace(' ','_')
                        memberno += 1
                        memberstr = memberstr + indentStr + '(\'' + member['name'] + '\', '
                        memtype = ''
                        try:
                            memtype = self.__convertdict[member['type']]
                            if memtype in self.__anonymous_items:
                                anonyno += 1
                                anonystr =  anonystr + '\'' + member['name'] + '\', '
                        except KeyError:
                            memtype = 'PY_'+member['type']
                            # self.__WarnMsgAppend('[输出文档]未知类型：',member['type'],'暂用名称',memtype)
                        bitnum = member.get('bit')
                        if bitnum is not None:
                            memtype = memtype + ', ' + bitnum
                        else:
                            number = member.get('number')
                            if number is not None:
                                for n in reversed(number):
                                    memtype = '(' + memtype + ' * ' + str(n) + ')'
                        memberstr += memtype
                        if memberno == len(item['members']):
                            memberstr = memberstr + ')]'
                        else:
                            memberstr = memberstr + '),'
                        memberstr += '\n'
                    if memberno == 0:
                        memberstr += indentStr + ']\n'
                    if anonyno > 0:
                        anonystr += ')\n'
                        result += anonystr
                    result = result + memberstr + '\n'
            return result
            