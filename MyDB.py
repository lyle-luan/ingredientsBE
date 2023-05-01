import mysql.connector.pooling
import time
import datetime

class MyDB:
    api_key = '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'
    prompt = '提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议，少于 100 个字: {}'
    max_retry_count = 2
    retry_interval_s = 0.3

    def __init__(self, log):
        db_config = {
            "host": "localhost",
            "user": "ingredient",
            "password": "FaTqs-_7",
            "database": "ingredient"
        }
        self.db_pool = mysql.connector.pooling.MySQLConnectionPool(pool_size=5, **db_config)
        self.mydb = self.db_pool.get_connection()
        self.log = log

    def update_usage(self, uid, img_path, ocr, openai_answer):
        cursor = self.mydb.cursor()
        query = "update user set usage_count=usage_count+1 where uid=%s"
        self.log.info(query)
        cursor.execute(query, (uid,))
        cursor.close()

        now_timestamp = int(time.time())
        now_timestamp_str = datetime.datetime.fromtimestamp(now_timestamp).strftime(
            '%Y-%m-%d %H:%M:%S')
        cursor = self.mydb.cursor()
        query = "insert into `usage` (uid, img_path, ocr, openai_answer, timestamp) values (%s, %s, %s, %s)"
        self.log.info(query)
        cursor.execute(query, (uid, img_path, ocr, openai_answer, now_timestamp_str))
        cursor.close()
        self.mydb.commit()

    def usage_info_of_uid(self, uid):
        cursor = self.mydb.cursor()
        query = "select usage_count, usage_limit from user where uid=%s"
        self.log.info(query)
        cursor.execute(query, (uid,))
        results = cursor.fetchall()
        self.log.info('select result: {}'.format(results))
        cursor.close()
        if len(results) > 0:
            return results[0]
        else:
            return -1, -1

    def create_user(self, wx_open_id, wx_session_key, wx_expires_timestamp_str):
        cursor = self.mydb.cursor()
        query = "insert into user (wx_open_id, wx_session_key, wx_expires_timestamp) values (%s, %s, %s) " \
                "RETURNING uid;"
        self.log.info(query)
        cursor.execute(query, (wx_open_id, wx_session_key, wx_expires_timestamp_str))
        uid, = cursor.fetchone()
        self.log.info('return uid: {}'.format(uid))
        cursor.close()
        self.mydb.commit()
        return uid

    def update_or_create_user(self, uid, wx_open_id, wx_session_key, wx_expires_timestamp_str):
        cursor = self.mydb.cursor()
        query = "insert into user (wx_open_id, wx_session_key, wx_expires_timestamp) values (%s, %s, %s) " \
                "ON DUPLICATE KEY UPDATE " \
                "wx_open_id = values(wx_open_id)," \
                "wx_session_key = values(wx_session_key)," \
                "wx_expires_timestamp = values(wx_expires_timestamp) " \
                "RETURNING uid;"
        self.log.info(query)
        cursor.execute(query, (wx_open_id, wx_session_key, wx_expires_timestamp_str))
        uid, = cursor.fetchone()
        self.log.info('return uid: {}'.format(uid))
        cursor.close()
        self.mydb.commit()
        return uid

    def wx_expires_timestamp_of_user(self, uid):
        cursor = self.mydb.cursor()
        query = "select wx_expires_timestamp from user where uid=%s"
        cursor.execute(query, (uid,))
        wx_expires_timestamp, = cursor.fetchone()
        self.log.info('return wx_expires_timestamp: {}'.format(wx_expires_timestamp))
        cursor.close()
        return wx_expires_timestamp
