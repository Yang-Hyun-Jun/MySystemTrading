import copy
import os
import matplotlib
import pandas as pd

from datetime import datetime
from .log_manager import LogManager


class Analyzer:
    """
    거래 요청, 결과 정보를 저장하고 분석하는 클래스
    
    Attributes:
        request_list: 거래 요청 목록
        result_list: 거래 결과 데이터 목록
        info_list: 종목 주가 데이터 목록
        asset_info_list: 특정 시점에 기록된 자산 데이터(잔고, 보유 자산, 종목별 딕셔너리) 목록
        score_list: 특정 시점에 기록된 수익률 데이터 목록
        get_asset_info_func: 현재 자산 정보를 요청하기 위한 콜백

    kind: 제공 정보 종류
    0: 거래 데이터
    1: 매매 요청 정보
    2: 매매 결과 정보
    3: 수익률 정보
    """

    ISO_DATEFORMAT = "%Y-%m-%dT%H:%M:%S"
    OUTPUT_FOLDER = "output/"
    RECORD_INTERVAL = 60
    SMA = (5, 20)

    def __init__(self):
        self.request_list = []
        self.result_list = []
        self.info_list = []
        self.asset_info_list = []
        self.score_list = []
        
        self.get_asset_info_func = None
        self.logger = LogManager.get_logger(__class__.__name__)

        # 결과 저장 폴더 생성 
        if os.path.isdir("output") is False:
            print("create output folder")
            os.makedirs("output")
    
    def initialize(self, get_asset_info_func):
        """
        콜백 함수를 입력으로 받아서 초기화 한다. 
        """
        self.get_asset_info_func = get_asset_info_func

    def put_trading_info(self, info):
        """
        거래 데이터를 저장한다. 
        """

        new = copy.deepcopy(info)
        new["kind"] = 0
        self.info_list.append(new)
        self.make_periodic_record() 

    def put_requests(self, requests):
        """
        거래 요청 정보를 저장한다. 
        """

        for request in requests:
            new = copy.deepcopy(request)

            if request["type"] == "cancel":
                new["price"] = 0
                new["amount"] = 0
            else:
                # 매수 및 매도 주문 중 주문 가격 및 수량이 0 이하면 저장 하지 않는다. 
                if float(request["price"]) <=0 or float(request["amount"]) <= 0:
                    continue

                new["price"] = float(new["price"])
                new["amount"] = float(new["amount"])
            new["kind"] = 1
            self.request_list.append(new)

    def put_result(self, result):
        """
        거래 결과 정보를 저장한다. 
        거래 결과 정보를 저장 할때는 자산 상황이 바뀌었을 수 있으므로 update asset info
        """

        try:
            if float(result["price"]) <=0 or float(result["amount"]) <= 0:
                return
        except KeyError:
            self.logger.warning("Invalid result")
            return
        
        new = copy.deepcopy(result)
        new["price"] = float(new["price"])
        new['amount'] = float(new['amount'])
        new['kind'] = 2
        self.result_list.append(new)
        self.update_asset_info() 

    def update_asset_info(self):
        """
        자산 정보를 저장하고 이를 기반으로 수익률 생성

        returns:
        {
            balance: 계좌 잔고
            asset: 보유 자산 (평단가, 수량) 딕셔너리
            quote: 종목별 현재가 딕셔너리
        }
        """
        if self.get_asset_info_func is None:
            self.logger.warning("get_asset_info_func is None")
            return
        
        asset_info = self.get_asset_info_func()
        new = copy.deepcopy(asset_info)
        new["balance"] = float(new["balance"])
        self.asset_info_list.append(new)
        self.make_score_record(new)

    def make_start_point(self):
        """
        시작 시점 거래 정보를 기록한다. 
        """
        self.request_list = []
        self.result_list = []
        self.asset_info_list = []
        self.update_asset_info()

    def make_periodic_record(self):
        """
        주기적으로 수익률을 기록한다. 
        """
        now = datetime.now()
        last = datetime.strptime(self.asset_info_list[-1]["date_time"], self.ISO_DATEFORMAT)
        delta = now - last

        if delta.total_seconds() > self.RECORD_INTERVAL:
            self.update_asset_info()

    def make_score_record(self, new_info):
        """
        new_info(자산 정보)를 받아 수익률 기록을 생성한다. 

        score_record:
                balance: 계좌 현금 잔고
                cumulative_return: 기준 시점부터 누적 수익률
                price_change_ratio: 기준 시점부터 보유 종목별 가격 변동률 딕셔너리
                asset: 자산 정보 튜플 리스트 (종목, 평균 가격, 현재 가격, 수량, 수익률(소숫점3자리))
                date_time: 데이터 생성 시간, 시뮬레이션 모드에서는 데이터 시간
                kind: 3, 보고서를 위한 데이터 종류
        """

        try:
            start_total = self.__get_start_property_value()
            start_quote = self.asset_info_list[0]["quote"]
            current_total = float(new_info["balance"])
            current_quote = new_info["quote"]
            cumulative_return = 0
            new_asset_info_list = []
            price_change_ratio = {}
            self.logger.debug(f"make score record new_info {new_info}")

            # 종목별 수익률 계산
            for name, item in new_info["asset"].items():
                item_yield = 0 # 수익률
                now_amount = float(item[1])
                now_buy_avg = float(item[0])
                now_price = float(current_quote[name])
                current_total += now_amount * now_price
                item_price_diff = now_price - now_buy_avg

                if item_price_diff !=0 and now_buy_avg != 0:
                    item_yield = (now_price - now_buy_avg) / now_buy_avg * 100
                    item_yield = round(item_yield, 3)

                self.logger.debug(
                    f"{name}| yield record: {item_yield} | buy avg: {now_buy_avg} | price: {now_price} | amount: {now_amount}")

                # 종목별 가격 변동률 계산 
                new_asset_info_list.append((name, now_buy_avg, now_price, now_amount, item_yield))
                start_price = start_quote[name]
                price_change_ratio[name] = 0
                price_diff = now_price - start_price
                
                if price_diff !=0:
                    price_change_ratio[name] = price_diff / start_price * 100
                    price_change_ratio[name] = round(price_change_ratio[name], 3)
                
                self.logger.debug(
                    f"price change ratio {start_price} -> {now_price}, {price_change_ratio[name]}")

            # 누적 수익률 계산
            total_diff = current_total - start_total
            if total_diff != 0:
                cumulative_return = (current_total - start_total) / start_total * 100
                cumulative_return = round(cumulative_return, 3)
            
            self.logger.info(
                f"cumulative return {start_total} -> {current_total}, {cumulative_return}")

            self.score_list.append(
                {
                    "balance": float(new_info["balance"]),
                    "cumulative_return": cumulative_return,
                    "price_change_ratio": price_change_ratio,
                    "asset": new_asset_info_list,
                    "date_time": new_info["date_time"],
                    "kind": 3
                })

        except (IndexError, AttributeError) as msg:
            self.logger.error(f"making score record fail {msg}")

    def get_return_report(self, graph_filename=None):
        """
        현 시점 기준 간단한 수익률 보고서를 제공

        returns:
        (
            start_budget: 시작 자산
            final_balance: 최종 자산
            cumulative_return: 기준 시점부터 누적 수익률
            price_change_ratio: 기준 시점부터 보유 종목별 가격 변동률 딕셔너리
            graph: 그래프 파일 경로

        )
        """
        self.update_asset_info()

        try:
            graph = None
            start_value = self.__get_start_property_value()
            last_value = self.__get_last_property_value()
            last_return = self.score_list[-1]["cumulative_return"]
            change_ratio = self.score_list[-1]["price_change_ratio"]

            # if graph_filename is not None:
            #     graph = self.__draw_graph(graph_filename, is_fullpath=True)

            summary = (start_value, last_value, last_return, change_ratio, graph)
            
            self.logger.info("Return Report ===================================")
            self.logger.info(f"Property                 {start_value:10} -> {last_value:10}")
            self.logger.info(f"Gap                      {last_value - start_value:10}")
            self.logger.info(f"Cumulative return        {last_return:10}")
            self.logger.info(f"Price change ratio       {change_ratio}")
            return summary  

        except (IndexError, AttributeError):
            self.logger.error("get return report FAIL")



    def get_trading_results(self):
        """ 거래 결과 목록을 반환 """
        return self.result_list

    def __get_start_property_value(self):
        return round(self.__get_property_total_value(0))
    
    def __get_last_property_value(self):
        return round(self.__get_property_total_value(-1))
    
    def __get_property_total_value(self, index):
        """
        특정 시점(index) 에서 보유 자산 총액 계산
        현재 잔고 + sum (종목 현재가 * 종목 보유 수량)
        """
        total = float(self.asset_info_list[index]["balance"])
        quote = self.asset_info_list[index]["quote"]
        for name, item in self.asset_info_list[index]["asset"].items():
            stock_now_price = float(quote[name])
            stock_now_amount = float(item[1])
            total += stock_now_amount * stock_now_price
        return total