import requests
import json
import base64
import datetime
import gzip
import StringIO

def authenticate(func):
    def authenticate_and_call(*args):
        if not args[0].is_access_token_valid():
            args[0].access_token = args[0].fetch_access_token()
        return func(*args)
    return authenticate_and_call


class APIManager(object):
    def __init__(self, client_id, client_secret, hostname, compression_enabled=True):
        """ Initializes the API Manager which is responsible for authenticating every request.

        :param client_id: the client id generated by mnubo
        :param client_secret: the client secret generated by mnubo
        :param hostname: the hostname to send the requests (sandbox or production)
        :param compression: if True, enable compression in the HTTP requests (default: True)
        """

        if not client_id:
            raise ValueError("client_id cannot be null or empty.")

        if not client_secret:
            raise ValueError("client_secret cannot be null or empty.")


        try:
            requests.head(hostname)
        except requests.exceptions.ConnectionError:
            raise ValueError("Host at {} is not reachable".format(hostname))

        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__hostname = hostname
        self.__session = requests.Session()

        self.compression_enabled = compression_enabled
        self.access_token = self.fetch_access_token()

    def fetch_access_token(self):
        """ Requests the access token necessary to communicate with the mnubo plateform
        """

        requested_at = datetime.datetime.now()

        r = self.__session.post(self.get_auth_url(), headers=self.get_token_authorization_header())
        json_response = r.json()
        r.raise_for_status()

        return {
            'access_token': json_response['access_token'],
            'expires_in': datetime.timedelta(0, json_response['expires_in']),
            'requested_at': requested_at
        }

    def is_access_token_valid(self):
        """ Validates if the token is still valid

        :return: True of the token is still valid, False if it is expired
        """

        return (self.access_token['requested_at'] + self.access_token['expires_in']) > datetime.datetime.now()

    def get_token_authorization_header(self):
        """ Generates the authorization header used while requesting an access token
        """

        encoded = base64.b64encode("{0}:{1}".format(self.__client_id, self.__client_secret))
        return {'content-type': 'application/x-www-form-urlencoded', 'Authorization': "Basic {}".format(encoded)}

    def get_authorization_header(self):
        """ Generates the authorization header used to access resources via mnubo's API
        """
        return {'content-type': 'application/json', 'Authorization': 'Bearer ' + self.access_token['access_token']}

    def get_api_url(self):
        """ Generates the general API url
        """

        return self.__hostname + '/api/v3/'

    def get_auth_url(self):
        """ Generates the url to fetch the access token
        """

        return self.__hostname + '/oauth/token?grant_type=client_credentials&scope=ALL'

    def validate_response(self, response):
        """ Raises a ValueError instead of a HTTPError in case of a 400 or 409

        This allows easier development and consistency with client-side checks
        """
        if response.status_code in (400, 409):
            raise ValueError(response.content)
        response.raise_for_status()

    def _gzip_encode(self, data):
        out = StringIO.StringIO()
        f = gzip.GzipFile(mode='wb', fileobj=out)
        f.write(data)
        f.close()
        return out.getvalue()

    @authenticate
    def get(self, route, params={}):
        """ Build and send a get request authenticated

        :param route: JSON body to be included in the HTTP request
        :param params: (optional) additional parameters for the request string
        """

        url = self.get_api_url() + route
        headers = self.get_authorization_header()

        response = self.__session.get(url, params=params, headers=headers)
        self.validate_response(response)

        return response

    @authenticate
    def post(self, route, body={}):
        """ Build and send a post request authenticated

        :param route: resource path (not including the API root)
        :param body: JSON body to be included in the HTTP request
        """

        url = self.get_api_url() + route
        headers = self.get_authorization_header()

        if self.compression_enabled:
            headers.update({"content-encoding": "gzip"})
            encoded = self._gzip_encode(json.dumps(body))
            response = self.__session.post(url, data=encoded, headers=headers)
        else:
            response = self.__session.post(url, json=body, headers=headers)

        self.validate_response(response)

        return response

    @authenticate
    def put(self, route, body={}):
        """ Build and send an authenticated put request

        :param route: resource path (not including the API root)
        :param body: JSON body to be included in the HTTP request
        """

        url = self.get_api_url() + route
        headers = self.get_authorization_header()

        if self.compression_enabled:
            headers.update({"content-encoding": "gzip"})
            encoded = self._gzip_encode(json.dumps(body))
            response = self.__session.put(url, data=encoded, headers=headers)
        else:
            response = self.__session.put(url, json=body, headers=headers)

        self.validate_response(response)

        return response

    @authenticate
    def delete(self, route):
        """ Build and send a delete request authenticated

        :param route: which resource to access via the REST API
        """

        url = self.get_api_url() + route
        headers = self.get_authorization_header()

        response = self.__session.delete(url, headers=headers)
        self.validate_response(response)

        return response
