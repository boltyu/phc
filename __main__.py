
import re
import os
import json
import random

indentStr = '    ' # 缩进字符默认使用四个空格

class CElements:
    typedict = {   # 类型转换字典
        'VIM_U32':'c_uint', 'VIM_BOOL':'c_uint', 'VIM_U8':'c_uint', 'VIM_CHAR':'c_uint', 'VIM_S32':'c_uint', 'VIM_FR32':'c_uint', 'VIM_VOID*':'c_void_p',
        'VIM_DOUBLE':'c_double', 'VIM_FLOAT':'c_float', 'VIM_U64':'c_longlong','VIM_U16':'c_uint',
        'unsigned':'c_uint',
        'VI_CHN':'c_uint'
    }
    macrodict = {  # 宏定义转换字典

    }
    items = []     # items包含了从文件中识别到的所有struct union enum，类型为dict/json
    # 查找顶级元素（没有被嵌套的struct union enum）的表达式
    pattern = re.compile('(?<!//|/\*)[\t ]*((?:typedef)?[\t| ]*(?:struct|union|enum)[\t \n]*[A-Za-z_0-9]*[\t \n]*{.*?}[A-Z0-9_\[\] ,*]*;)',re.DOTALL)
    pattern_ex1 = re.compile('(?<!//|/\*)[\t ]*(?:typedef)?[\t ]*(?:struct|union|enum)[\t ]+[a-zA-Z0-9_]+[\t ]+[a-zA-Z0-9_*\[\]]+;')
    pattern_name = re.compile('}[\t ]*?([A-Z0-9_]+[\t ]*\*?)[\t ]*[;,]',re.DOTALL) # XXX[N] XXX* 没有同时兼容
    pattern_name_ex1 = re.compile('([A-Z0-9_a-z\[\]]+)[\t ]*[;,]')
    pattern_type = re.compile('(struct|union|enum)[A-Za-z0-9_ \t\n]*{')
    pattern_type_name = re.compile('(?:typedef)?[\t ]*(?:struct|union|enum)[\t ]+([a-zA-Z0-9_]+)')
    pattern_text = re.compile('{(.*)}',re.DOTALL)
    # 在class创建后，首先查找其所有顶级元素，元素所包含的内容暂时保存在元素的['text']键中
    def __init__(self,text):
        ## 先检查所有匿名的Union和Struct，将其随机命        struct{   };
        pattern_anonymous_union = re.compile('(?<!//|ef|/\*)[\t ]+((?:union|struct|enum)[ \t\n]*{.*?}[\t ]*;)',re.DOTALL)
        anonymous_union = pattern_anonymous_union.findall(text)
        for union in anonymous_union:
            tmpitem = {}
            while True:# random error(same val) may cause potentional infinite recycle
                name_prefix = union.strip()[0:5].replace('\n','').replace('\t','').replace(' ','')
                tmpitem['name'] = (name_prefix + '_' + str(random.random())[3:7]).upper()
                tmpval = self.typedict.get(tmpitem['name'])
                if tmpval == None:
                    self.typedict[tmpitem['name']] = 'PY_' + tmpitem['name']
                    tmpitem['type'] = name_prefix
                    tmpitem['text'] = self.pattern_text.findall(union)[0]
                    tmpitem['members'] = self.ParseStruct(tmpitem['text'])
                    self.items.append(tmpitem)
                    text = text.replace(union,tmpitem['name'] + ' ' + tmpitem['name'].lower() + ';')
                    break
        ## 其次检查所有新命名的Struct和Union       typedef struct $STRUCT_NAME {} $INST_NAME;           
        elementList = self.pattern.findall(text)
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
            except IndexError:
                pass
            try:
                item['name'] = self.pattern_name.findall(element)[0].replace(' ','')
                self.typedict[item['name']] = 'PY_' + item['name']
            except IndexError:
                pass
            self.items.append(item)  

        ## 最后检查所有滞后定义的Struct和Union      struct $STRUCT_NAME $INST_NAME;      # 待解决：滞后定义的typedef struct将使用最先定义的typedef struct的类型名称
        instance_union = self.pattern_ex1.findall(text)
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
                    tmpitem['type'] = typename
                    typename = 'PY_' + typename
                    print('未知类型：',tmpitem['type'],'，暂用名称：',typename)
                    self.typedict[tmpitem['type']] = typename
                    #item['name'] ???

    # 解析一个Struct或Union元素中的内容，即解析其成员。
    def ParseStruct(self,text): # also works for Union  由于struct和union成员内容的格式类似，所以都使用此函数
        pattern_name = re.compile('([A-Za-z0-9_\*]+)[0-9\[\] _A-Z]*;')
        pattern_number = re.compile('\[([0-9A-Z_]*)\]')
        pattern_type = re.compile('[a-zA-Z0-9_]+[\t ]*\*?')
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
                except IndexError:
                    print('\n以下字符未被解析，如果没有使用可以忽略：\n',member)
                    continue
                try:
                    tmpitem['type'] = pattern_type.findall(member.replace('struct','').replace('union','').replace('enum',''))[0].replace(' ','').replace('\t','')
                    if tmpitem['type'] not in self.typedict:
                        if '*' in tmpitem['type']:
                            self.typedict[tmpitem['type']] = 'POIONTER(' + self.typedict[tmpitem['type'].replace('*','')] + ')'
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
        pass

    # 将items内容输出为.py文件
    def DumpString(self):
        result = 'from ctypes import *\n\n'
        for item in self.items:
            if item['type'] == 'enum':
                result = result + 'class ' + self.typedict[item['name']] + '(c_uint):\n'
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
                result = result + 'class ' + self.typedict[item['name']] + '(Structure):\n'
                anonystr = indentStr + '_anonymous_=('
                memberstr = indentStr + '_fields_=[\n'
                memberno = 0
                anonyno = 0
                for member in item['members']:
                    memberno += 1
                    memberstr = memberstr + indentStr + '(\'' + member['name'] + '\','
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
                    memberstr = memberstr + '),'
                    if memberno == len(item['members']):
                        memberstr = memberstr + ']'
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
        return result

if __name__ == '__main__':
    headerText = ''  # 从.h文件中读取的全部内容
    pathPrefix = '.' + os.sep + 'tests'   # 查找目录
    # fileName = 'vim_comm_venc.h'          # 文件名称
    fileList = []
    fileCount = 0
    for fileName in os.listdir(pathPrefix):
        if fileName[-2:] == '.h':
            fileList.insert(fileCount,fileName)
            fileCount += 1
    for fileName in fileList:
        print('['+str(fileList.index(fileName))+']',fileName)
    i = int(input('选择一个文件: 0~'+str(len(fileList)-1)+'  '))
    # i = 1
    fileName = fileList[i]
    try:
        with open(pathPrefix+os.sep+fileName,'r',encoding='utf-8') as f:
            headerText = f.read(1024*1000*10)
    except UnicodeDecodeError as e:
        with open(pathPrefix+os.sep+fileName,'r',encoding='gbk') as f:
            headerText = f.read(1024*1000*10)
    except Exception as e:
        print(e)
    celements = CElements(headerText)
    celements.ParseMembers()

    with open('out.py','w',encoding='utf-8') as outfile:
        outfile.write(celements.DumpString())

    # 取消注释以输出typedict和item的json内容
    # with open('debug_typedict.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.typedict,jsonfile)
    # with open('debug_items.json','w',encoding='utf-8') as jsonfile:
    #     json.dump(celements.items,jsonfile)