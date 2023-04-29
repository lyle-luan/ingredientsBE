import datetime

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

    def __init__(self, app, mydb):
        self.app = app
        self.mydb = mydb
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
                return IngError.WXTokenTimeout.value, str(e), None
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.get_token.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXTokenHTTPError.value, str(e), None
        except Exception as e:
            self.app.logger.error('WxMini.get_token.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXTokenOtherError.value, str(e), None
        else:
            self.count_http_retry = 0
            result = response.json()
            self.access_token = result['access_token']
            self.access_token_expires_timestamp_s = now + result['expires_in']
            return 0, '', self.access_token

    def __db_insert_create_user(self, wx_open_id, wx_session_key, wx_expires_timestamp_str):
        cursor = self.mydb.cursor()
        query = "insert into user (wx_open_id, wx_session_key, wx_expires_timestamp) values (%s, %s, %s)"
        self.app.logger.info(query)
        cursor.execute(query, (wx_open_id, wx_session_key, wx_expires_timestamp_str,))
        self.mydb.commit()
        cursor.close()
        cursor = self.mydb.cursor()
        query = "select uid from user where wx_open_id = \"{}\" and wx_session_key = \"{}\"".format(wx_open_id,
                                                                                                    wx_session_key)
        self.app.logger.info(query)
        cursor.execute(query)
        uid_all = cursor.fetchall()
        self.app.logger.info('select result: {}'.format(uid_all))
        cursor.close()
        for row in uid_all:
            self.app.logger.info('select uid: {} from: {}'.format(row, query))
        if len(uid_all) > 0:
            uid = uid_all[0]
            if len(uid_all) > 1:
                self.app.logger.warn('select uid: {} from : {}'.format(uid_all, query))
            return uid[0]
        else:
            return None

    def __wx_login(self, js_code, uid):
        try:
            self.app.logger.info('WxMini.login...: js_code: {}, uid: {}'.format(js_code, uid))
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
                return IngError.WXLoginTimeout.value, str(e), None
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.login.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXLoginHTTPError.value, str(e), None
        except Exception as e:
            self.app.logger.error('WxMini.login.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXLoginOtherError.value, str(e), None
        else:
            self.count_http_retry = 0
            result = response.json()
            self.app.logger.info('WxMini.login.result: {}'.format(result))
            wx_openid = result['openid']
            wx_session_key = result['session_key']
            wx_expires_in = result['expires_in']
            self.app.logger.info(
                'User: {} logined, openid: {}, session_key: {}, expires_in: {}, last_ingKey: {}'.format(js_code,
                                                                                                        wx_openid,
                                                                                                        wx_session_key,
                                                                                                        wx_expires_in,
                                                                                                        uid))
            wx_expires_timestamp = int(time.time()) + wx_expires_in
            wx_expires_timestamp_str = datetime.datetime.fromtimestamp(wx_expires_timestamp).strftime(
                '%Y-%m-%d %H:%M:%S')
            if not uid:
                uid_new = self.__db_insert_create_user(wx_openid, wx_session_key, wx_expires_timestamp_str)
                self.app.logger.info("uid_new: {}".format(uid_new))
                if not uid_new:
                    return IngError.DBInsertNewUserError.value, 'insert new user error', None
                else:
                    return 0, '', uid_new
            else:
                cursor = self.mydb.cursor()
                query = "select uid from user where uid = \"{}\"".format(uid)
                self.app.logger.info(query)
                cursor.execute(query)
                uid_all = cursor.fetchall()
                cursor.close()
                if len(uid_all) > 0:
                    cursor = self.mydb.cursor()
                    query = "update user set wx_open_id=%s, wx_session_key=%s, wx_expires_timestamp=%s where uid=%s"
                    self.app.logger.info(query)
                    cursor.execute(query, (wx_openid, wx_session_key, wx_expires_timestamp_str, uid))
                    self.mydb.commit()
                    cursor.close()
                    return 0, '', uid
                else:
                    uid_new = self.__db_insert_create_user(wx_openid, wx_session_key, wx_expires_timestamp_str)
                    if not uid_new:
                        return IngError.DBInsertNewUserError.value, 'insert new user error', None
                    else:
                        return 0, '', uid_new

    # uid: WX 文档里所说的"自定义用户态"
    def login(self, js_code, uid):
        if (not js_code) or (len(js_code) == 0):
            return IngError.WXLoginRequestParameterError.value, 'no js_code', None

        if not uid:
            return self.__wx_login(js_code, None)
        else:
            cursor = self.mydb.cursor()
            query = "select wx_expires_timestamp from user where uid=%s"
            cursor.execute(query, (uid,))
            results = cursor.fetchall()
            cursor.close()
            if len(results) > 0:
                wx_expires_timestamp, = results[0]
                elapsed_time = int(wx_expires_timestamp.timestamp()) - int(time.time())
                if elapsed_time <= 0:
                    self.app.logger.info('login uid: {}, timeout'.format(uid))
                    return self.__wx_login(js_code, uid)
                else:
                    self.app.logger.info('login uid: {}, not timeout'.format(uid))
                    return 0, '', uid
            else:
                return self.__wx_login(js_code, None)

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
                return IngError.WXOcrTimeout.value, str(e), None
        except exceptions.HTTPError as e:
            self.app.logger.error('WxMini.get_ocr.HTTPError: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXOcrHTTPError.value, str(e), None
        except Exception as e:
            self.app.logger.error('WxMini.get_ocr.OtherException: {}'.format(e))
            self.count_http_retry = 0
            return IngError.WXOcrOtherError.value, str(e), None
        else:
            self.count_http_retry = 0
            result = response.json()
            if result['errcode'] != 0:
                self.app.logger.error('WxMini.get_ocr.APIError: {}'.format(result))
                return IngError.WXOcrAPIError.value, 'wx errcode: {}, wx errmsg: {}'.format(result['errcode'],
                                                                                            result['errmsg']), None

            ocr_result = ''
            items = result['items']
            for item in items:
                ocr_result += item['text'] + ' '

            return 0, '', ocr_result
