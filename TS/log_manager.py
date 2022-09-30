import logging
from logging.handlers import RotatingFileHandler


class LogManager:
    """ 
    File Handler와 포맷 설정,
    Stream Handler와 포맷 설정 하여
    Logger 인스턴스를 생성하는 클래스
    """

    # 파일 핸들러 생성 
    file_formatter = logging.Formatter(
        fmt = "%(asctime)s %(levelname)5.5s %(name)20.20s %(lineno)5d - %(message)s"
    )

    file_handler = RotatingFileHandler(filename="system.log", maxBytes=1000000, backupCount=10)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # 스트림 핸들러 설정
    stream_formatter = logging.Formatter(
        fmt = "%(asctime)s %(levelname)5.5s %(name)20.20s - %(message)s"
    )
    
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(stream_formatter)
    logger_map = {} 


    @classmethod
    def get_logger(cls, name):
        """
        Handler들 붙인 후, Logger 인스턴스 생성
        """
        logger = logging.getLogger(name)
        
        # 이미 생성된 Logger는 그대로 리턴
        if name in cls.logger_map:
            return logger

        # 처음 생성된 Logger는 Handler 붙이기
        logger.addHandler(cls.file_handler)
        logger.addHandler(cls.stream_handler)
        logger.setLevel(logging.DEBUG)
        
        cls.logger_map[name] = True
        return logger


    @classmethod
    def set_stream_level(cls, level):
        """
        Stream Handler Logging Level 설정
        """
        cls.stream_handler.setLevel(level)