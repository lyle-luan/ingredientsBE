import asyncio
from EdgeGPT import Chatbot, ConversationStyle
from IngError import IngError


class BingGPT:
    max_retry_count = 2
    retry_interval_s = 0.3

    def __init__(self, app):
        self.count_retry = 0
        self.app = app
        self.bot = Chatbot.create(cookie_path='./cookies.json')

    def ask(self, ingredients: str):
        try:
            self.app.logger.info('BingGPT.ask...: {}'.format(ingredients))
            response = self.bot.ask(
                prompt="提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议，少于 100 个字:{}".format(
                    ingredients),
                conversation_style=ConversationStyle.creative)
        except Exception as e:
            self.app.logger.error('BingGPT.ask.OtherException: {}'.format(e))
            self.count_retry = 0
            return IngError.BingOtherError.value, str(e), ''
        else:
            item = response['item']
            if item:
                result = item['result']
                if result:
                    value = result['value']
                    if value and value == 'Success':
                        messages = item['messages']
                        for message in messages:
                            text = message['text']
                            author = message['author']
                            if author and author == 'bot':
                                if text:
                                    return 0, 'success', text
                                else:
                                    return IngError.BingAskResultError.value, 'BingGPT ask failed', ''

            return IngError.BingAskResultError.value, 'BingGPT ask failed', ''
