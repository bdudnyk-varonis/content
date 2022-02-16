"""Base Integration for Cortex XSOAR (aka Demisto)

This is an empty Integration with some basic structure according
to the code conventions.

MAKE SURE YOU REVIEW/REPLACE ALL THE COMMENTS MARKED AS "TODO"

Developer Documentation: https://xsoar.pan.dev/docs/welcome
Code Conventions: https://xsoar.pan.dev/docs/integrations/code-conventions
Linting: https://xsoar.pan.dev/docs/integrations/linting

This is an empty structure file. Check an example at;
https://github.com/demisto/content/blob/master/Packs/HelloWorld/Integrations/HelloWorld/HelloWorld.py

"""

import demistomock as demisto
from CommonServerPython import *  # noqa # pylint: disable=unused-wildcard-import
from CommonServerUserPython import *  # noqa

import requests
import traceback
from typing import Dict, Any, List
from requests_ntlm import HttpNtlmAuth

# Disable insecure warnings
requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member


''' CONSTANTS '''

THREAT_MODEL_ENUM_ID = 5821
ALERT_STATUSES = {'Open': 1, 'Under Investigation': 2, 'Closed': 3}
STATUSES_TO_RETRY = [304, 405]
ALERT_COLUMNS = [
    'Alert.ID',
    'Alert.Rule.Name',
    'Alert.Time',
    'Alert.Rule.Severity.Name',
    'Alert.Rule.Category.Name',
    'Alert.Location.CountryName',
    'Alert.Location.SubdivisionName',
    'Alert.Status.Name',
    'Alert.CloseReason.Name',
    'Alert.Location.BlacklistedLocation',
    'Alert.Location.AbnormalLocation',
    'Alert.EventsCount',
    'Alert.User.Name',
    'Alert.User.SamAccountName',
    'Alert.User.AccountType.Name',
    'Alert.User.IsFlagged',
    'Alert.Data.IsFlagged',
    'Alert.Data.IsSensitive',
    'Alert.Filer.Platform.Name',
    'Alert.Asset.Path',
    'Alert.Filer.Name',
    'Alert.Device.HostName',
    'Alert.Device.IsMaliciousExternalIP',
    'Alert.Device.ExternalIPThreatTypesName']

''' CLIENT CLASS '''


class Client(BaseClient):

    """Client class to interact with the service API

    This Client implements API calls, and does not contain any XSOAR logic.
    Should only do requests and return data.
    It inherits from BaseClient defined in CommonServer Python.
    Most calls use _http_request() that handles proxy, SSL verification, etc.
    For this  implementation, no special attributes defined
    """
    def baseintegration_dummy(self, url: str) -> Dict[str, str]:
        """Returns a simple python dict with the information provided
        in the input (dummy).

        :type dummy: ``str``
        :param dummy: string to add in the dummy dict that is returned

        :return: dict as {"dummy": dummy}
        :rtype: ``str``
        """

        return {'dummy': url}

    def varonis_authenticate(self, username: str, password: str) -> Dict[str, Any]:
        ntlm = HttpNtlmAuth(username, password)
        response = self._http_request('POST', '/auth/win', auth=ntlm, data='grant_type=client_credentials')
        token = response['access_token']
        token_type = response['token_type']
        self._expires_in = response['expires_in']
        self._headers = {
            'Authorization': f'{token_type} {token}'
        }
        return response

    def varonis_get_enum(self, enum_id: int) -> List[Any]:
        respose = self._http_request('GET', f'/api/entitymodel/enum/{enum_id}')
        return respose

    def varonis_search_alerts(self, query: Dict[str, Any]) -> List[Any]:
        response = self._http_request('POST', '/api/search/v2/search', json_data=query)
        return response

    def varonis_get_alerts(self, search_location: str, url_query: str, retries=0) -> Dict[str, Any]:
        response = self._http_request(
            'GET',
            f'/api/search/{search_location}?{url_query}',
            retries=retries,
            status_list_to_retry=STATUSES_TO_RETRY)
        return response


''' HELPER FUNCTIONS '''


class SearchQueryBuilder(object):
    def __init__(self, select_columns: List[str], client: Client):
        self._filters: List[Any] = []
        self._columns = select_columns
        self._client = client
        self._url_query = ''

    def create_threat_model_filter(self, threats: List[str]):
        rule_enum = self._client.varonis_get_enum(THREAT_MODEL_ENUM_ID)
        filter_obj: Dict[str, Any] = {
            'path': 'Alert.Rule.ID',
            'operator': 'In',
            'values': []
        }

        for t in threats:
            rule = next(x for x in rule_enum if x['ruleName'] == t)
            threat_object = {
                'Alert.Rule.ID': rule['ruleID'],
                'displayValue': rule['ruleName']
            }
            filter_obj['values'].append(threat_object)
        self._filters.append(filter_obj)

    def create_time_interval_filter(self, start: datetime, end: datetime):
        filter_obj: Dict[str, Any] = {
            'path': 'Alert.Time',
            'operator': 'Between',
            'values': [
                {
                    'Alert.Time': start.isoformat(),
                    'displayValue': start.isoformat(),
                    'Alert.Time0': end.isoformat()
                }
            ]
        }
        self._filters.append(filter_obj)

    def create_alert_status_filter(self, statuses: List[str]):
        status_enum = ALERT_STATUSES
        filter_obj: Dict[str, Any] = {
            'path': 'Alert.Status.ID',
            'operator': 'In',
            'values': []
        }

        for status_name in statuses:
            status_id = status_enum[status_name]
            status_object = {
                'Alert.Status.ID': status_id,
                'displayValue': status_name
            }
            filter_obj['values'].append(status_object)
        self._filters.append(filter_obj)

    def build(self):
        query: Dict[str, Any] = dict()
        query['rows'] = {'columns': self._columns}
        query['query'] = {
            'entityName': 'Alert',
            'requestParams': {'searchSource': 1, 'searchSourceName': 'Alert'},  # todo
            'filter': {'filterOperator': 0, 'filters': self._filters}
        }
        return query


