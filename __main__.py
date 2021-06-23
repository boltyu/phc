
import re
import os
import json
import random

indentStr = '    ' # 缩进字符默认使用四个空格

class CElements:
    typedict = {   # 类型转换字典
        'VIM_U32':'c_uint', 'VIM_BOOL':'c_uint', 'VIM_U8':'c_uint', 'VIM_CHAR':'c_uint', 'VIM_S32':'c_uint', 'VIM_FR32':'c_uint', 'VIM_VOID*':'c_void_p',
        'VIM_DOUBLE':'c_double', 'VIM_FLOAT':'c_float', 'VIM_U64':'c_longlong',
        'VIM_U16':'c_uint',
        'VI_CHN':'c_uint'
    }
    items = []     # items包含了从文件中识别到的所有struct union enum，类型为dict/json
    # 查找顶级元素（没有被嵌套的struct union enum）的表达式
    pattern = re.compile('(?<!//|/\*) *typedef (?:struct|union|enum).*?{.*?}[A-Z0-9_ ,*]+;',re.DOTALL)
    pattern_ex1 = re.compile('(?<!//|/\*) *typedef *(?:struct|union|enum) *[a-zA-Z0-9_]+ *[A-Z0-9_*]+;',re.DOTALL)
    pattern_name = re.compile('} *?([A-Z0-9_]+ *\*?) *[;,]',re.DOTALL)
    pattern_name_ex1 = re.compile('[A-Z][A-Z0-9_]+ *?([A-Z0-9_]+) *[;,]',re.DOTALL)
    pattern_type = re.compile('(?:typedef| |\t)+(struct|union|enum)')
    pattern_text = re.compile('{(.*)}',re.DOTALL)
    # 在class创建后，首先查找其所有顶级元素，元素所包含的内容暂时保存在元素的['text']键中
    def __init__(self,text):
        elementList = self.pattern.findall(text)
        elementList += self.pattern_ex1.findall(text)
        for element in elementList:
            item = {}
            try:
                item['name'] = self.pattern_name.findall(element)[0].replace(' ','')
            except IndexError:
                item['name'] = self.pattern_name_ex1.findall(element)[0].replace(' ','')
            self.typedict[item['name']] = 'PY_' + item['name'] 
            item['type'] = self.pattern_type.findall(element)[0]
            try:
                item['text'] = self.pattern_text.findall(element)[0]
            except IndexError:
                continue
            self.items.append(item)
    # 将items内容输出为.py文件
    def DumpString(self):
        result = ''
        for item in self.items:
            if item['type'] == 'enum':
                result = result + 'class ' + self.typedict[item['name']] + '(Structure):\n'
                for member in item['members']:
                    result = result + indentStr + member['name'] + ' = ' + str(member['val']) 
                    comment =  member.get('comment')
                    if comment is not None:
                        result = result + '    # ' + comment
                    result += '\n'
                result += '\n'
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
                        print('unkown type: '+ member['type'] + ', use : ' + memtype)
                    number = member.get('number')
                    if number is not None:
                        for n in reversed(number):
                            memtype = '(' + memtype + '*' + str(n) + ')'
                    memberstr += memtype
                    memberstr = memberstr + ')'
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
    # 解析一个Struct元素中的内容，即解析其成员。
    def ParseStruct(self,text): # also works for Union  由于struct和union成员内容的格式类似，所以都使用此函数
        pattern_name = re.compile('([a-zA-Z_][A-Za-z0-9_\*]+)[0-9\[\] ]*;')
        pattern_number = re.compile('\[([0-9]*)\]')
        pattern_type = re.compile('[A-Z][A-Z0-9_]+[\t ]*\*?')
        pattern_comment = re.compile('(?://|/\*)(.*)\*?/?')
        item = []
        ## 检查是否包含匿名的Union，并将其解析
        pattern_anonymous_union = re.compile('(?<!// )(union.*?{.*?} *;)',re.DOTALL)
        anonymous_union = pattern_anonymous_union.findall(text)
        for union in anonymous_union:
            tmpitem = {}
            while True:# potentional infinite recycle
                tmpitem['name'] = 'UNION' + str(str(random.random()).replace('0.',''))
                tmpval = self.typedict.get(tmpitem['name'])
                if tmpval == None:
                    self.typedict[tmpitem['name']] = 'PY_' + tmpitem['name']
                    tmpitem['type'] = 'union'
                    tmpitem['text'] = self.pattern_text.findall(union)[0]
                    tmpitem['members'] = self.ParseUnion(tmpitem['text'])
                    self.items.append(tmpitem)
                    text = text.replace(union,tmpitem['name'] + ' ' + tmpitem['name'].replace('UNION','union_') + ';')
                    break
        ## 【检查是否包含匿名的Union，并将其解析】 结束
        members = text.split('\n')
        ## 继续解析其它成员
        for member in members:
            if member.isspace() == False and member != '':
                tmpitem = {}
                try:
                    tmpitem['comment'] = pattern_comment.findall(member)[0]
                    member = member.replace(tmpitem['comment'],'')
                    tmpitem['comment'] = tmpitem['comment'].replace('\n','\n#').replace('*/','').strip()
                except IndexError:
                    pass
                try:
                    headchar = member.replace('\t','').replace(' ','')[0:2]
                    if headchar == '//' or headchar == '/*':
                        continue
                    tmpitem['name'] = pattern_name.findall(member)[0]
                except IndexError:
                    continue
                try:
                    tmpitem['type'] = pattern_type.findall(member)[0].replace(' ','').replace('\t','')
                    if tmpitem['type'] not in self.typedict:
                        if '*' in tmpitem['type']:
                            self.typedict[tmpitem['type']] = 'POIONTER(' + self.typedict[tmpitem['type'].replace('*','')] + ')'
                    if len(tmpitem['type']) == 1 or tmpitem['type'] == 'VENC_DATA_TYPE_UD':
                        pass
                except IndexError:
                    continue
                try:
                    tmpitem['number'] = pattern_number.findall(member)
                    if len(tmpitem['number']) > 0:
                        for i in tmpitem['number']:
                            i = int(i)
                    else:
                        del tmpitem['number']
                except IndexError:
                    pass
                item.append(tmpitem)
        return item
    # Union暂同Struct
    def ParseUnion(self,text):
        pass
    # 解析一个Enum中的所有元素
    def ParseEnum(self,text):
        pattern_name = re.compile('(?<!//) *([A-Za-z][A-Za-z0-9_]*)=?')
        pattern_val = re.compile('= *([0-9]+) *,')
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
fileName = fileList[i]
try:
    with open(pathPrefix+os.sep+fileName,'r',encoding='utf-8') as f:
        headerText = f.read(1024*1000*10)
except UnicodeDecodeError as e:
    with open(pathPrefix+os.sep+fileName,'r',encoding='GBK') as f:
        headerText = f.read(1024*1000*10)

for i in re.findall('//.*',headerText):
    headerText = headerText.replace(i,'')
for i in re.findall('/\*.*?\*/',headerText,re.DOTALL):
    headerText = headerText.replace(i,'')
with open('bk'+fileName,'w',encoding='utf-8') as f:
    f.write(headerText.replace('\t',' '))
exit(0)

celements = CElements(headerText)
celements.ParseMembers()

with open('out.py','w',encoding='utf-8') as outfile:
    outfile.write(celements.DumpString())

# 取消注释以输出typedict和item中的内容
# with open('debug_typedict.json','w',encoding='utf-8') as jsonfile:
#     json.dump(celements.typedict,jsonfile)
# with open('debug_items.json','w',encoding='utf-8') as jsonfile:
#     json.dump(celements.items,jsonfile)