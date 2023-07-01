import time 
import threading

from datetime import datetime
from .log_manager import LogManager
from .worker import Worker


class Operator:
    """
    전체 시스템의 운영을 담당하는 클래스
    이 모듈은 각 모듈을 컨트롤하여 전체 시스템을 운영한다. 

    Attributes:
        data_provider: 사용될 DataProvider 인스턴스
        strategy: 사용될 Strategy 인스턴스
        trader: 사용될 Trader 인스턴스
        analyzer: 거래 분석용 Analyzer 인스턴스
    """

    ISO_DATEFORMAT = "%Y-%m-%dT%H:%M:%S"
    OUTPUT_FOLDER = "output/"

    def __init__(self):
        self.logger = LogManager.get_logger(__class__.__name__)
        self.data_provider = None
        self.strategy = None
        self.trader = None
        self.analyzer = None

        self.state = None 
        self.last_report = None

    def initialize(self, data_provider, strategy, trader, analyzer, budget):
        """
        운영에 필요한 모듈과 정보를 설정 및 각 모듈 초기화 수행
        """

        # 상태 변수 체크
        if self.state is not None: 
            return

        self.data_provider = data_provider
        self.strategy = strategy
        self.trader = trader
        self.analyzer = analyzer
        self.state = "ready"
        self.trader.initialize(budget)
        self.strategy.initialize(budget)
        self.analyzer.initialize(trader.get_account_info)

    def start(self):
        """
        자동 거래를 시작한다. 
        """
        if self.state != "ready":
            return False
        
        self.logger.info("====== Start Operating ======")
        self.state = "running" 
        self.analyzer.make_start_point()
        self.thread = threading.Thread(target=self._execute_trading, daemon=True)
        self.thread.start()

    def stop(self):
        """
        거래를 중단한다. 
        """
        if self.state != "running":
            return

        self.logger.info("===== Stop operating =====")
        self.state = "terminating"
        
        self.trader.worker.stop()
        self.trader.cancel_all_requests()
        trading_info = self.data_provider.get_info()
        self.analyzer.put_trading_info(trading_info)
        # self.last_report = self.analyzer.create_report(tag=self.tag)
        self.thread.join()
        self.state = "ready"

    def _execute_trading(self):
        """
        자동 거래를 실행한다. 
        """
        self.logger.debug("========= trading is started =========")

        # 결과 콜백 함수 
        def send_request_callback(result):
            print(result)
            if result["state"] == "done" and result["type"] == "buy":
                self.strategy.hold = True
                self.strategy.last_buy_id = result["request"]["id"]
            if result["state"] == "done" and result["type"] == "sell":
                self.strategy.hold = False
                self.strategy.last_buy_id = None
 
            self.strategy.update_result(result)
            if result["state"] != "requested":
                self.analyzer.put_result(result)
        
        # 트레이딩
        try:
            while self.state != "terminating":

                # 종목 데이터 전달 
                trading_info = self.data_provider.get_info()    
                self.strategy.update_trading_info(trading_info)
                self.analyzer.put_trading_info(trading_info)

                # 시그널 후 주문 생성
                target_request = self.strategy.get_request()
                if target_request:

                    print(target_request)
                    self.logger.debug(f"Trading Signal is made with info : {trading_info}")
                    self.logger.debug(f"Trading Request is made : {target_request}")

                    self.analyzer.put_requests(target_request)
                    self.trader.send_request(target_request, send_request_callback)
                    
                time.sleep(1/10)

        except (AttributeError, TypeError) as msg:
            self.logger.error(f"excuting fail {msg}")
        return True

    def get_trading_results(self):
        """현재까지 거래 결과 기록을 반환한다"""
        return self.analyzer.get_trading_results()