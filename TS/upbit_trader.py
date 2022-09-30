import os
import copy
import uuid
import threading
import hashlib
import requests
import jwt

from datetime import datetime
from urllib.parse import urlencode
from urllib.parse import unquote
from urllib import request, response
from dotenv import load_dotenv

from .upbit_api import UpbitAPI
from .log_manager import LogManager
from .trader import Trader
from .worker import Worker

load_dotenv(verbose=True)


class UpbitTrader(Trader):
    """
    거래 요청 정보를 받아서 
    업비트 거래소에 요청하고 거래소에서 받은 결과를 제공해주는 클래스

    request['id']: TS 내에서 사용하는 주문의 고유 번호
    response['uuid']: 거래소 내에서 사용하는 주문의 고유 번호

    order_map: 
    {
        request[id]: {"uuid": response["uuid"], "callback": task["callback"], "result": result}
    }

    result:
    {
        uuid: 요청 정보
        type: 거래 유형
        price: 거래 가격
        amount: 거래 수량
        msg: 메시지
        state: 거래 상태
        date_time: 결과 생성 시간
    }
    """

    MARKET = "KRW-BTC"
    MARKET_CURRENCY = "BTC"
    ISO_DATEFORMAT = "%Y-%m-%dT%H:%M:%S"
    COMMISSION_RATIO = 0.0005
    RESULT_CHECKING_INTERVAL = 5

    def __init__(self):
        self.logger = LogManager.get_logger(__class__.__name__)
        self.worker = Worker("UpbitTrader-Worker")
        self.worker.start()

        self.timer = None
        self.order_map = {}
        self.asset = (0, 0)
        self.balance = None
        self.name = "Upbit"
        self.is_initialized = False

        self.ACCESS_KEY = os.environ.get("UPBIT_OPEN_API_ACCESS_KEY", "upbit_access_key")
        self.SECRET_KEY = os.environ.get("UPBIT_OPEN_API_SECRET_KEY", "upbit_secret_key")
        self.SERVER_URL = os.environ.get("UPBIT_OPEN_API_SERVER_URL", "upbit_server_url")

        self.upbit_api = UpbitAPI(self.ACCESS_KEY, self.SECRET_KEY, self.SERVER_URL, self.MARKET)

    def initialize(self, budget):
        self.balance = budget
        self.is_initialized = True

    def send_request(self, request_list, callback):
        """
        거래 요청을 처리한다. 
        """
        if self.is_initialized == False:
            raise UserWarning("Upbit Trader is not initialized")

        for request in request_list:
            self.worker.post_task({"runnable": self._execute_order, "request": request, "callback": callback})
    
    def cancel_request(self, request_id):
        """
        거래 요청을 취소한다.
        """
        if self.is_initialized == False:
            raise UserWarning("Upbit Trader is not initialized")
            
        if request_id not in self.order_map:
            return
        
        # request id로 주문 가져오기
        order = self.order_map[request_id]
        del self.order_map[request_id]

        # 취소 주문 후 response 받아오기
        result = order["result"]
        response = self.upbit_api.cancel_order(order["uuid"]) 
        self.logger.debug(f"Canceled order {response}")

        # 최종 체결 가격, 수량으로 업데이트 (체결 된게 없으면 0)
        result["price"] = float(response["price"]) if response["price"] is not None else 0 
        result["date_time"] = response["created_at"].replace("+09:00", "")
        result["state"] = "done"
        self._call_callback(order["callback"], result)

    def cancel_all_requests(self):
        """
        모든 거래 요청을 취소한다.
        체결되지 않고 대기중인 모든 거래 요청을 취소한다.
        """
        orders = copy.deepcopy(self.order_map)
        for request_id in orders.keys():
            self.cancel_request(request_id)

    def get_account_info(self):
        """
        계좌 정보를 요청한다.
        return:
            {
                balance: 계좌 현금 잔고
                asset: 자산 목록, 마켓이름을 키값으로 갖고 (평균 매입 가격, 수량)을 갖는 딕셔너리
                quote: 종목별 현재 가격 딕셔너리
                date_time: 현재 시간
            }
        """
        trade_info = self.upbit_api.get_trade_tick() # 최근 체결 정보
        result = {
            "balance": self.balance,
            "asset": {self.MARKET_CURRENCY: self.asset},
            "quote": {},
            "date_time": datetime.now().strftime(self.ISO_DATEFORMAT)} 
        
        result["quote"][self.MARKET_CURRENCY] = float(trade_info[0]["trade_price"])
        self.logger.debug(f"account info | banance: {result['balance']} | {result['asset']} | {result['quote']}")
        return result

