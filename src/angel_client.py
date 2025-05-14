import pyotp
from SmartApi import SmartConnect
from logzero import logger
from config import login_api_key, login_username, login_pwd, login_token
from src.utils import retry_on_network_error


class AngelOneClient:
    def __init__(self,logger):
        self.api_key = login_api_key
        self.username = login_username
        self.password = login_pwd
        self.token = login_token
        self.smartApi = None
        self.logger = logger
        
    @retry_on_network_error()
    def login(self):
        try:
            self.smartApi = SmartConnect(api_key=self.api_key, timeout=60)

            # Generate TOTP
            totp = pyotp.TOTP(self.token).now()

            # Login
            session_data = self.smartApi.generateSession(self.username, self.password, totp)
            if not session_data.get('status'):
                raise Exception ("Login Failed Please re-run the workflow again")

            # Get tokens and profile
            jwt_token = session_data['data']['jwtToken']
            refresh_token = session_data['data']['refreshToken']

            self.smartApi.getfeedToken()
            profile = self.smartApi.getProfile(refresh_token)

            if profile.get('status'):
                user_name = profile['data'].get('name', 'Unknown User')
                self.logger.write(f"🎉 Logged in successfully as {user_name}")
            else:
                logger.warning("Failed to fetch profile details after login.")

            return self.smartApi

        except Exception as e:
            raise Exception (f"Error In Angle Login method: {e}")
