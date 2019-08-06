import logging


def init_log():
    logger = logging.getLogger('netbox_agent')
    logger.setLevel(logging.DEBUG)

    logger_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

    fh = logging.FileHandler('netbox.log')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logger_formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logger_formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = init_log()
