import requests
import pandas as pd 

from urllib import response
from .date_converter import DateConverter
from .data_provider import DataProvider
from .log_manager import LogManager
from .upbit_api import UpbitAPI


class UpbitDataProvider(DataProvider):
    """
    업비트 거래소의 실시간 거래 데이터를 제공하는 클래스
    업비트 open api를 사용, 별도의 가입, 인증, token 없이 사용 가능
    """

    URL = "https://api.upbit.com/v1/candles/minutes/1"
    
    def __init__(self):
        self.logger = LogManager.get_logger(__class__.__name__)
        self.query_string = {"market": "KRW-BTC", "count": 1}
        self.upbit_api = UpbitAPI(access_key=0, secret_key=0, server_url=0, market=0)
    
    def set_market(self, market="KRW-BTC"):
        """ 마켓을 설정한다 """
        self.query_string["market"] = market

    def get_info(self):
        """
        실시간 거래 정보 전달한다. 

        
        returns: 거래 정보 info
        {
            "market": 거래 시장 종류 BTC
            "date_time": 정보의 기준 시간
            "opening_price": 시작 거래 가격
            "high_price": 최고 거래 가격
            "low_price": 최저 거래 가격
            "closing_price": 마지막 거래 가격
            "acc_price": 단위 시간내 누적 거래 금액
            "acc_volume": 단위 시간내 누적 거래 양
        } 
        """

        data = self.__get_data_from_server()
        return self.__create_candle_info(data[0])

    def get_history_df(self, from_dash_to): 
        """
        날짜를 입력으로 받아서 과거 데이터 프레임 로드 
        """
        strat, end, count = DateConverter.to_end_min(from_dash_to)
        self.query_string["to"] = DateConverter.from_kst_to_utc_str(end) + "Z"
        self.query_string["count"] = count
        response = self.upbit_api.get_data_from_server(url=self.URL, params=self.query_string)
        response.reverse()
        return pd.DataFrame(response)
    
    def __create_candle_info(self, data):
        try:
            return {
                "market": data["market"],
                "date_time": data["candle_date_time_kst"],
                "opening_price": float(data["opening_price"]),
                "high_price": float(data["high_price"]),
                "low_price": float(data["low_price"]),
                "closing_price": float(data["trade_price"]),
                "acc_price": float(data["candle_acc_trade_price"]),
                "acc_volume": float(data["candle_acc_trade_volume"]),
            }
        
        except KeyError:
            self.logger.warning("Invalid data for candle info")
            return None
        
    def __get_data_from_server(self):
        return self.upbit_api.get_data_from_server(url=self.URL, params=self.query_string)
