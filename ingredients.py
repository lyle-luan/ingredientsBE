import json

from flask import Flask, request, jsonify
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from IngError import IngError
from OpenAI import OpenAI
from WxMini import WxMini
from MyDB import MyDB
import time
import datetime

app = Flask(__name__)

log_dir = os.path.join(app.root_path, 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

log_file = os.path.join(log_dir, 'app.log')
handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=7, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(lineno)d %(message)s'))
handler.setLevel(logging.DEBUG)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

UPLOAD_FOLDER = '/var/www/newtype.top/images/'
mydb = MyDB(app.logger)
wx = WxMini(app.logger, mydb)
gpt = OpenAI(app)


@app.route('/api/login', methods=['POST'])
def api_login():
    app.logger.info('/api/login...')
    try:
        data = request.get_json()
        code = data.get('code')
        uid = data.get('key')
        app.logger.info('/api/login: code: {}, key: {}'.format(code, uid))
        if code:
            errcode, errmsg, result = wx.login(code, uid)
            if (errcode != 0) or (not result):
                app.logger.error(
                    '/api/login: 500, WxMini.login errcode: {}, errmsg: {}'.format(errcode, errmsg))
                return jsonify({'errcode': errcode, 'errmsg': errmsg}), 500

            app.logger.info('/api/login: 200, uid: {}'.format(result))
            return jsonify({'errcode': 0, 'errmsg': 'success', 'uid': result})

        app.logger.error('/api/login: code: {}, key: {}'.format(code, uid))
        return jsonify({'errcode': IngError.WXLoginRequestParameterError.value,
                        'errmsg': '/api/login: code: {}, key: {}'.format(code, uid)}), 500
    except Exception as e:
        app.logger.error('/api/login: 500, errors not caught: {}'.format(e))
        return jsonify({'errcode': IngError.LoginOtherError.value, 'errmsg': 'errors not caught'}), 500


@app.route('/upload', methods=['POST'])
def upload():
    # todo: 图片指纹库
    # todo: 接入告警
    # todo: 历史记录，图片不删除，并制作 thumb; 历史记录暂时不做
    try:
        app.logger.info('/upload...')
        data = request.form.get('data')
        json_ata = json.loads(data)
        uid = json_ata.get('uid')
        app.logger.info('/upload: uid: {}'.format(uid))
        if not uid:
            app.logger.error('/upload: uid: {}'.format(uid))
            return jsonify({'errcode': IngError.UploadNoUid.value,
                            'errmsg': '/upload: uid: {}'.format(uid)}), 500

        if 'img' not in request.files:
            app.logger.error('/upload: 400, No img uploaded')
            return jsonify({'errcode': IngError.UploadNoImg.value, 'errmsg': 'No img uploaded'}), 400

        file = request.files['img']

        if file.filename == '':
            app.logger.error('/upload: 400, No img selected')
            return jsonify({'errcode': IngError.UploadImgNoName.value, 'errmsg': 'No img selected'}), 400

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        app.logger.info('/upload save file success.')
        img_url = 'https://newtype.top/images/' + file.filename

        ocr_code, ocr_msg, ocr = wx.get_ocr(img_url)
        # os.remove(file_path)

        if (ocr_code != 0) or (not ocr) or (len(ocr) <= 0):
            app.logger.error(
                '/upload: 500, WxMini.get_ocr err: {}, {}'.format(ocr_code, ocr_msg))
            return jsonify({'errcode': ocr_code, 'errmsg': ocr_msg}), 500

        gpt_code, gpt_msg, conclusion = gpt.ask(ocr)
        if (gpt_code != 0) or (not conclusion) or (len(conclusion) <= 0):
            app.logger.error('/upload: 500, OpenAI.ask errcode: {}, errmsg: {}'.format(gpt_code, gpt_msg))
            return jsonify({'errcode': gpt_code, 'errmsg': gpt_msg}), 500

        app.logger.info('/upload: 200, conclusion: {}'.format(conclusion))
        mydb.updateUsage(uid, file_path, ocr, conclusion)
        return jsonify({'errcode': 0, 'errmsg': 'success', 'ocr': conclusion})
    except Exception as e:
        app.logger.error('/upload: 500, errors not caught: {}'.format(e))
        return jsonify({'errcode': IngError.UploadOtherError.value, 'errmsg': 'errors not caught'}), 500


@app.route('/api/usage', methods=['POST'])
def api_usage():
    app.logger.info('/api/usage...')
    try:
        data = request.get_json()
        uid = data.get('uid')
        app.logger.info('/api/usage: uid: {}'.format(uid))
        if not uid:
            app.logger.error('/api/usage: uid: {}'.format(uid))
            return jsonify({'errcode': IngError.UsageRequestParamError.value,
                            'errmsg': '/api/usage: uid: {}'.format(uid)}), 500

        usage, limit = mydb.usage_info_of_uid(uid)
        if usage < 0 or limit < 0:
            app.logger.error('/api/usage: 500, no uid: {}'.format(uid))
            return jsonify({'errcode': IngError.UsageNoUsageFound.value, 'errmsg': 'no uid: {}'.format(uid)}), 500
        else:
            if usage < limit:
                app.logger.info('/api/usage: 200, uid: {}'.format(uid))
                return jsonify({'errcode': 0, 'errmsg': 'success', 'usage': 1})
            else:
                app.logger.error('/api/usage: 500, run out uid: {}'.format(uid))
                return jsonify({'errcode': IngError.UsageRunOut.value, 'errmsg': 'run out'}), 500

    except Exception as e:
        app.logger.error('/api/usage: 500, errors not caught: {}'.format(e))
        return jsonify({'errcode': IngError.UsageOtherError.value, 'errmsg': 'errors not caught'}), 500


# @app.teardown_appcontext
# def close(error):
#     mydb.close()


if __name__ == '__main__':
    # app.run('127.0.0.1', '8888', debug=True)
    app.run(debug=True)
