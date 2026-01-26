import logging

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers during Streamlit reruns
if not logger.handlers:
    # File handler
    file_handler = logging.FileHandler('./session.log')
    file_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add the handler
    logger.addHandler(file_handler)
    
#header = """
#    ___         __                        __  _                ___    __      __         
#   /   | __  __/ /_____  ____ ___  ____ _/ /_(_)___  ____ _   /   |  / /___  / /_  ____ _
#  / /| |/ / / / __/ __ \/ __ `__ \/ __ `/ __/ / __ \/ __ `/  / /| | / / __ \/ __ \/ __ `/
# / ___ / /_/ / /_/ /_/ / / / / / / /_/ / /_/ / / / / /_/ /  / ___ |/ / /_/ / / / / /_/ / 
#/_/  |_\__,_/\__/\____/_/ /_/ /_/\__,_/\__/_/_/ /_/\__, /  /_/  |_/_/ .___/_/ /_/\__,_/  
                                                  /____/           /_/                   
#"""
#logger.info(header)

