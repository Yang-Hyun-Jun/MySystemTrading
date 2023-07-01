from concurrent.futures import thread
import time
import pandas as pd
import threading

from TS.upbit_api import UpbitAPI

UPBIT_OPEN_API_ACCESS_KEY= "rJNoEXhipffTC3Ykx5qM4zvAPbcPM6bAv7rZPqKj"
UPBIT_OPEN_API_SECRET_KEY= "PDP4XxFLvatuCbD2gLIUggn68Cix63CNcfPiE2lx"
UPBIT_OPEN_API_SERVER_URL= "https://api.upbit.com"

trade_data = []

api = UpbitAPI(UPBIT_OPEN_API_ACCESS_KEY, UPBIT_OPEN_API_SECRET_KEY, UPBIT_OPEN_API_SERVER_URL, "KRW-BTC")

prior_id = None
file_num = 0

while True:
    print(f"{len(trade_data)}")
    data = api.get_trade_tick()[0]

    if data["sequential_id"] != prior_id:
        trade_data.append(data)

    if len(trade_data) > 10:
        df = pd.DataFrame(trade_data)
        df.to_csv("/Users/mac/Desktop/Trading Machine/trade_data.csv")
        del df
        trade_data = []
        file_num += 1
    
    prior_id = data["sequential_id"]
    time.sleep(1/10)



