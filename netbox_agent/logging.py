import logging
import sys

from netbox_agent.config import config

logger = logging.getLogger()

#match support only from python 3.10, our instances still have instance run python 3.9
# match config.log_level.lower():
#     case 'debug':
#         logger.setLevel(logging.DEBUG)
#     case 'info':
#         logger.setLevel(logging.INFO)
#     case 'warning':
#          logger.setLevel(logging.WARNING)
#     case 'error':
#          logger.setLevel(logging.ERROR)
if config.log_level.lower() == 'debug':
    logger.setLevel(logging.DEBUG)
elif config.log_level.lower() == 'warning':
    logger.setLevel(logging.WARNING)
elif config.log_level.lower() == 'error':
    logger.setLevel(logging.ERROR)
else:
    logger.setLevel(logging.INFO)
# logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S',level=logging.ERROR)