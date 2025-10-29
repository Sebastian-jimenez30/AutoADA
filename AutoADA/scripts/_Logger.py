import logging
import sys


def initlog(file, append=False):
    # CONFIGURACION DE LOGGER 
    logformat = logging.Formatter('%(levelname)-8s -  %(asctime)s  -  %(message)s')  # Ajuste de longitud del nivel de log
    logformatconsole = logging.Formatter('%(levelname)-8s -  %(message)s')

    # Definicion de log en archivo
    logger = logging.getLogger("loger2")
    logger.setLevel(logging.DEBUG) 

    # Definicion de log en consola
    logger_console = logging.getLogger("logger")
    logger_console.setLevel(logging.DEBUG) 

    # Defincion de manejadores de logs
    hand_console = logging.StreamHandler(sys.stdout)
    hand_console.setFormatter(logformatconsole)
    mode = 'a' if append else 'w'
    hand_file = logging.FileHandler(filename=file, mode=mode)
    hand_file.setFormatter(logformat)

    # Limpiar handlers previos para evitar duplicados
    if logger.hasHandlers():
        logger.handlers.clear()
    if logger_console.hasHandlers():
        logger_console.handlers.clear()

    # Agregando manejadores a los logger
    logger.addHandler(hand_file)
    logger_console.addHandler(hand_console)

    return logger, logger_console

class write_log():
    def __init__(self):
        pass      
    def log_all(self, level, msjs, logger_console, logger):
        self.msjs = msjs
        self.level = level
        self.logger_console = logger_console
        self.logger = logger

        msjs_with_level = f"{self.msjs}"  

        if self.level == 'info':            
            logger_console.info(msjs_with_level) 
            logger.info(msjs_with_level) 
        elif self.level == 'debug':            
            logger_console.debug(msjs_with_level)
            logger.debug(msjs_with_level) 
        elif self.level == 'warning':            
            logger_console.warning(msjs_with_level)
            logger.warning(msjs_with_level) 
        elif self.level == 'error':            
            logger_console.error(msjs_with_level)
            logger.error(msjs_with_level) 
        elif self.level == 'critical':            
            logger_console.critical(msjs_with_level)
            logger.critical(msjs_with_level) 

    def log_consol(self, level, msjs, logger_console):
        self.msjs = msjs
        self.level = level 
        self.logger_console = logger_console
        msjs_with_level = f"{self.level.upper()}: {self.msjs}"  
        if self.level == 'info':            
            logger_console.info(msjs_with_level) 
        elif self.level == 'debug':            
            logger_console.debug(msjs_with_level)
        elif self.level == 'warning':            
            logger_console.warning(msjs_with_level)
        elif self.level == 'error':            
            logger_console.error(msjs_with_level)
        elif self.level == 'critical':            
            logger_console.critical(msjs_with_level)

    def log_files(self, level, msjs, logger):        
        self.msjs = msjs
        self.level = level
        self.logger = logger 
        msjs_with_level = f"{self.level.upper()}: {self.msjs}"  
        if self.level == 'info':            
            logger.info(msjs_with_level) 
        elif self.level == 'debug':            
            logger.debug(msjs_with_level)
        elif self.level == 'warning':            
            logger.warning(msjs_with_level)
        elif self.level == 'error':            
            logger.error(msjs_with_level)
        elif self.level == 'critical':            
            logger.critical(msjs_with_level)
