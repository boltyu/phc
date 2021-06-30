import re
import random
import os
import copy

indentStr = '    ' # 缩进字符默认使用四个空格

class CElements:
    typedict = {   # 类型转换字典
        'VIM_U32':'c_uint', 'VIM_BOOL':'c_uint', 'VIM_U8':'c_uint', 'VIM_CHAR':'c_uint', 'VIM_S32':'c_uint', 'VIM_FR32':'c_uint', 'VIM_VOID*':'c_void_p',
        'VIM_DOUBLE':'c_double', 'VIM_FLOAT':'c_float', 'VIM_U64':'c_longlong','VIM_U16':'c_uint',
        'unsigned long':'c_long',
        'unsigned int': 'c_uint',
        'VI_CHN':'c_uint', '__u32':'c_uint', '__s32':'c_uint'
    }
    macrodict = {} # 宏定义转换字典，暂未使用
    items = [] # items包含了从文件中识别到的所有struct union enum
    unknow_items = set() # 类型未知/定义未找到的struct union enum的名称
    
    cur_dir = ''

    def FormatDocument(self,text):
        pattern_comment1 = re.compile('//.*')
        pattern_comment2 = re.compile('/\*.*?\*/',re.DOTALL)
        textlen = len(text)
        newText = ''
        for pattern in [pattern_comment1,pattern_comment2]: # remove comment
            textpos = 0
            while textpos < textlen:
                comment = pattern.search(text,textpos)
                if comment is None:
                    newText += text[textpos:]
                    break
                newText += text[textpos:comment.start()]
                textpos = comment.end()
            text = copy.copy(newText)
            newText = ''
        newText = ''
        text = text.replace('\t',' ')
        for t in text.split(' '):       # replace multi-space with one space
            if t != '':
                newText = newText + t + ' '
        return newText
    def LoadFromDir(self,directory):
        headerText = ''
        dir_current = directory
        filecount = 0
        for filename in os.listdir(dir_current):
            if filename[-2:] == '.h':           # 删除此行将不筛选.h文件
                filename = dir_current + os.sep + filename
                filecount += 1
                try:
                    with open(filename,'r',encoding='utf-8') as f:
                        headerText += f.read(1024*1000*10)
                except UnicodeDecodeError as e:
                    with open(filename,'r',encoding='gbk') as f:
                        headerText += f.read(1024*1000*10)
                except Exception as e:
                    print(e)
                    exit(0)
        if filecount == 0 :
            print(directory,"中没有找到.h文件")
            exit(0)

        return self.FormatDocument(headerText)
    
    
    # 查找元素的表达式
    pattern = re.compile('(?:struct|union|enum)[ \n]*\w*[ \n]*{.*?}[A-Z0-9_\[\] ,*]*;',re.DOTALL)
    pattern_ex1 = re.compile('typedef[ ]*(?:struct|union|enum)[ ]+[a-zA-Z0-9_]+[ ]+[\w*\[\]]+;')
    pattern_name = re.compile('}[ ]*?([A-Z0-9_]+[ ]*\*?)[ ]*[;,]',re.DOTALL) 
    pattern_name_ex1 = re.compile('([\w\[\]]+)[ ]*[;,]')
    pattern_type = re.compile('(struct|union|enum)[\w \n]*{')
    pattern_type_name = re.compile('(?:struct|union|enum)[ ]+(\w+)')
    pattern_text = re.compile('{(.*)}',re.DOTALL)
    pattern_macro = re.compile('#define[ ]+(\w+)[ ]+([\dxa-fA-F]+)')
    pattern_anonymous_union = re.compile('(?<!\w\w|f )(?:union|struct|enum)[ \n]*{.*?}[\w ,\[\]0-9\*]*;',re.DOTALL)

    def FindElements(self,headerText):
        ## 找到所有固定值的宏，将宏名称直接替换为值，此处只做替换并未保存
        macros = self.pattern_macro.findall(headerText)
        for name,val in macros:
            headerText = headerText.replace(name,val)
        ## 先检查所有匿名的Union和Struct，将其随机命。   查找格式为     struct{...}...;
        anonymous_union = self.pattern_anonymous_union.findall(headerText)
        for union in anonymous_union:
            item = {}
            errorcount = 0
            while True:# random error(same val) may cause potentional infinite recycle
                errorcount += 1
                if errorcount > 10:
                    print(union[:100],'\n......\n',union[-100:],'\n以上解析有误,headerText保存至error.txt')
                    with open('error.txt','w') as f:
                        f.write(headerText)
                    exit(0)
                name_prefix = union.strip()[0:5].replace('\n','').replace(' ','').replace('{','').replace('}','')
                try:
                    item['name'] = self.pattern_name.findall(union)[0]  # unsupport array naming: xxxx[n]
                except IndexError:
                    item['name'] = (name_prefix + '_' + str(random.random())[3:7]).upper()
                tmpval = self.typedict.get(item['name'])
                if tmpval == None:
                    self.typedict[item['name']] = 'PY_' + item['name']
                    item['type'] = name_prefix
                    item['text'] = self.pattern_text.findall(union)[0]
                    if item['type'] == 'enum':
                        self.typedict[item['name']] = 'c_uint'
                        item['members'] = self.ParseEnum(item['text'])
                    else:
                        item['members'] = self.ParseStruct(item['text'])
                    self.items.insert(0,item)
                    # self.items[item['name']] = item 
                    headerText = headerText.replace(union,item['name'] + ' ' + item['name'].lower() + ';')
                    break
        ## 其次检查所有命名的Struct和Union和       typedef struct $STRUCT_NAME {} $INST_NAME;           
        elementList = self.pattern.findall(headerText)
        for element in elementList:
            item = {}
            item['type'] = self.pattern_type.findall(element)[0]
            try:
                item['text'] = self.pattern_text.findall(element)[0]
            except IndexError:
                continue
            try:
                item['name'] = self.pattern_type_name.findall(element)[0]
                self.typedict[item['name']] = 'PY_' + item['name']
                self.unknow_items.remove(item['name'])
            except (IndexError, KeyError):
                pass
            try:
                item['name'] = self.pattern_name.findall(element)[0].replace(' ','')
                self.typedict[item['name']] = 'PY_' + item['name']
                self.unknow_items.remove(item['name'])
            except (IndexError, KeyError):
                pass
            if item['type'] == 'enum':
                self.typedict[item['name']] = 'c_uint'
            self.items.append(item)  
            # self.items[item['name']] = item 
        ## 最后检查所有滞后定义的Struct和Union      struct $STRUCT_NAME $INST_NAME;      # 待解决：滞后定义的typedef struct将使用最先定义的typedef struct的类型名称
        instance_union = self.pattern_ex1.findall(headerText)
        pattern_number = re.compile('\[([A-Z_0-9]*)\]')
        for union in instance_union:
            tmpnamelist = self.pattern_name_ex1.findall(union)
            try:
                typename = self.pattern_type_name.findall(union)[0]
            except IndexError:
                print('[查找元素]解析类型错误, 原文: ',union)
                exit(0)
            for name in tmpnamelist:
                item = {}
                try:
                    item['number'] = pattern_number.findall(name)
                    if len(item['number']) > 0:
                        try:
                            for i in item['number']:
                                i = int(i)
                        except ValueError:
                            print('[查找元素]不确定的值：',i)
                    else:
                        del item['number']
                except IndexError:
                    pass
                try:
                    item['type'] = self.typedict[typename]
                    self.typedict[name] = self.typedict[typename]
                except KeyError:
                    self.unknow_items.add(typename)
                    item['type'] = typename
                    typename = 'PY_' + typename
                    self.typedict[item['type']] = typename
                    #item['name'] ???

    # 在初始化函数中，首先查找其所有顶级元素，并保存在item中
    def __init__(self,directory):
        self.cur_dir = directory
        headerText = self.LoadFromDir(directory)
        self.FindElements(headerText)

    # 解析一个Struct或Union元素中的内容，即解析其成员。
    def ParseStruct(self,text): # also works for Union  由于struct和union成员内容的格式类似，所以都使用此函数
        pattern_name = re.compile('(\w+)[0-9\[\] ]*(?=;)')
        pattern_number = re.compile('\[([0-9A-Z_]*)\]')
        memberlist = []
        members = text.split('\n')
        for member in members:
            member = member.strip()
            if member.isspace() == False and member != '':
                item = {}
                try:
                    item['number'] = pattern_number.findall(member)
                    if len(item['number']) > 0:
                        try:
                            for i in item['number']:
                                member = member.replace('['+i+']','')
                                i = int(i)
                        except ValueError:
                            print('[解析成员]不确定的值：',i)
                    else:
                        del item['number']
                except IndexError:
                    pass
                try:
                    item['name'] = pattern_name.findall(member)[0]
                except IndexError:
                    print('不能解析的句式:',member)
                    continue
                try:
                    item['type'] = member.replace(item['name'],'').replace(';','')
                    if 'struct' in item['type'] or 'enum' in item['type'] or 'union' in item['type']:
                        item['type'] = item['type'].replace('union','').replace('enum','').replace('struct','')
                    item['type'] = ' '.join(item['type'].split()).strip().replace(' *','*')# replace multi-space with one space
                    if item['type'] not in self.typedict:
                        if '*' in item['type']:  # 是否因为星号导致类型没找到
                            self.typedict[item['type']] = 'POINTER(' + self.typedict[item['type'].replace('*','')] + ')'
                            # item['type'] = item['type'].replace('*','').strip()
                        else:                       # 如果不是，则认定为未知类型
                            self.unknow_items.add(item['type'])
                except IndexError:
                    print('\n以下字符未被解析，如果没有使用可以忽略：\n',member)
                    continue
                memberlist.append(item)
        return memberlist 

    # 解析一个Enum中的所有元素
    def ParseEnum(self,text):
        pattern_name = re.compile('([A-Za-z][A-Za-z0-9_]*)=?')
        pattern_val = re.compile('=[ ]*([0-9]+)[ ]*,')
        __item_no__ = 0
        members = text.split('\n')
        memberlist = []
        for member in members:
            member = member.strip()
            if member.isspace() == False and member != '':
                item = {}
                try:
                    item['name'] = pattern_name.findall(member)[0]
                except IndexError:
                    if not member.isspace() and member != '':
                        print('不能解析的Enum成员:',member)
                    continue
                try:
                    item['val'] = int(pattern_val.findall(member)[0])
                    __item_no__ = item['val']
                except IndexError:
                    item['val'] = __item_no__
                memberlist.append(item)
                __item_no__ += 1
        return memberlist
    # 此函数开始解析items中所有元素的成员内容，如果不执行此函数，元素的成员内容仍以text的形式保存在['text']键中
    def ParseMembers(self):
        for item in self.items:
            if item['type'] == 'struct':
                item['members'] = self.ParseStruct(item['text'])
            elif item['type'] == 'union':
                item['members'] = self.ParseStruct(item['text'])
            elif item['type'] == 'enum':
                item['members'] = self.ParseEnum(item['text'])
        # 从includeText查找剩余未定义元素
        includeText = self.LoadFromDir(self.cur_dir + os.sep + 'include')
        unknow_items = copy.copy(self.unknow_items)
        for unknow_item in unknow_items:
            pattern_include_item = re.compile('(?:struct|union|enum) .*' + unknow_item + '[\w\n ]*{.*}[\w \n]*;',re.DOTALL)
            pattern_include_item1 = re.compile('(?:struct|union|enum)[\n ]*{.*} ?' + unknow_item + ' ?;',re.DOTALL)
            pattern_include_item3 = re.compile('(?:typedef )?(?:struct|union|enum).*?(?<! )}.*?;',re.DOTALL)
            pattern_result = pattern_include_item3.findall(includeText)
            resultlist = []
            for i in pattern_result:
                if len(pattern_include_item.findall(i)) > 0 or len(pattern_include_item1.findall(i)) > 0:
                    resultlist.append(i)
            if len(resultlist) == 1:
                self.FindElements(resultlist[0])
            elif len(resultlist) == 0: 
                pass
            else:
                print(unknow_item,'匹配到多项:')
                for i in resultlist:
                    print(i[:100],'......',i[-100:])
                exit(0)
        # 下面的内容冗余，待完善
        for item in self.items:
            if item['type'] == 'struct':
                try:
                    item['members']
                except KeyError:
                    item['members'] = self.ParseStruct(item['text'])
            elif item['type'] == 'union':
                try:
                    item['members']
                except KeyError:
                    item['members'] = self.ParseStruct(item['text'])
            elif item['type'] == 'enum':
                try:
                    item['members']
                except KeyError:
                    item['members'] = self.ParseEnum(item['text'])
           
    # 将items内容输出为.py文件
    def DumpToFile(self,filename):
        result = 'from ctypes import *\n\n'
        for item in self.items:
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
                result = result + memberliststr + '])\n' + indentStr + 'def __iter__(self):\n' + indentStr*2 + 'return self.list\n\n'
            elif item['type'] == 'struct' or item['type'] == 'union':
                parentclass = 'Structure'
                if item['type'] == 'union':
                    parentclass = 'Union'
                result = result + 'class ' + self.typedict[item['name']] + '(' + parentclass +'):\n'
                anonystr = indentStr + '_anonymous_=('
                memberstr = indentStr + '_fields_=[\n'
                memberno = 0
                anonyno = 0
                for member in item['members']:
                    memberno += 1
                    memberstr = memberstr + indentStr + '(\'' + member['name'] + '\','
                    memtype = ''
                    try:
                        memtype = self.typedict[member['type']]
                        if member['type'][0:5] == 'UNION':
                            anonyno += 1
                            anonystr =  anonystr + '\'' + member['name'] + '\', '
                    except KeyError:
                        memtype = 'PY_'+member['type']
                        # print('[输出文档]未知类型：',member['type'],'暂用名称',memtype)
                    number = member.get('number')
                    if number is not None:
                        for n in reversed(number):
                            memtype = '(' + memtype + '*' + str(n) + ')'
                    memberstr += memtype
                    if memberno == len(item['members']):
                        memberstr = memberstr + ')]'
                    else:
                        memberstr = memberstr + '),'
                    comment =  member.get('comment')
                    if comment is not None:
                        memberstr = memberstr + '    # ' + comment
                    memberstr += '\n'
                if memberno == 0:
                    memberstr += indentStr + ']\n'
                if anonyno > 0:
                    anonystr += ')\n'
                    result += anonystr
                result = result + memberstr + '\n'
        for unknow_item in self.unknow_items:
            print('[输出文档]未找到定义：',unknow_item)
        with open(filename,'w',encoding='utf-8') as outfile:
            outfile.write(result)

'''
a tough format:
    # bad style: printf("/*"); printf("*/");
a confused and bad re: 
    pattern_include_item1 = re.compile('(?:typedef )?(?:struct|union|enum).*{.*} ?' + unknow_item + ';',re.DOTALL)
'''
