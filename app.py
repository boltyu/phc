from os import mkdir,remove,listdir,sep
from flask import Flask
from flask import render_template
from flask import request
from flask import send_file
from pyHeader2Ctypes import CElements
import traceback

app = Flask(__name__, static_folder='./webfiles', template_folder='./webfiles')
app.config['UPLOAD_FOLDER'] = 'tmp'
app.debug = True

    

@app.route('/',methods=['get'])
def route_home():
    return render_template('app.html',name='file exchange')

@app.route('/headerfile',methods=['post'])
def route_headerfile():
    # if request.method == 'post':
    for file in listdir('tmp'):
        try:
            remove('tmp' + sep + file)
        except PermissionError:
            pass
    file_count = 0
    while True:
        try:
            file = request.files['file'+str(file_count)]
            if file:
                file.save('tmp'+sep+file.filename)
            file_count += 1
        except:
            break
    print('recv total ', file_count, 'files')
    try:
        celements = CElements('tmp')
        result = celements.DumpToStr()
        return result
    except:
        m
        with open('err.txt','w') as f:
            traceback.print_exc(file=f)
        return send_file('err.txt')