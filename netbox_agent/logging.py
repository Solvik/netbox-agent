import logging

from netbox_agent.config import LOG_LEVEL


logger = logging.getLogger()

if LOG_LEVEL == 'debug':
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
