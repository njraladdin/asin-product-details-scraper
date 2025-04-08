from queue import Queue
import threading
from .scraper import AmazonScraper
from .logger import setup_logger
from concurrent.futures import ThreadPoolExecutor
from .utils import load_config
import time

class SessionPool:
    def __init__(self):
        self.logger = setup_logger('SessionPool')
        self.config = load_config()
        self.sessions = Queue()
        self.lock = threading.Lock()
        
        # Initialize pool with a few sessions
        self.initialize_pool()
    
    def initialize_pool(self):
        """Initialize the pool with a few sessions"""
        try:
            # Create initial sessions
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i in range(5):  # Start with 5 sessions
                    future = executor.submit(self._initialize_single_session, i)
                    futures.append(future)
                
                # Wait for all sessions to initialize
                for future in futures:
                    future.result()
                    
            self.logger.info(f"Session pool initialized with {self.sessions.qsize()} sessions")
        except Exception as e:
            self.logger.error(f"Failed to initialize session pool: {str(e)}")
    
    def _initialize_single_session(self, index):
        """Initialize a single session"""
        try:
            scraper = AmazonScraper()
            if scraper.initialize_session():
                self.sessions.put(scraper)
                self.logger.info(f"Successfully initialized session {index + 1}")
                return True
            else:
                self.logger.error(f"Failed to initialize session {index + 1}")
                return False
        except Exception as e:
            self.logger.error(f"Error initializing session {index + 1}: {str(e)}")
            return False
    
    def get_session(self):
        """Get a session from the pool"""
        try:
            return self.sessions.get(timeout=10)  # 10 second timeout
        except:
            self.logger.warning("No sessions available, creating new one")
            return self._create_new_session()
    
    def _create_new_session(self):
        """Create a new session if pool is empty"""
        scraper = AmazonScraper()
        if scraper.initialize_session():
            return scraper
        return None
    
    def return_session(self, session):
        """Return a session to the pool"""
        if session and session.is_initialized:
            self.sessions.put(session)
    
    def get_pool_size(self):
        """Get current number of available sessions"""
        return self.sessions.qsize()

def test_session_pool():
    """Test function to initialize a single session"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    pool = SessionPool()
    
    print("\n=== Testing Session Pool ===")
    print(f"Initial pool size: {pool.get_pool_size()}")
    
    # Test getting and returning a session
    session = pool.get_session()
    if session:
        print("Successfully got a session")
        pool.return_session(session)
        print("Successfully returned the session")
    else:
        print("Failed to get a session")
    
    print(f"Final pool size: {pool.get_pool_size()}")
    print("\n=== Test completed ===")

if __name__ == "__main__":
    test_session_pool() 