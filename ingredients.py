from flask import Flask, request, jsonify
from requests import requests, exceptions
import os
import openai
import time

app = Flask(__name__)
UPLOAD_FOLDER = '/var/www/newtype.top/images/'
wx_access_token = ''
wx_access_token_expires_at = ''

def get_token():
    appId = 'wx4226b6f08dfba65a'
    appSerect = '67d2ef55944c47c92010300014b711f4'
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid='+appId+'&secret='+appSerect

    response = requests.get(url)
    return response.json()['access_token']

@app.route('/upload', methods=['POST'])
def upload():
    if 'img' not in request.files:
        return jsonify({'error': 'No img uploaded'})

    file = request.files['img']

    if file.filename == '':
        return jsonify({'error': 'No img selected'})

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    access_token = get_token()
    img_url = 'https://newtype.top/images/' + file.filename
    wx_url = 'https://api.weixin.qq.com/cv/ocr/comm?access_token='+access_token+'&img_url='+img_url
    response = requests.post(wx_url)
    result = response.json()
    if result['errcode'] != 0:
        return jsonify({'result': 'upload error'})

    ocr_result = ''
    items = result['items']
    for item in items:
        ocr_result += item['text'] + ' '

    return ask_chat(ocr_result)


def ask_chat(ingredients):
    OPENAI_API_KEY = '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'
    #return """提取上面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议\n
    prompt =  '提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议: {}'.format(ingredients)
    openai.api_key = OPENAI_API_KEY
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=3000,
        n=1,
        stop=None,
        temperature=0.3).choices
    response_str = ''
    for item in response:
        response_str += item.text
    return response_str


@app.route('/doocr', methods=['POST'])
def do_ocr():
    data = request.get_json()
    img_base64 = data.get('imgbase64')
    #img_base64 = request.args.get('imgbase64', '')

    mini_program_ocr_url = 'https://api.weixin.qq.com/cv/ocr/general?access_token=' + '67d2ef55944c47c92010300014b711f4'
    data = {'img_base64': img_base64}

    response = requests.post(mini_program_ocr_url, json=data)

    print(response.json())

    #return response.json()
    return jsonify({'result': 'OCR completed' + img_base64})

if __name__ == '__main__':
    # 启动 HTTPS 服务器
    #app.run(ssl_context='adhoc', host='0.0.0.0', port=443)
    #app.run(host='0.0.0.0', port=5001)
    app.run()

