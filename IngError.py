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
    OpenAIOtherError = 9
    WXTokenTimeout = 10
    WXTokenHTTPError = 11
    WXTokenOtherError = 11
    WXOcrTimeout = 12
    WXOcrHTTPError = 13
    WXOcrAPIError = 14
    WXOcrOtherError = 14
    WXLoginTimeout = 12
    WXLoginHTTPError = 13
    WXLoginAPIError = 14
    WXLoginOtherError = 14
    WXLoginRequestParameterError = 15
    UploadOtherError = 100
    LoginOtherError = 200
