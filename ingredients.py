from flask import Flask, request, jsonify
import requests
from requests import exceptions
import os
import openai
import time


class OpenAI:
    api_key = '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'
    prompt = '提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议，少于 100 个字: {}'
    max_retry_count = 2
    retry_interval_s = 0.3

    def __init__(self):
        openai.api_key = OpenAI.api_key
        self.count_retry = 0

    def ask(self, ingredients: str):
        try:
            response = openai.Completion.create(
                engine='text-davinci-003',
                prompt=OpenAI.prompt.format(ingredients),
                max_tokens=3000,
                n=1,
                stop=None,
                temperature=0.3).choices
        except openai.error.APIError as e:
            return 1, 'openai.error.APIError', ''
            pass
        except openai.error.Timeout as e:
            # todo: retry request after a brief wait
            return 2, 'openai.error.Timeout', ''
        except openai.error.RateLimitError as e:
            return 3, 'openai.error.RateLimitError', ''
        except openai.error.APIConnectionError as e:
            # todo: retry request after a brief wait
            return 4, 'openai.error.APIConnectionError', ''
        except openai.error.InvalidRequestError as e:
            # todo: log e.message
            return 5, 'openai.error.InvalidRequestError', ''
        except openai.error.AuthenticationError as e:
            return 6, 'openai.error.AuthenticationError', ''
        except openai.error.ServiceUnavailableError as e:
            # todo: retry request after a brief wait
            return 7, 'openai.error.ServiceUnavailableError', ''
        else:
            result = ''
            for item in response:
                result += item.text
            return 0, 'success', result


class WxMini:
    app_id = 'wx4226b6f08dfba65a'
    app_secret = '67d2ef55944c47c92010300014b711f4'
    token_url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=' + \
                app_id + '&secret=' + app_secret
    ocr_url = 'https://api.weixin.qq.com/cv/ocr/comm?access_token={}&img_url={}'
    max_http_retry = 3            # todo: retry request after a brief wait
    max_ocr_retry = 2            # todo: retry request after a brief wait
    retry_interval_s = 0.3

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
                return 1, str(e), ''
        except exceptions.HTTPError as e:
            self.count_http_retry = 0
            return 2, str(e), ''
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
            response = requests.post(wx_url)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.count_http_retry += 1
            if self.count_http_retry <= WxMini.max_ocr_retry:
                return self.get_ocr(img_url)
            else:
                self.count_http_retry = 0
                return 1, str(e), ''
        except exceptions.HTTPError as e:
            self.count_http_retry = 0
            return 2, str(e), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            if result['errcode'] != 0:
                return 3, 'wx errcode: {}, wx errmsg: {}'.format(result['errcode'], result['errmsg']), ''

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
    # todo: 接入日志
    try:
        if 'img' not in request.files:
            return jsonify({'errcode': 1, 'errmsg': 'No img uploaded'}), 400

        file = request.files['img']

        if file.filename == '':
            return jsonify({'errcode': 2, 'errmsg': 'No img selected'}), 400

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        img_url = 'https://newtype.top/images/' + file.filename

        ocr_result = wx.get_ocr(img_url)
        os.remove(file_path)

        ocr = ocr_result[2]
        if (ocr_result[0] != 0) or (not ocr) or (len(ocr) <= 0):
            return jsonify({'errcode': ocr_result[0], 'errmsg': ocr_result[1]}), 500

        gpt_result = gpt.ask(ocr)
        conclusion = gpt_result[2]
        if (gpt_result[0] != 0) or (not conclusion) or (len(conclusion) <= 0):
            return jsonify({'errcode': gpt_result[0], 'errmsg': gpt_result[1]}), 500

        return jsonify({'errcode': 0, 'errmsg': 'success', 'ocr': conclusion})
    except exceptions as e:
        return jsonify({'errcode': 1, 'errmsg': 'errors not caught'}), 500


if __name__ == '__main__':
    app.run()
