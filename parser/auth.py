from apiclient import errors
import httplib2
import logging
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import Credentials
from oauth2client.client import FlowExchangeError
from apiclient.discovery import build

CLIENTSECRETS_LOCATION = 'app-secret.json'
REDIRECT_URI = 'http://ppkt.eu'
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    # Add other requested scopes.
]

class GetCredentialsException(Exception):
  """Error raised when an error occurred while retrieving credentials.

  Attributes:
    authorization_url: Authorization URL to redirect the user to in order to
                       request offline access.
  """

  def __init__(self, authorization_url):
    """Construct a GetCredentialsException."""
    self.authorization_url = authorization_url


class CodeExchangeException(GetCredentialsException):
  """Error raised when a code exchange has failed."""


class NoRefreshTokenException(GetCredentialsException):
  """Error raised when no refresh token has been found."""


class NoUserIdException(Exception):
  """Error raised when no user ID could be retrieved."""


class GoogleDriveAuth:
    def get_stored_credentials(self, user_id):
        """Retrieved stored credentials for the provided user ID.

        Args:
            user_id: User's ID.
        Returns:
            Stored oauth2client.client.OAuth2Credentials if found, None otherwise.
        """

        filename = '%s-credentials.json' % (user_id)

        try:
            with open(filename) as f:
                file = f.read()
                credentials = Credentials.new_from_json(file)
            return credentials
        except:
            return None



    def store_credentials(self, user_id, credentials):
        """Store OAuth 2.0 credentials in the application's database.

        This function stores the provided OAuth 2.0 credentials using the user ID as
        key.

        Args:
            user_id: User's ID.
            credentials: OAuth 2.0 credentials to store.
        """
        filename = '%s-credentials.json' % (user_id)
        with open(filename, 'w') as f:
            f.write(credentials.to_json())


    def exchange_code(self, authorization_code):
        """Exchange an authorization code for OAuth 2.0 credentials.

        Args:
            authorization_code: Authorization code to exchange for OAuth 2.0
                                credentials.
        Returns:
            oauth2client.client.OAuth2Credentials instance.
        Raises:
            CodeExchangeException: an error occurred.
        """
        flow = flow_from_clientsecrets(CLIENTSECRETS_LOCATION, ' '.join(SCOPES))
        flow.redirect_uri = REDIRECT_URI
        try:
            credentials = flow.step2_exchange(authorization_code)
            return credentials
        except FlowExchangeError, error:
            logging.error('An error occurred: %s', error)
        raise CodeExchangeException(None)


    def get_user_info(self, credentials):
        """Send a request to the UserInfo API to retrieve the user's information.

        Args:
        credentials: oauth2client.client.OAuth2Credentials instance to authorize the
                     request.
        Returns:
        User information as a dict.
        """
        user_info_service = build(
            serviceName='oauth2', version='v2',
            http=credentials.authorize(httplib2.Http()))
        user_info = None
        try:
            user_info = user_info_service.userinfo().get().execute()
        except errors.HttpError, e:
            logging.error('An error occurred: %s', e)
        if user_info and user_info.get('id'):
            return user_info
        else:
            raise NoUserIdException()


    def get_authorization_url(self, email_address, state):
        """Retrieve the authorization URL.

        Args:
            email_address: User's e-mail address.
            state: State for the authorization URL.
        Returns:
            Authorization URL to redirect the user to.
        """
        flow = flow_from_clientsecrets(CLIENTSECRETS_LOCATION, ' '.join(SCOPES))
        flow.params['access_type'] = 'offline'
        flow.params['approval_prompt'] = 'force'
        flow.params['user_id'] = email_address
        flow.params['state'] = state
        return flow.step1_get_authorize_url(REDIRECT_URI)


    def get_credentials(self, authorization_code, state):
        """Retrieve credentials using the provided authorization code.

        This function exchanges the authorization code for an access token and queries
        the UserInfo API to retrieve the user's e-mail address.
        If a refresh token has been retrieved along with an access token, it is stored
        in the application database using the user's e-mail address as key.
        If no refresh token has been retrieved, the function checks in the application
        database for one and returns it if found or raises a NoRefreshTokenException
        with the authorization URL to redirect the user to.

        Args:
            authorization_code: Authorization code to use to retrieve an access token.
            state: State to set to the authorization URL in case of error.
        Returns:
            oauth2client.client.OAuth2Credentials instance containing an access and
                refresh token.
        Raises:
            CodeExchangeError: Could not exchange the authorization code.
            NoRefreshTokenException: No refresh token could be retrieved from the
                                     available sources.
        """
        email_address = ''
        try:
            credentials = self.exchange_code(authorization_code)
            user_info = self.get_user_info(credentials)
            email_address = user_info.get('email')
            user_id = user_info.get('id')
            if credentials.refresh_token is not None:
                self.store_credentials(user_id, credentials)
                return credentials
            else:
                credentials = self.get_stored_credentials(user_id)
                if credentials and credentials.refresh_token is not None:
                    return credentials
        except CodeExchangeException, error:
            logging.error('An error occurred during code exchange.')
            # Drive apps should try to retrieve the user and credentials for the current
            # session.
            # If none is available, redirect the user to the authorization URL.
            error.authorization_url = self.get_authorization_url(email_address, state)
            raise error
        except NoUserIdException:
            logging.error('No user ID could be retrieved.')
            # No refresh token has been retrieved.
            authorization_url = self.get_authorization_url(email_address, state)
            raise NoRefreshTokenException(authorization_url)


    def build_service(self, credentials):
        """Build a Drive service object.

        Args:
            credentials: OAuth 2.0 credentials.

        Returns:
            Drive service object.
        """
        http = httplib2.Http()
        http = credentials.authorize(http)
        return build('drive', 'v2', http=http)


    def print_file_metadata(self, service, file_id):
        """Print a file's metadata.

        Args:
            service: Drive API service instance.
            file_id: ID of the file to print metadata for.
        """
        try:
            file = service.files().get(fileId=file_id).execute()

            print 'Title: %s' % file.get('title')
            print 'Description: %s' % file.get('description')
            print 'MIME type: %s' % file.get('mimeType')
            print 'Download link: %s' % file.get('downloadUrl')
            print 'Export links: %s' % file.get('exportLinks')
        except errors.HttpError, error:
            if error.resp.status == 401:
                # Credentials have been revoked.
                # TODO: Redirect the user to the authorization URL.
                raise NotImplementedError()
            else:
                print 'Error while retrieving file metadata: %s' % error


    def download_file(self, service, file_id, format='text/plain'):
        """Download file

        Args:
            service: Drive API service instance.
            file_id: ID of the file to download

        Returns:
            Content of file or None if error occured
        """
        file = service.files().get(fileId=file_id).execute()
        download_url = file.get('exportLinks').get(format)

        if download_url:
            resp, content = service._http.request(download_url)

            if resp.status == 200:
                print 'Status: %s' % resp
                return content
            else:
                print 'Error while downloading file: %s' % resp
                return None
        else:
            print 'Format %s not supported' % format
            return None


    def retrieve_all_files(self, service):
        """Retrieve a list of files

        Args:
            service: Drive API service instance.

        Returns:
            List of File resources
        """

        result = []
        page_token = None
        while True:
            try:
                param = {}
                if page_token:
                    param['pageToken'] = page_token
                files = service.files().list(**param).execute()

                result.extend(files['items'])
                page_token = files.get('nextPageToken')
                if not page_token:
                    break
            except errors.HttpError, error:
                print 'An error occurred: %s' % error
                break
        return result