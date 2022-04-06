"""Base Integration for Cortex XSOAR - Unit Tests file

Pytest Unit Tests: all funcion names must start with "test_"

More details: https://xsoar.pan.dev/docs/integrations/unit-testing

MAKE SURE YOU REVIEW/REPLACE ALL THE COMMENTS MARKED AS "TODO"

You must add at least a Unit Test function for every XSOAR command
you are implementing with your integration
"""

import json
import io
import demistomock as demisto
from pytest_mock import MockerFixture

from VaronisDataSecurityPlatform import Client


def util_load_json(path):
    with io.open(path, mode='r', encoding='utf-8') as f:
        return json.loads(f.read())


''' COMMAND UNIT TESTS '''


def test_varonis_get_alerts_command(mocker: MockerFixture):
    """
        When:
            - Get alerts from Varonis api
        Then
            - Assert output prefix data is as expected
            - Assert mapping works as expected
    """
    from VaronisDataSecurityPlatform import varonis_get_alerts_command

    client = Client(
        base_url='https://test.com',
        verify=False,
        proxy=False
    )
    mocker.patch.object(
        client,
        'varonis_execute_search',
        return_value=util_load_json('test_data/search_alerts_response.json')
    )
    mocker.patch.object(
        client,
        'varonis_get_search_result',
        return_value=util_load_json('test_data/varonis_get_alerts_api_response.json')
    )
    mocker.patch.object(
        client,
        'varonis_get_enum',
        return_value=util_load_json('test_data/varonis_get_enum_response.json')
    )

    args = util_load_json("test_data/demisto_search_alerts_args.json")
    expected_outputs = util_load_json('test_data/varonis_get_alerts_command_output.json')

    result = varonis_get_alerts_command(client, args)

    assert result.outputs_prefix == 'Varonis'
    assert result.outputs == expected_outputs


def test_varonis_update_alert_status_command(requests_mock):
    from VaronisDataSecurityPlatform import varonis_update_alert_status_command

    requests_mock.post('https://test.com/api/alert/alert/SetStatusToAlerts', json=True)

    client = Client(
        base_url='https://test.com',
        verify=False,
        proxy=False
    )

    args = {
        'Status': 'Under Investigation',
        'Alert_id': "C8CF4194-133F-4F5A-ACB1-FFFB00573468, F8F608A7-0256-42E0-A527-FFF4749C1A8B"
    }

    resp = varonis_update_alert_status_command(client, args)

    assert resp is True


def test_varonis_close_alert_command(requests_mock):
    from VaronisDataSecurityPlatform import varonis_close_alert_command

    requests_mock.post('https://test.com/api/alert/alert/SetStatusToAlerts', json=True)

    client = Client(
        base_url='https://test.com',
        verify=False,
        proxy=False
    )

    args = {
        'Close_Reason': 'Account misclassification',
        'Alert_id': "C8CF4194-133F-4F5A-ACB1-FFFB00573468, F8F608A7-0256-42E0-A527-FFF4749C1A8B"
    }

    resp = varonis_close_alert_command(client, args)

    assert resp is True


def test_varonis_get_alerted_events_command(mocker: MockerFixture):
    """
        When:
            - Get alerted events from Varonis api
        Then
            - Assert output prefix data is as expected
            - Assert mapping works as expected
    """

    from VaronisDataSecurityPlatform import varonis_get_alerted_events_command

    client = Client(
        base_url='https://test.com',
        verify=False,
        proxy=False
    )
    mocker.patch.object(
        client,
        'varonis_execute_search',
        return_value=util_load_json('test_data/search_alerted_events_response.json')
    )
    mocker.patch.object(
        client,
        'varonis_get_search_result',
        return_value=util_load_json('test_data/varonis_get_alerted_events_response.json')
    )

    args = util_load_json("test_data/demisto_alerted_events_args.json")
    expected_outputs = util_load_json('test_data/varonis_get_alerted_events_command_output.json')

    result = varonis_get_alerted_events_command(client, args)

    assert result.outputs_prefix == 'Varonis'
    assert result.outputs == expected_outputs


def test_fetch_incidents(mocker: MockerFixture, requests_mock: MockerFixture):
    from VaronisDataSecurityPlatform import fetch_incidents

    requests_mock.get(
        'https://test.com/api/alert/alert/GetAlertsID'
        '?threatModels=Suspicious&severity=Medium&status=1&fromAlertId=150&bulkSize=200',
        json=util_load_json('test_data/demisto_get_alert_ids.json'))

    client = Client(
        base_url='https://test.com',
        verify=False,
        proxy=False
    )

    mocker.patch.object(
        client,
        'varonis_get_enum',
        return_value=util_load_json('test_data/varonis_get_enum_response.json')
    )

    mocker.patch.object(
        client,
        'varonis_execute_search',
        return_value=util_load_json('test_data/search_alerts_response.json')
    )

    mocker.patch.object(
        client,
        'varonis_get_search_result',
        return_value=util_load_json('test_data/varonis_get_alerts_api_response.json')
    )

    mocker.patch.object(demisto, 'debug', return_value=None)

    last_run = {
        'last_fetched_id': 150
    }

    next_run, incidents = fetch_incidents(
        client=client,
        max_results=200,
        alert_status='Open',
        severity='Medium',
        threat_model='Suspicious',
        last_run=last_run,
        first_fetch_time='3 days'
    )

    expected_outputs = util_load_json('test_data/varonis_get_alerts_command_output.json')

    assert next_run == {'last_fetched_id': 200}
    assert incidents == [
        {
            'name': 'Varonis alert 4FDB86C2-D78F-47EC-A1B1-74C4268A8A60',
            'occurred': '2022-02-12T13:59:00Z',
            'rawJSON': json.dumps(expected_outputs['Alert'][0]),
            'type': 'Varonis DSP Incident',
            'severity': 3,
        },
        {
            'name': 'Varonis alert D99AEA15-7F17-46FC-A249-942B974377D6',
            'occurred': '2022-02-12T13:59:00Z',
            'rawJSON': json.dumps(expected_outputs['Alert'][1]),
            'type': 'Varonis DSP Incident',
            'severity': 3,
        }
    ]
