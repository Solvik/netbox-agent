import logging

from netbox_agent.config import config

logger = logging.getLogger()

if config.log_level == 'debug':
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
