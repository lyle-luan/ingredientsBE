from flask import Flask, request, jsonify
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from IngError import IngError
from OpenAI import OpenAI
from WxMini import WxMini

app = Flask(__name__)

log_dir = os.path.join(app.root_path, 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

log_file = os.path.join(log_dir, 'app.log')
handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=7, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

UPLOAD_FOLDER = '/var/www/newtype.top/images/'
wx = WxMini(app)
gpt = OpenAI(app)


@app.route('/api/login', methods=['POST'])
def api_login():
    app.logger.info('/api/login...')
    try:
        data = request.get_json()
        code = data.get('code')
        ing_key = data.get('key')
        app.logger.info('/api/login: code: {}, key: {}'.format(code, ing_key))
        if code and ing_key:
            errcode, errmsg, result = wx.login(code, ing_key)
            if (errcode != 0) or (not result) or (len(result) <= 0):
                app.logger.error(
                    '/api/login: 500, WxMini.login errcode: {}, errmsg: {}'.format(errcode, errmsg))
                return jsonify({'errcode': errcode, 'errmsg': errmsg}), 500

            app.logger.info('/api/login: 200, ing_key: {}'.format(result))
            return jsonify({'errcode': 0, 'errmsg': 'success', 'ing_key': result})

        app.logger.error('/api/login: code: {}, key: {}'.format(code, ing_key))
        return jsonify({'errcode': IngError.WXLoginRequestParameterError.value,
                        'errmsg': '/api/login: code: {}, key: {}'.format(code, ing_key)}), 500
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
        return jsonify({'errcode': 0, 'errmsg': 'success', 'ocr': conclusion})
    except Exception as e:
        app.logger.error('/upload: 500, errors not caught: {}'.format(e))
        return jsonify({'errcode': IngError.UploadOtherError.value, 'errmsg': 'errors not caught'}), 500


if __name__ == '__main__':
    app.run()
