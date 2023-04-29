import json

from flask import Flask, request, jsonify
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from IngError import IngError
from OpenAI import OpenAI
from WxMini import WxMini
import mysql.connector
import time
import datetime

app = Flask(__name__)
mydb = mysql.connector.connect(
    host="localhost",
    user="ingredient",
    password="FaTqs-_7",
    database="ingredient"
)

log_dir = os.path.join(app.root_path, 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

log_file = os.path.join(log_dir, 'app.log')
handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=7, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(lineno)d: %(message)s'))
handler.setLevel(logging.DEBUG)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

UPLOAD_FOLDER = '/var/www/newtype.top/images/'
wx = WxMini(app, mydb)
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

        ocr_result = wx.get_ocr(img_url)
        os.remove(file_path)

        ocr = ocr_result[2]
        if (ocr_result[0] != 0) or (not ocr) or (len(ocr) <= 0):
            app.logger.error(
                '/upload: 500, WxMini.get_ocr errcode: {}, errmsg: {}'.format(ocr_result[0], ocr_result[1]))
            return jsonify({'errcode': ocr_result[0], 'errmsg': ocr_result[1]}), 500

        gpt_result = gpt.ask(ocr)
        conclusion = gpt_result[2]
        if (gpt_result[0] != 0) or (not conclusion) or (len(conclusion) <= 0):
            app.logger.error('/upload: 500, OpenAI.ask errcode: {}, errmsg: {}'.format(gpt_result[0], gpt_result[1]))
            return jsonify({'errcode': gpt_result[0], 'errmsg': gpt_result[1]}), 500

        app.logger.info('/upload: 200, conclusion: {}'.format(conclusion))
        cursor = mydb.cursor()
        query = "update user set usage_count=usage_count+1 where uid=%s"
        app.logger.info(query)
        cursor.execute(query, (uid,))
        mydb.commit()
        cursor.close()
        cursor = mydb.cursor()
        query = "insert into usage (uid, img_path, ocr, openai_answer, timestamp) values (%s, %s, %s, %s)"
        app.logger.info(query)
        now_timestamp = int(time.time())
        now_timestamp_str = datetime.datetime.fromtimestamp(now_timestamp).strftime(
            '%Y-%m-%d %H:%M:%S')
        cursor.execute(query, (uid, file_path, ocr, conclusion, now_timestamp_str))
        mydb.commit()
        cursor.close()
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

        cursor = mydb.cursor()
        query = "select usage_count, usage_limit from user where uid=%s"
        app.logger.info(query)
        cursor.execute(query, (uid,))
        results = cursor.fetchall()
        app.logger.info('select result: {}'.format(results))
        cursor.close()
        if len(results) > 0:
            usage, limit = results[0]
            if usage < limit:
                app.logger.info('/api/usage: 200, uid: {}'.format(uid))
                return jsonify({'errcode': 0, 'errmsg': 'success', 'usage': 1})
            else:
                app.logger.error('/api/usage: 500, run out uid: {}'.format(uid))
                return jsonify({'errcode': IngError.UsageRunOut.value, 'errmsg': 'run out'}), 500
        else:
            app.logger.error('/api/usage: 500, no uid: {}'.format(uid))
            return jsonify({'errcode': IngError.UsageNoUsageFound.value, 'errmsg': 'no uid: {}'.format(uid)}), 500
    except Exception as e:
        app.logger.error('/api/usage: 500, errors not caught: {}'.format(e))
        return jsonify({'errcode': IngError.UsageOtherError.value, 'errmsg': 'errors not caught'}), 500


if __name__ == '__main__':
    # app.run('127.0.0.1', '8888', debug=True)
    app.run(debug=True)