#################################################################################################################################

    def _execute_order(self, task):
        request = task["request"]
        is_buy = request["type"] == "buy" 
        # 주문 취소
        if request["type"] == "cancel":
            self.cancel_request(request["id"])
            return
        # price 0
        if request["price"] == 0:
            self.logger.warning("Invalid price request, zero price is not supported now")
            return
        # 매수 시 잔고가 부족하다면
        if is_buy and float(request["price"]) * float(request["amount"]) > self.balance:
            self.logger.warning("Invalid price request. Balance is too small!")
            task["callback"]("error")
            return
        # 매도 시 보유 수량이 부족하다면
        if is_buy is False and float(request["amount"]) > self.asset[1]:
            self.logger.warning(f"Invalid price request. RQ:{request['amount']} > MY: {self.asset[1]}")
            task["callback"]("error")
            return

        # 주문 요청
        if is_buy:
            response = self.upbit_api.send_order(self.MARKET, is_buy, price=request["price"], volume=None) 
        else:
            response = self.upbit_api.send_order(self.MARKET, is_buy, price=None, volume=request["amount"]) 

        if response is None:
            task["callback"]("error")
            return
        
        # 주문 정보 저장 해놓기 (체결 결과 및 취소 주문을 위해서)
        result = {
            "uuid": response["uuid"], 
            "state": "requested", "request": request, 
            "type": request["type"],
            "price": request["price"],
             "amount": request["amount"],
            "msg": "success"
            }
        self.order_map[request["id"]] = {
            "uuid": response["uuid"],
            "callback": task["callback"],
            "result": result
            }

        self._start_timer()

    def _start_timer(self):
        """ 일정 시간 이후 주문 상태 테스트 추가 후 """
        if self.timer is not None:
            return
        
        def post_get_result_task():
            self.worker.post_task({"runnable": self._get_order_result})
        
        self.timer = threading.Timer(self.RESULT_CHECKING_INTERVAL, post_get_result_task)
        self.timer.start()

    def _stop_timer(self):
        if self.timer is None:
            return

        self.timer.cancel()
        self.timer = None

    def _get_order_result(self, task):
        """
        order map으로부터
        넣은 주문들에 대한 결과 생성
        """
        del task
        uuids = []
        # Interval 동안 넣은 주문의 uuid를 order_map에서 가져오기
        for request_id, order in self.order_map.items():
            uuids.append(order["uuid"])
        
        if len(uuids) == 0:
            return
        
        # 해당 uuid에서 [done, cancel] 주문들 조회
        # 시장가 매수 주문의 경우 잔량이 남으면 (소수점 문제로) cancel로 처리될 수도 있음
        order_results = self.upbit_api.get_order_list(uuids, is_done_state=True)
        if order_results is None:
            return

        waiting_request = {}
        self.logger.debug(f"waiting order count: {len(self.order_map)}")
        for request_id, request in self.order_map.items():
            # 주문이 주문 내역에서 조회된 경우: 체결 완료 
            is_done = False
            for order_result in order_results:
                if request["uuid"] == order_result["uuid"]:
                    order_final = self.upbit_api.get_order_one(request["uuid"])

                    result = request["result"]
                    result["date_time"] = order_final["created_at"].replace("+09:00", "")
                    # 최종 체결 가격, 수량으로 업데이트
                
                    result["price"] = float(order_final["trades"][0]['price'])
                    result["amount"] = float(order_final["trades"][0]['volume'])
                    result["state"] = "done"
                    self._call_callback(request["callback"], result)
                    is_done = True
            
            # 주문이 주문 내역에서 조회되지 않는 경우: 체결 대기
            if is_done is False:
                self.logger.debug(f"waiting order {request}")
                waiting_request[request_id] = request
                
        self.order_map = waiting_request
        self.logger.debug(f"After resulting, waiting order count: {len(self.order_map)}")
        self._stop_timer()
        if len(self.order_map) > 0:
            self._start_timer()

    def _call_callback(self, callback, result):
        """
        result 받아서 self.asset, self.balance 업데이트하고
        콜백으로 결과 전달
        """
        old_balance = self.balance
        result_value = float(result["price"]) * float(result["amount"])
        fee = result_value * self.COMMISSION_RATIO

        # 매수 체결 주문의 경우 
        if result["state"] == "done" and result["type"] == "buy":
            old_value = self.asset[0] * self.asset[1]
            new_value = old_value + result_value
            new_amount = self.asset[1] + float(result["amount"])
            new_amount = round(new_amount, 8)
            
            if new_amount == 0:
                avr_price = 0
            else:
                avr_price = new_value / new_amount
            
            self.asset = (avr_price, new_amount)
            self.balance -= round(result_value + fee)

        # 매도 체결 주문의 경우
        elif result["state"] == "done" and result["type"] == "sell":
            old_avr_price = self.asset[0]
            new_amount = self.asset[1] - float(result["amount"])
            new_amount = round(new_amount, 8)

            if new_amount == 0:
                old_avr_price = 0
            
            self.asset = (old_avr_price, new_amount)
            self.balance += round(result_value - fee)
        
        print(f"잔고 변화: {old_balance} -> {self.balance}")
        callback(result)




