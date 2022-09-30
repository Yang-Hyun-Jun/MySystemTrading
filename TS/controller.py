import uuid
import jwt
import requests
import os
import threading

from dotenv import load_dotenv
from .log_manager import LogManager
from .analyzer import Analyzer
from .upbit_trader import UpbitTrader
from .upbit_data_provider import UpbitDataProvider
from .strategy_bnh import StrategyBuyAndHold
from .strategy_bns import StrategyBuyAndSell
from .operator import Operator

load_dotenv(verbose=True)

class Controller:
    """
    TS controller 
    TS 운영 인터페이스
    Operator를 사용해서 시스템을 컨트롤하는 모듈
    """

    MAIN_STATEMENT = "명령어를 입력하세요. (h: 도움말): "
    
    def __init__(self):
        self.logger = LogManager.get_logger(__class__.__name__)
        self.terminating = False
        self.operator = Operator()
        self.budget = None
        self.is_initialized = False
        self.command_list = []
        self.create_command()
        LogManager.set_stream_level(30)


    def create_command(self):
        """ 명령어 정보를 생성한다. """
        self.command_list = [
            {
                "guide": "{0:15} 도움말 출력".format("h, help"),
                "cmd": ["help"],
                "short": ["h"],
                "need_value": False,
                "action": self.print_help,
            },
            {
                "guide": "{0:15} 자동 거래 시작".format("r, run"),
                "cmd": ["run"],
                "short": ["r"],
                "need_value": False,
                "action": self.start,
            },
            {
                "guide": "{0:15} 자동 거래 중지".format("s, stop"),
                "cmd": ["stop"],
                "short": ["s"],
                "need_value": False,
                "action": self.stop,
            },
            {
                "guide": "{0:15} 프로그램 종료".format("t, terminate"),
                "cmd": ["terminate"],
                "short": ["t"],
                "need_value": False,
                "action": self.terminate,
            },
            {
                "guide": "{0:15} 정보 조회".format("q, query"),
                "cmd": ["query"],
                "short": ["q"],
                "need_value": True,
                "value_guide": "무엇을 조회할까요? (Ex 1.state, 2.score, 3.result, 4.account info) :",
                "action_with_value": self._on_query_command,
            },
        ]

    def main(self):
        """ main 함수 """
        budgetible = float(self._get_budgitable())
        self.budget = input(f"시드머니 값 입력 (현재 거래 가능 금액: {budgetible}) :")           
        self.budget = float(self.budget) 
        self.logger.debug(f"Start trading seed: {self.budget}")
        
        assert self.budget <= budgetible

        self.operator.initialize(
            UpbitDataProvider(),
            StrategyBuyAndSell(),
            UpbitTrader(),
            Analyzer(),
            budget=self.budget)

        print("=============== TS is intialized ===============")
        print(f"Start Seed Money:{self.budget}")
        print("================================================")

        while not self.terminating:
            try:
                key = input(self.MAIN_STATEMENT)
                self.logger.debug(f"Execute command {key}")
                self._on_command(key)
            except EOFError:
                break

    def print_help(self):
        """ 가이드 문구 출력 """
        print("명령어 목록 ==============")
        for item in self.command_list:
            print(item["guide"])
    
    def start(self):
        """ 프로그램 시작, 재시작 """
        self.operator.start() 

    def stop(self):
        """ 프로그램 중지 """
        self.operator.stop()
    
    def terminate(self):
        """ 프로그램 종료 """
        print("프로그램 종료 중 ....")
        self.stop()
        self.terminating = True
        print("Good Bye~")

    def _get_score(self):
        """ Operator로 현재 수익률 조회 """
        print(self.operator.analyzer.score_list[-1])

        # # callback
        # def print_score_and_main_statement(score):
        #     print("current score ==========")
        #     print(score)        
        # self.operator.get_score(print_score_and_main_statement)
    
    def _on_command(self, key):
        """ 커맨드 처리를 담당 """
        value = None
        for cmd in self.command_list:
            if key.lower() in cmd["cmd"] or key.lower() in cmd["short"]:
                if cmd["need_value"]:
                    value = input(cmd["value_guide"])
                    print(f"{cmd['cmd'][0].upper()} - {value.upper()} 명령어를 실행합니다.")
                    cmd["action_with_value"](value)
                else:
                    print(f"{cmd['cmd'][0].upper()} 명령어를 실행합니다.")
                    cmd["action"]()
                return
        print("잘못된 명령어가 입력 되었습니다.")

    def _on_query_command(self, value):
        """ 가이드 문구 출력 """
        key = value.lower()
        if key in ["state", "1"]:
            print(f"현재 상태: {self.operator.state}")
        elif key in ["score", "2"]:
            self._get_score()
        elif key in ["result", "3"]:
            print(self.operator.get_trading_results())
        elif key in ["result", "4"]:
            print(self.operator.trader.get_account_info())

    def _get_budgitable(self):
        ACCESS_KEY = os.environ.get("UPBIT_OPEN_API_ACCESS_KEY", "upbit_access_key")
        SECRET_KEY = os.environ.get("UPBIT_OPEN_API_SECRET_KEY", "upbit_secret_key")
        SERVER_URL = os.environ.get("UPBIT_OPEN_API_SERVER_URL", "upbit_server_url")

        payload = {
            'access_key': ACCESS_KEY,
            'nonce': str(uuid.uuid4())}

        jwt_token = jwt.encode(payload, SECRET_KEY)
        authorization = 'Bearer {}'.format(jwt_token)
        headers = {'Authorization': authorization}

        try:
            res = requests.get(SERVER_URL + '/v1/accounts', headers=headers)
            res.raise_for_status()
            return res.json()[0]["balance"]

        except requests.exceptions.HTTPError as msg:
            self.logger.error(msg)
            return None
        except requests.exceptions.RequestException as msg:
            self.logger.error(msg)
            return None
        


