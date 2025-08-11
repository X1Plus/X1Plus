"""
RTSP Module errors
"""


class RTSPError(Exception):
    """Base RTSP error"""
    type = 'unknown'

    def reason(self) -> dict:
        """
        Structured data for RTSP errors, including type,
        and potentially type-specific extra values.
        """
        return {
            'type': self.type
        }


class RTSPResponseError(RTSPError):
    """
    Error upon response. If the response is provided, will be printed
    """
    type = 'response'

    def __init__(self, msg, response=None):
        self.response = response
        super().__init__(msg, self.reason())

    def __str__(self):
        msg = f'REASON: {super().__str__()}'
        if self.response:
            msg += f'\nRESPONSE: {self.response}'
            if self.response.content:
                msg += f'\nCONTENT: {self.response.content}'
        return msg

    def reason(self):
        r = super().reason()
        if self.response:
            r['status'] = self.response.status
            r['message'] = self.response.status_msg
        return r


class RTSPConnectionError(RTSPError):
    """
    RTSP connection error
    """
    type = 'connection'


class RTSPTimeoutError(RTSPError):
    """
    A request timed out (no answer we could understand)
    """
    type = 'timeout'
