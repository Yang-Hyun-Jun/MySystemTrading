import uuid
import threading
import hashlib
import requests
import jwt

from datetime import datetime
from urllib import request, response
from urllib.parse import urlencode
from urllib.parse import unquote
from dotenv import load_dotenv
from .log_manager import LogManager
from .date_converter import DateConverter

class UpbitAPI:

    def __init__(self, access_key, secret_key, server_url, market):
        self.ACCESS_KEY = access_key
        self.SECRET_KEY = secret_key
        self.SERVER_URL = server_url
        self.market = market
        self.logger = LogManager.get_logger(__class__.__name__)
    

    def send_order(self, market, is_buy, price=None, volume=None):
        """
        주문 접수

        response:
            uuid: 주문 아이디 string
            side: 주문 종류 string
            ord_type: 주문 방식 string
            price: 주문 당시 가격, NumberString
            avg_price: 체결 가격의 평균가 NumberString
            state: 주문 상태, String
            market: 마켓의 유일키, String
            created_at: 주문 생성 시간, String
            volume: 사용자가 입력한 주문 양, NumberString
            remaining_volume: 체결 잔량, NumberString
            reserved_fee: 수수료로 예약된 비용, NumberString
            remaining_fee: 남은 수수료, NumberString
            paid_fee: 사용된 수수료, NumberString
            locked: 거래에 사용중인 비용, NumberString
            trade_acount: 해당 주문의 체결 수, Integer    
        """
        # 지정가 주문
        if price is not None and volume is not None:
            query_string = self._create_limit_order_query(market, is_buy, price, volume)

        # 시장가 매도        
        elif volume is not None and is_buy is False:
            self.logger.warning("### Market price sell order is submitted ###")
            query_string = self._create_market_price_order_query(market, volume=volume)
        
        # 시장가 매수        
        elif price is not None and is_buy is True:
            self.logger.warning("### Marker price buy order is submitted ###")
            query_string = self._create_market_price_order_query(market, price=price)
        
        # 잘못된 주문
        else:
            self.logger.error("Invalid order")
            return None            

        # 토큰 생성
        jwt_token = self._create_jwt_token(self.ACCESS_KEY, self.SECRET_KEY, query_string)
        authorize_token = f"Bearer {jwt_token}"
        headers = {"Authorization": authorize_token}

        # 주문
        try:
            response = requests.post(self.SERVER_URL + "/v1/orders", params=query_string, headers=headers)
            response.raise_for_status()
            result = response.json()

        except ValueError:
            self.logger.error("Invalid data from server")
            return None
        except requests.exceptions.HTTPError as msg:
            self.logger.error(msg)
            return None
        except requests.exceptions.RequestException as msg:
            self.logger.error(msg)
            return None
        return result


    def cancel_order(self, request_uuid):
        """
        개별 취소 주문 접수

        response:
            uuid: 주문 아이디 string
            side: 주문 종류 string
            ord_type: 주문 방식 string
            price: 주문 당시 가격, NumberString
            avg_price: 체결 가격의 평균가 NumberString
            state: 주문 상태, String
            market: 마켓의 유일키, String
            created_at: 주문 생성 시간, String
            volume: 사용자가 입력한 주문 양, NumberString
            remaining_volume: 체결 잔량, NumberString
            reserved_fee: 수수료로 예약된 비용, NumberString
            remaining_fee: 남은 수수료, NumberString
            paid_fee: 사용된 수수료, NumberString
            locked: 거래에 사용중인 비용, NumberString
            trade_acount: 해당 주문의 체결 수, Integer        
        """
        self.logger.info(f"CANCEL ORDER ##### {request_uuid}")

        query = {"uuid": request_uuid}
        query_string = urlencode(query).encode()

        jwt_token = self._create_jwt_token(self.ACCESS_KEY, self.SECRET_KEY, query_string)
        authorize_token = f"Bearer {jwt_token}"
        headers = {"Authorization": authorize_token}

        try:
            response = requests.delete(self.SERVER_URL + "/v1/order", params=query_string, headers=headers)
            response.raise_for_status()
            result = response.json()
        
        except ValueError:
            self.logger.error("Invalid data from server")
            return None
        except requests.exceptions.HTTPError as msg:
            self.logger.error(msg)
            return None
        except requests.exceptions.RequestException as msg:
            self.logger.error(msg)
            return None
        return result


    def get_data_from_server(self, url, params):
        """ 
        서버에서 데이터 로드
        """
        try:
            response = requests.get(url=url, params=params)
            response.raise_for_status()
            return response.json()
        
        except ValueError as error:
            self.logger.error("Invalid data from server")
            raise UserWarning("Fail get data from server") from error
        except requests.exceptions.HTTPError as error:
            self.logger.error(error)
            raise UserWarning("Fail get data from server") from error
        except requests.exceptions.RequestException as error:
            self.logger.error(error)
            raise UserWarning("Fail get data from server") from error

    def get_order_list(self, uuids, is_done_state):
        """ 
        주문들 상태 리스트 조회 

        # 매수 주문의 경우 
        [{'uuid': 'cc87341b-9892-49fa-9cdc-c60028431b0c',
        'side': 'bid',
        'ord_type': 'price',
        'price': '10000',
        'state': 'cancel',
        'market': 'KRW-BTC',
        'created_at': '2022-09-28T13:42:16+09:00',
        'reserved_fee': '5',
        'remaining_fee': '0.00010352',
        'paid_fee': '4.99989648',
        'locked': '0.20714352',
        'executed_volume': '0.00036768',
        'trades_count': 1}]

        # 매도 주문의 경우
        [{'uuid': '0745ac08-4087-474a-8b3f-6e88cf7d0b42',
        'side': 'bid', 
        'ord_type': 'price', 
        'price': '10000',
        'state': 'cancel', 
        'market': 'KRW-BTC', 
        'created_at': '2022-09-28T14:51:46+09:00', 
        'reserved_fee': '5', 
        'remaining_fee': '0.000114805',
        'paid_fee': '4.999885195', 
        'locked': '0.229724805', 
        'executed_volume': '0.00036749',** 
        'trades_count': 1}]
        """
        query_states = ["wait", "watch"]
        if is_done_state:
            query_states = ["done", "cancel"]

        states_query_string = "&".join([f"states[]={state}" for state in query_states])
        uuids_query_string = "&".join([f"uuids[]={uuid}" for uuid in uuids])
        query_string = (states_query_string + "&" + uuids_query_string).encode()

        jwt_token = self._create_jwt_token(self.ACCESS_KEY, self.SECRET_KEY, query_string)
        authorize_token = f"Bearer {jwt_token}"
        headers = {"Authorization": authorize_token}

        order_list = self._request_get(self.SERVER_URL + "/v1/orders", params=query_string, headers=headers)
        return order_list


    def get_order_one(self, uuid):
        """ 
        한 개의 주문 상태 조회 

        {'uuid': '508d57ee-c08b-4c4f-bec3-cbe1e188b998',
        'side': 'ask',
        'ord_type': 'market',
        'state': 'done',
        'market': 'KRW-BTC',
        'created_at': '2022-09-28T14:51:58+09:00',
        'volume': '0.000367',
        'remaining_volume': '0',
        'reserved_fee': '0',
        'remaining_fee': '0',
        'paid_fee': '4.990833',
        'locked': '0',
        'executed_volume': '0.000367',
        'trades_count': 1,
        'trades': [{'market': 'KRW-BTC',
        'uuid': '987d734c-a0d8-4043-b34f-55d36ba96bfb',
        'price': '27198000',
        'volume': '0.000367',
        'funds': '9981.666',
        'trend': 'down',
        'created_at': '2022-09-28T14:51:57+09:00',
        'side': 'ask'}]}
        """
        params = {'uuid': uuid}
        query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
        jwt_token = self._create_jwt_token(self.ACCESS_KEY, self.SECRET_KEY, query_string)

        authorization = 'Bearer {}'.format(jwt_token)
        headers = {'Authorization': authorization}

        order_one = self._request_get(self.SERVER_URL + "/v1/order", params=params, headers=headers)
        return order_one


    def get_trade_tick(self):
        """ 
        최근 체결 정보 조회 
        """
        querystring = {"market": self.market, "count": "1"}
        return self._request_get(self.SERVER_URL + "/v1/trades/ticks/", params=querystring)

    
    @staticmethod
    def _create_limit_order_query(market, is_buy, price, volume):
        """ 
        지정가 주문 쿼리 생성 
        """
        query = {
            "market": market,
            "side": "bid" if is_buy else "ask",
            "volume": str(volume),
            "price": str(price),
            "ord_type": "limit",
            }
        return urlencode(query).encode()

    @staticmethod
    def _create_market_price_order_query(market, price=None, volume=None):
        """ 
        시장가 주문 쿼리 생성 
        """
        query = {"market": market}

        # 시장가 매도 주문
        if price is None and volume is not None:
            query["side"] = "ask"
            query["volume"] = str(volume)
            query["ord_type"] = "market"
        # 시장가 매수 주문
        elif price is not None and volume is None:
            query["side"] = "bid"
            query["price"] = str(price)
            query["ord_type"] = "price"
        
        else: 
            return None
        return urlencode(query).encode()
        
    @staticmethod
    def _create_jwt_token(a_key, s_key, query_string=None):
        """
        JWT 토큰 생성 
        """
        payload={"access_key": a_key, "nonce": str(uuid.uuid4())}

        if query_string is not None:
            msg = hashlib.sha512()
            msg.update(query_string)
            query_hash = msg.hexdigest()
            payload["query_hash"] = query_hash
            payload["query_hash_alg"] = "SHA512"
        return jwt.encode(payload, s_key)

    def _request_get(self, url, headers=None, params=None):
        try:
            if params is not None:
                response = requests.get(url, params=params, headers=headers)
            else:
                response = requests.get(url, headers=headers)
            
            response.raise_for_status()
            result = response.json()
        
        except ValueError:
            self.logger.error("Invalid data from server")
            return None
        except requests.exceptions.HTTPError as msg:
            self.logger.error(msg)
            return None
        except requests.exceptions.RequestException as msg:
            self.logger.error(msg)
            return None
        return result
    
    def _optimize_price(self, price, is_buy):
        latest = self.get_trade_tick()

        if latest is None:
            return price
        
        if (is_buy is True and latest[0]["trade_price"] < price) or (
            is_buy is False and latest[0]["trade_price"] > price):
            return latest[0]["trade_price"]
        return price

