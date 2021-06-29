import re
import random
import os
import copy

indentStr = '    ' # 缩进字符默认使用四个空格

class CElements:
    typedict = {   # 类型转换字典
        'VIM_U32':'c_uint', 'VIM_BOOL':'c_uint', 'VIM_U8':'c_uint', 'VIM_CHAR':'c_uint', 'VIM_S32':'c_uint', 'VIM_FR32':'c_uint', 'VIM_VOID*':'c_void_p',
        'VIM_DOUBLE':'c_double', 'VIM_FLOAT':'c_float', 'VIM_U64':'c_longlong','VIM_U16':'c_uint',
        'unsignedlong':'c_long',  # 由于解析方法的原因，unsigned long在这里写法需要去掉空格
        'unsignedint': 'c_uint',
        'VI_CHN':'c_uint', '__u32':'c_uint', '__s32':'c_uint'
    }
    macrodict = {} # 宏定义转换字典，暂未使用
    items = []     # items包含了从文件中识别到的所有struct union enum，类型为dict/json
    unknow_items = set() # 类型未知/定义未找到的struct union enum的名称
    
    cur_dir = ''

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

        return headerText
    
    
    # 查找元素的表达式
    pattern = re.compile('(?<!//)[\t ]*((?:typedef)?[\t| ]*(?:struct|union|enum)[\t \n]*\w*[\t \n]*{.*?}[A-Z0-9_\[\] ,*]*;)',re.DOTALL)
    pattern_ex1 = re.compile('(?<!//|/\*)[\t ]*(?:typedef)?[\t ]*(?:struct|union|enum)[\t ]+[a-zA-Z0-9_]+[\t ]+[\w*\[\]]+;')
    pattern_name = re.compile('}[\t ]*?([A-Z0-9_]+[\t ]*\*?)[\t ]*[;,]',re.DOTALL) 
    pattern_name_ex1 = re.compile('([\w\[\]]+)[\t ]*[;,]')
    pattern_type = re.compile('(struct|union|enum)[\w \t\n]*{')
    pattern_type_name = re.compile('(?:typedef)?[\t ]*(?:struct|union|enum)[\t ]+(\w+)')
    pattern_text = re.compile('{(.*)}',re.DOTALL)
    pattern_macro = re.compile('#define[\t ]+(\w+)[\t ]+([\dxa-fA-F]+)')
    pattern_anonymous_union = re.compile('(?<!//|ef|/\*)[\t ]+(?:union|struct|enum)[ \t\n]*{.*?}[\w\t ,\[\]0-9\*]*;',re.DOTALL)

    def FindElements(self,headerText):
        ## 找到所有固定值的宏，将宏名称直接替换为值，此处只做替换并未保存
        macros = self.pattern_macro.findall(headerText)
        for name,val in macros:
            headerText = headerText.replace(name,val)
        ## 先检查所有匿名的Union和Struct，将其随机命。   查找格式为     struct{...}...;
        anonymous_union = self.pattern_anonymous_union.findall(headerText)
        for union in anonymous_union:
            tmpitem = {}
            while True:# random error(same val) may cause potentional infinite recycle
                name_prefix = union.strip()[0:5].replace('\n','').replace('\t','').replace(' ','').replace('{','').replace('}','')
                try:
                    tmpitem['name'] = self.pattern_name.findall(union)[0]  # unsupport array naming: xxxx[n]
                except IndexError:
                    tmpitem['name'] = (name_prefix + '_' + str(random.random())[3:7]).upper()
                tmpval = self.typedict.get(tmpitem['name'])
                if tmpval == None:
                    self.typedict[tmpitem['name']] = 'PY_' + tmpitem['name']
                    tmpitem['type'] = name_prefix
                    tmpitem['text'] = self.pattern_text.findall(union)[0]
                    if tmpitem['type'] == 'enum':
                        self.typedict[tmpitem['name']] = 'c_uint'
                        tmpitem['members'] = self.ParseEnum(tmpitem['text'])
                    else:
                        tmpitem['members'] = self.ParseStruct(tmpitem['text'])
                    self.items.insert(0,tmpitem)
                    headerText = headerText.replace(union,tmpitem['name'] + ' ' + tmpitem['name'].lower() + ';')
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
        ## 最后检查所有滞后定义的Struct和Union      struct $STRUCT_NAME $INST_NAME;      # 待解决：滞后定义的typedef struct将使用最先定义的typedef struct的类型名称
        instance_union = self.pattern_ex1.findall(headerText)
        pattern_number = re.compile('\[([A-Z_0-9]*)\]')
        for union in instance_union:
            tmpnamelist = self.pattern_name_ex1.findall(union)
            try:
                typename = self.pattern_type_name.findall(union)[0]
            except IndexError:
                print('[查找元素]解析类型错误, 原文: ',name)
                exit(0)
            for name in tmpnamelist:
                tmpitem = {}
                try:
                    tmpitem['number'] = pattern_number.findall(name)
                    if len(tmpitem['number']) > 0:
                        try:
                            for i in tmpitem['number']:
                                i = int(i)
                        except ValueError:
                            print('[查找元素]不确定的值：',i)
                    else:
                        del tmpitem['number']
                except IndexError:
                    pass
                try:
                    tmpitem['type'] = self.typedict[typename]
                    self.typedict[name] = self.typedict[typename]
                except KeyError:
                    self.unknow_items.add(typename)
                    tmpitem['type'] = typename
                    typename = 'PY_' + typename
                    self.typedict[tmpitem['type']] = typename
                    #item['name'] ???

    # 在初始化函数中，首先查找其所有顶级元素，并保存在item中
    def __init__(self,directory):
        self.cur_dir = directory
        headerText = self.LoadFromDir(directory)
        self.FindElements(headerText)

    # 解析一个Struct或Union元素中的内容，即解析其成员。
    def ParseStruct(self,text): # also works for Union  由于struct和union成员内容的格式类似，所以都使用此函数
        pattern_name = re.compile('([\w]+)[0-9\[\] _A-Z]*;')
        pattern_number = re.compile('\[([0-9A-Z_]*)\]')
        pattern_type = re.compile('[\w\t ]+')
        pattern_comment = re.compile('(?://|/\*)[\t ]*(.+)\*?/?')
        item = []
        members = text.split('\n')
        for member in members:
            if member.isspace() == False and member != '':
                tmpitem = {}
                try:
                    tmpitem['comment'] = pattern_comment.findall(member)[0]
                    member = member.replace(tmpitem['comment'],' ') # [error] when comment has empty body, replace may cause 'replace('',' ')' ==> 'ABC' - ' A B C '
                    tmpitem['comment'] = tmpitem['comment'].replace('\n','\n#').replace('*/','').strip()
                except IndexError:
                    pass
                try:
                    headchar = member.replace('\t','').replace(' ','')[0:2]
                    if headchar == '//' or headchar == '/*':
                        continue
                    tmpitem['name'] = pattern_name.findall(member)[0]
                    member = member.replace(tmpitem['name'],'')
                except IndexError:
                    print('\n以下字符未被解析，如果没有使用可以忽略：\n',member)
                    continue
                try:
                    tmpitem['type'] = pattern_type.findall(member.replace('struct','').replace('union','').replace('enum',''))[0].replace(' ','').replace('\t','')
                    if tmpitem['type'] not in self.typedict:
                        if '*' in tmpitem['type']:  # 是否因为星号导致类型没找到
                            self.typedict[tmpitem['type']] = 'POINTER(' + self.typedict[tmpitem['type'].replace('*','')] + ')'
                        else:                       # 如果不是，则认定为未知类型
                            self.unknow_items.add(tmpitem['type'])
                    if len(tmpitem['type']) == 1 or tmpitem['type'] == 'VENC_DATA_TYPE_UD':
                        pass
                except IndexError:
                    print('\n以下字符未被解析，如果没有使用可以忽略：\n',member)
                    continue
                try:
                    tmpitem['number'] = pattern_number.findall(member)
                    if len(tmpitem['number']) > 0:
                        try:
                            for i in tmpitem['number']:
                                i = int(i)
                        except ValueError:
                            print('[解析成员]不确定的值：',i)
                    else:
                        del tmpitem['number']
                except IndexError:
                    pass
                item.append(tmpitem)
        return item

    # 解析一个Enum中的所有元素
    def ParseEnum(self,text):
        pattern_name = re.compile('(?<!//)[\t ]*([A-Za-z][A-Za-z0-9_]*)=?')
        pattern_val = re.compile('=[\t ]*([0-9]+)[\t ]*,')
        pattern_comment = re.compile('[\\\*/]+(.*)\*?/?')
        __item_no__ = 0
        members = text.replace('\t','').split('\n')
        item = []
        for member in members:
            if member.isspace() == False and member != '':
                tmpitem = {}
                try:
                    tmpitem['comment'] = pattern_comment.findall(member)[0]
                    member = member.replace(tmpitem['comment'],'').replace(' ','')
                    tmpitem['comment'] = tmpitem['comment'].replace('\n','\n#').replace('*/','').strip()
                except IndexError:
                    pass
                tmpitem['name'] = pattern_name.findall(member)[0]
                try:
                    tmpitem['val'] = int(pattern_val.findall(member)[0])
                    __item_no__ = tmpitem['val']
                except IndexError:
                    tmpitem['val'] = __item_no__
                item.append(tmpitem)
                __item_no__ += 1
        return item
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
            pattern_include_item = re.compile('(?:struct|union|enum)[\t ]+' + unknow_item + '[\t \n]*{.*?(?<!\t| )}[\w\t \n]*;',re.DOTALL)
            pattern_include_item1 = re.compile('(?:struct|union|enum)[\t ]*\w*[\t \n]*{.*?}[\t ]*'+ unknow_item +'[\t \n]*;',re.DOTALL)
            include_items = pattern_include_item.findall(includeText)
            include_items += pattern_include_item1.findall(includeText)
            if len(include_items) == 1:
                self.FindElements(include_items[0])
            elif len(include_items) == 0: 
                pass
            else:
                print(unknow_item,'redefined:')
                for i in include_items:
                    print(i)
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
                    memberliststr = memberliststr + '(\'' + member['name'] + '\',' + member['name'] +'), '
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
                        print('[输出文档]未知类型：',member['type'],'，暂用名称：',memtype)
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
