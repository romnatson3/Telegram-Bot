import logging
import sys


#LOG_FILE = '/opt/telegram/server.log'


logger = logging.getLogger(__name__)
#ch = logging.FileHandler(LOG_FILE)
sh = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s] %(message)s')
logger.setLevel(logging.DEBUG)
#ch.setFormatter(formatter)
sh.setFormatter(formatter)
#logger.addHandler(ch)
logger.addHandler(sh)
