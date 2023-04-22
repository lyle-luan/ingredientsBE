from enum import Enum, unique


class IngError(Enum):
    UploadNoImg = 1
    UploadImgNoName = 2
    OpenAIAPIError = 3
    OpenAITimeout = 4
    OpenAIRateLimitError = 5
    OpenAIAPIConnectionError = 6
    OpenAIInvalidRequestError = 7
    OpenAIAuthenticationError = 8
    OpenAIServiceUnavailableError = 9
    WXTokenTimeout = 10
    WXTokenHTTPError = 11
    WXOcrTimeout = 12
    WXOcrHTTPError = 13
    WXOcrAPIError = 14
