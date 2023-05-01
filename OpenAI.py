import asyncio
import openai
from IngError import IngError


async def delayed_response(interval):
    await asyncio.sleep(interval)


class OpenAI:
    api_key = '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'
    prompt = '提取下面文字中的食品配料表，并分析每种配料对人体是否健康，并给出食用建议，少于 100 个字: {}'
    max_retry_count = 2
    retry_interval_s = 0.3

    def __init__(self, app):
        openai.api_key = OpenAI.api_key
        self.count_retry = 0
        self.app = app

    def ask(self, ingredients: str):
        try:
            self.app.logger.info('OpenAI.ask...: {}'.format(ingredients))
            response = openai.Completion.create(
                engine='text-davinci-003',
                prompt=OpenAI.prompt.format(ingredients),
                max_tokens=3000,
                n=1,
                stop=None,
                temperature=0.3).choices
        except openai.error.APIError as e:
            self.app.logger.error('OpenAI.ask.APIError: {}'.format(e))
            self.count_retry = 0
            return IngError.OpenAIAPIError.value, 'openai.error.APIError', ''
        except openai.error.Timeout as e:
            self.app.logger.error('OpenAI.ask.Timeout: {}'.format(e))
            self.count_retry += 1
            if self.count_retry < OpenAI.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(OpenAI.retry_interval_s))
                return self.ask(ingredients)
            self.count_retry = 0
            return IngError.OpenAITimeout.value, 'openai.error.Timeout', ''
        except openai.error.RateLimitError as e:
            self.app.logger.error('OpenAI.ask.RateLimitError: {}'.format(e))
            self.count_retry += 1
            if self.count_retry < OpenAI.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(OpenAI.retry_interval_s))
                return self.ask(ingredients)
            self.count_retry = 0
            return IngError.OpenAIRateLimitError.value, 'openai.error.RateLimitError', ''
        except openai.error.APIConnectionError as e:
            self.app.logger.error('OpenAI.ask.APIConnectionError: {}'.format(e))
            self.count_retry += 1
            if self.count_retry < OpenAI.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(OpenAI.retry_interval_s))
                return self.ask(ingredients)
            self.count_retry = 0
            return IngError.OpenAIAPIConnectionError.value, 'openai.error.APIConnectionError', ''
        except openai.error.InvalidRequestError as e:
            self.app.logger.error('OpenAI.ask.InvalidRequestError: {}'.format(e))
            self.count_retry = 0
            return IngError.OpenAIInvalidRequestError.value, 'openai.error.InvalidRequestError', ''
        except openai.error.AuthenticationError as e:
            self.app.logger.error('OpenAI.ask.AuthenticationError: {}'.format(e))
            self.count_retry = 0
            return IngError.OpenAIAuthenticationError.value, 'openai.error.AuthenticationError', ''
        except openai.error.ServiceUnavailableError as e:
            self.app.logger.error('OpenAI.ask.ServiceUnavailableError: {}'.format(e))
            self.count_retry += 1
            if self.count_retry < OpenAI.max_retry_count:
                asyncio.get_event_loop().run_until_complete(delayed_response(OpenAI.retry_interval_s))
                return self.ask(ingredients)
            self.count_retry = 0
            return IngError.OpenAIServiceUnavailableError.value, 'openai.error.ServiceUnavailableError', ''
        except Exception as e:
            self.app.logger.error('OpenAI.ask.OtherException: {}'.format(e))
            self.count_retry = 0
            return IngError.OpenAIOtherError.value, str(e), ''
        else:
            result = ''
            for item in response:
                result += item.text
            self.count_retry = 0
            return 0, 'success', result
