import requests
from requests import exceptions
import time
import asyncio
from IngError import IngError


async def delayed_response(interval):
    await asyncio.sleep(interval)


class WxMini:
    app_id = 'wx4226b6f08dfba65a'
    app_secret = '67d2ef55944c47c92010300014b711f4'
    token_url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=' + \
                app_id + '&secret=' + app_secret
    ocr_url = 'https://api.weixin.qq.com/cv/ocr/comm?access_token={}&img_url={}'
    login_url = 'https://api.weixin.qq.com/sns/jscode2session?appid={}&secret={}&js_code={' \
                '}&grant_type=authorization_code'
    max_retry_count = 2
    retry_interval_s = 0.3

    def __init__(self, app):
        self.app = app
        self.access_token = ''
        self.access_token_expires_timestamp_s = time.time()
        self.count_http_retry = 0

    def __get_token(self):
        self.app.logger.info('WxMini.get_token...')
        now = time.time()
        if now < self.access_token_expires_timestamp_s:
            self.app.logger.info('WxMini.get_token not expired')
            self.count_http_retry = 0
            return 0, '', self.access_token

        try:
            self.app.logger.info('WxMini.get_token request')
            response = requests.get(self.token_url, timeout=1)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.app.logger.error('WxMini.get_token.Timeout: {}'.format(e))
            self.count_http_retry += 1
            if self.count_http_retry < WxMini.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(WxMini.retry_interval_s))
                return self.__get_token()
            else:
                self.count_http_retry = 0
                return IngError.WXTokenTimeout.value, str(e), ''
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.get_token.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXTokenHTTPError.value, str(e), ''
        except Exception as e:
            self.app.logger.error('WxMini.get_token.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXTokenOtherError.value, str(e), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            self.access_token = result['access_token']
            self.access_token_expires_timestamp_s = now + result['expires_in']
            return 0, '', self.access_token

    # ing_key: WX 文档里所说的"自定义用户态"
    def login(self, js_code, ing_key):
        try:
            self.app.logger.info('WxMini.login...: js_code: {}, ing_key: {}'.format(js_code, ing_key))
            login_url = WxMini.login_url.format(WxMini.app_id, WxMini.app_secret, js_code)
            self.app.logger.info('WxMini.login...: url: {}'.format(login_url))
            response = requests.get(login_url)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.app.logger.error('WxMini.login.Timeout: {}'.format(e))
            self.count_http_retry += 1
            if self.count_http_retry < WxMini.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(WxMini.retry_interval_s))
                return self.login(js_code)
            else:
                self.count_http_retry = 0
                return IngError.WXLoginTimeout.value, str(e), ''
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.login.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXLoginHTTPError.value, str(e), ''
        except Exception as e:
            self.app.logger.error('WxMini.login.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXLoginOtherError.value, str(e), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            self.app.logger.info('WxMini.login.result: {}'.format(result))
            if result['errcode'] != 0:
                self.app.logger.error('WxMini.login.APIError: {}'.format(result))
                return IngError.WXLoginAPIError.value, 'wx errcode: {}, wx errmsg: {}'.format(result['errcode'],
                                                                                              result['errmsg']), ''

            user_openid = result['openid']
            user_session_key = result['session_key']
            user_unionid = result['unionid']
            # todo: 保存到数据库, js_code 是临时的
            # if NOT ing_key，数据库更新下数据，否则 insert
            self.app.logger.info(
                'User: {} logined, openid: {}, session_key: {}, unionid: {}, last_ingKey: {}'.format(js_code,
                                                                                                     user_openid,
                                                                                                     user_session_key,
                                                                                                     user_unionid,
                                                                                                     ing_key))
            return 0, '', 'IUEIROJF&234234'  # ing_key

    def get_ocr(self, img_url):
        self.app.logger.info('WxMini.get_ocr...')
        self.__get_token()
        wx_url = WxMini.ocr_url.format(self.access_token, img_url)
        try:
            response = requests.post(wx_url)
            response.raise_for_status()
        except exceptions.Timeout as e:
            self.app.logger.error('WxMini.get_ocr.Timeout: {}'.format(e))
            self.count_http_retry += 1
            if self.count_http_retry < WxMini.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(WxMini.retry_interval_s))
                return self.get_ocr(img_url)
            else:
                self.count_http_retry = 0
                return IngError.WXOcrTimeout.value, str(e), ''
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.get_ocr.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXOcrHTTPError.value, str(e), ''
        except Exception as e:
            self.app.logger.error('WxMini.get_ocr.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXOcrOtherError.value, str(e), ''
        else:
            self.count_http_retry = 0
            result = response.json()
            if result['errcode'] != 0:
                self.app.logger.error('WxMini.get_ocr.APIError: {}'.format(result))
                return IngError.WXOcrAPIError.value, 'wx errcode: {}, wx errmsg: {}'.format(result['errcode'],
                                                                                            result['errmsg']), ''

            ocr_result = ''
            items = result['items']
            for item in items:
                ocr_result += item['text'] + ' '

            return 0, '', ocr_result
