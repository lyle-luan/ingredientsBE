from flask import Flask, request, jsonify
import requests
from requests import exceptions
import os
import openai
import time


class OpenAI:
    api_key = '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'
    prompt = '提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议: {}'

    def __init__(self):
        openai.api_key = OpenAI.api_key

    def ask(self, ingredients: str) -> str:
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=OpenAI.prompt.format(ingredients),
            max_tokens=4096,
            n=1,
            stop=None,
            temperature=0.3).choices
        result = ''
        for item in response:
            result += item.text
        return result


class WxMini:
    app_id = 'wx4226b6f08dfba65a'
    app_secret = '67d2ef55944c47c92010300014b711f4'
    token_url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=' + \
                app_id + '&secret=' + app_secret
    ocr_url = 'https://api.weixin.qq.com/cv/ocr/comm?access_token={}&img_url={}'
    max_http_retry = 3
    max_ocr_retry = 2

    def __init__(self):
        self.access_token = ''
        self.access_token_expires_timestamp_s = time.time()
        self.count_http_retry = 0

    def __get_token(self):
        now = time.time()
        if now < self.access_token_expires_timestamp_s:
            return 0, '', self.access_token

        try:
            response = requests.get(self.token_url, timeout=1)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.count_http_retry += 1
            if self.count_http_retry <= WxMini.max_http_retry:
                return self.__get_token()
            else:
                self.count_http_retry = 0
                return 1, str(e.message), ''
        except exceptions.HTTPError as e:
            self.count_http_retry = 0
            return 2, str(e.message), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            self.access_token = result['access_token']
            self.access_token_expires_timestamp_s = now + result['expires_in']
            return 0, '', self.access_token

    def get_ocr(self, img_url):
        self.__get_token()
        wx_url = WxMini.ocr_url.format(self.access_token, img_url)
        try:
            response = requests.post(wx_url, timeout=1)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.count_http_retry += 1
            if self.count_http_retry <= WxMini.max_ocr_retry:
                return self.get_ocr(img_url)
            else:
                self.count_http_retry = 0
                return 1, str(e.message), ''
        except exceptions.HTTPError as e:
            self.count_http_retry = 0
            return 2, str(e.message), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            if result['errcode'] != 0:
                return 3, 'wx errcode: ' + result['errcode'] + ', wx errmsg: ' + result['errmsg'], ''

            ocr_result = ''
            items = result['items']
            for item in items:
                ocr_result += item['text'] + ' '

            return 0, '', ocr_result


UPLOAD_FOLDER = '/var/www/newtype.top/images/'
app = Flask(__name__)
wx = WxMini()
gpt = OpenAI()


@app.route('/upload', methods=['POST'])
def upload():
    # todo: 图片指纹库
    if 'img' not in request.files:
        return jsonify({'errcode': 1, 'errmsg': 'No img uploaded'})

    file = request.files['img']

    if file.filename == '':
        return jsonify({'errcode': 2, 'errmsg': 'No img selected'})

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    os.file.save(file_path)
    img_url = 'https://newtype.top/images/' + file.filename

    ocr_result = wx.get_ocr(img_url)
    os.remove(file_path)

    ocr = ocr_result[2]
    if ocr_result[0] != 0 or not ocr or ocr.isspace():
        return jsonify({'errcode': ocr_result[0], 'errmsg': ocr_result[1], 'data': jsonify({'ocr': ocr_result[2]})})

    result = gpt.ask(ocr)
    return jsonify({'errcode': 0, 'errmsg': '', 'data': jsonify({'ocr': result})})


if __name__ == '__main__':
    # 启动 HTTPS 服务器
    # app.run(ssl_context='adhoc', host='0.0.0.0', port=443)
    # app.run(host='0.0.0.0', port=5001)
    app.run()