def get_query_range(count: int):
    if count:
        return f'from=0&to={count-1}'
    else:
        return ''


def get_search_result_path(search_response: List[Any]) -> str:
    return next(x['location'] for x in search_response if x['dataType'] == 'rows')


def get_alerts(client: Client, statuses: List[str], threats: List[str], start: datetime, end: datetime, count: int):
    builder = SearchQueryBuilder(ALERT_COLUMNS, client)

    if statuses and any(statuses):
        builder.create_alert_status_filter(statuses)
    if threats and any(threats):
        builder.create_threat_model_filter(threats)
    if start and end:
        builder.create_time_interval_filter(start, end)

    query = builder.build()

    response = client.varonis_search_alerts(query)
    location = get_search_result_path(response)
    date_range = get_query_range(count)

    search_result = client.varonis_get_alerts(location, date_range, 10)
    return search_result


def create_output_from_alerts(rows: List[Any]) -> List[str]:
    outputs: List[Any] = []
    for row in rows:
        output = {
            'ID': row[0],
            'Name': row[1],
            'Time': row[2],
            'Severity': row[3],
            'Category': row[4],
            'Country': row[5],
            'State': row[6],
            'Status': row[7],
            'CloseReason': row[8],
            'BlacklistLocation': row[9],
            'AbnormalLocation': row[10],
            'NumOfAlertedEvents': row[11],
            'UserName': row[12],
            'By.SamAccountName': row[13],
            'By.PreivilegedAccountType': row[14],
            'By.HasFollowUpIndicators': row[15],
            'On.ContainsFlaggedData': row[16],
            'On.ContainsSensitiveData': row[17],
            'On.Platform': row[18],
            'on.Asset': row[19],
            'On.FileServerOrDomain': row[20],
            'Device.Name': row[21],
            'Device.ContainMaliciousExternalIP': row[22],
            'Device.IPThreatTypes': row[23]
        }
        outputs.append(output)
    return outputs


''' COMMAND FUNCTIONS '''


def test_module(client: Client) -> str:
    """Tests API connectivity and authentication'

    Returning 'ok' indicates that the integration works like it is supposed to.
    Connection to the service is successful.
    Raises exceptions if something goes wrong.

    :type client: ``Client``
    :param Client: client to use

    :return: 'ok' if test passed, anything else will fail the test.
    :rtype: ``str``
    """

    message: str = ''
    try:
        client.varonis_get_enum(THREAT_MODEL_ENUM_ID)
        message = 'ok'
    except DemistoException as e:
        if 'Forbidden' in str(e) or 'Authorization' in str(e):  # TODO: make sure you capture authentication errors
            message = 'Authorization Error: make sure API Key is correctly set'
        else:
            raise e
    return message


def varonis_get_alerts_command(client: Client, args: Dict[str, Any]) -> CommandResults:

    threat_model_names = args.get('threat_model_name', None)
    max_results = args.get('max_results', None)
    start_time = args.get('Start time', None)
    end_time = args.get('End time', None)
    alert_statuses = args.get('Alert Status', None)

    result = get_alerts(client, alert_statuses, threat_model_names, start_time, end_time, max_results)
    outputs = create_output_from_alerts(result['rows'])
    return CommandResults(
        outputs_prefix='Varonis.Alert',
        outputs_key_field='Varonis.Alert.ID',
        outputs=outputs,
    )


def varonis_update_alert_status_command(client: Client, args: Dict[str, Any]) -> CommandResults:
    pass


''' MAIN FUNCTION '''


def main() -> None:
    """main function, parses params and runs command functions

    :return:
    :rtype:
    """

    # TODO: make sure you properly handle authentication
    username = demisto.params().get('Username')
    password = demisto.params().get('Password')

    # get the service API url
    base_url = urljoin(demisto.params()['url'], '/DatAdvantage')

    # if your Client class inherits from BaseClient, SSL verification is
    # handled out of the box by it, just pass ``verify_certificate`` to
    # the Client constructor
    verify_certificate = not demisto.params().get('insecure', False)

    # if your Client class inherits from BaseClient, system proxy is handled
    # out of the box by it, just pass ``proxy`` to the Client constructor
    proxy = demisto.params().get('proxy', False)

    demisto.debug(f'Command being called is {demisto.command()}')
    try:
        client = Client(
            base_url=base_url,
            verify=verify_certificate,
            proxy=proxy
        )

        client.varonis_authenticate(username, password)

        if demisto.command() == 'test-module':
            # This is the call made when pressing the integration Test button.
            result = test_module(client)
            return_results(result)

        # TODO: REMOVE the following dummy command case:
        elif demisto.command() == 'varonis-get-alerts':
            return_results(varonis_get_alerts_command(client, demisto.args()))
        elif demisto.command() == 'varonis-update-alert-status':
            return_results(varonis_update_alert_status_command(client, demisto.args()))
        # TODO: ADD command cases for the commands you will implement

    # Log exceptions and return errors
    except Exception as e:
        demisto.error(traceback.format_exc())  # print the traceback
        return_error(f'Failed to execute {demisto.command()} command.\nError:\n{str(e)}')


''' ENTRY POINT '''


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
