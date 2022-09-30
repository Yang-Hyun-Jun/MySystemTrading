from abc import ABCMeta, abstractmethod


class Stratgy(metaclass=ABCMeta):
    """
    데이터를 받아서 정해진 전랙에 따라
    매매 판단을 하고 결과를 받아서 다음 판단에 반영하는 Strategy 추상 클래스
    """

    @abstractmethod
    def initialize(self, budget, min_price=100):
        """ 
        예산을 설정하고 초기화한다.
        """

    @abstractmethod
    def get_request(self):
        """
        거래 요청 내용 생성

        return:
        [{
            "id": 오청 정보 id "1607862457.560075",
            "type": 거래 유형 sell, buy, cancel,
            "price": 거래 가격,
            "amount": 거래 수량,
            "date_time": 요청 생성 시간, 시뮬레이션에서는 데이터 시간
        }]
        """

    @abstractmethod
    def update_trading_info(self, info):
        """
        종목 정보 업데이트

        info:
        {
            "market": 거래 시장 종류 BTC,
            "date_time": 정보의 기준 시간, 
            "opening_price": 시가,
            "high_price": 고가,
            "low_price": 저가,
            "clsoing_price": 종가,
            "acc_price": 단위 시간내 누적 거래 금액,
            "acc_volume": 단위 시간내 누적 거래 양
        }
        """

    @abstractmethod
    def update_result(self, result):
        """
        요청한 거래의 결과를 업데이트

        result:
        {
            "request": 거래 요청 내용,
            "type": 거래 유형 sell, buy, cancel,
            "price": 거래 가격,
            "amount": 거래 수량,
            "state": 거래 상태 requested, done
            "msg": 거래 결과 메시지,
            "date_time": 거래 체결 시간
        }
        """