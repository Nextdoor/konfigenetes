import unittest
from pathlib import Path

import yaml

from konfigenetes import konfigenetes


def test_data_file(filename):
    """Gets path to a Konfigenetes file"""
    return str(Path(__file__).parent / 'test_data' / filename)


class TestKonfigenetes(unittest.TestCase):
    """Konfigenetes tests"""

    def test_no_changes(self):
        """Test no changes if no patches or variables."""
        konfigured_resources = konfigenetes(
            resource_file_paths=[test_data_file('resources/pod_and_service.yml')])

        with open(test_data_file('resources/pod_and_service.yml')) as resource_file:
            unkonfigured_resources = list(yaml.load_all(resource_file))

        self.assertEqual(konfigured_resources, unkonfigured_resources)

    def test_env_var_patch(self):
        """Test patching env vars."""
        konfigured_resources = konfigenetes(
            resource_file_paths=[test_data_file('resources/pod_and_service.yml')],
            patch_file_paths=[test_data_file('patches/env_vars.yml')])

        konfigured_env = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['env']
        expected_env = [
            {'name': 'ENV_1', 'value': 'NEW_VAL_1'},
            {'name': 'ENV_2', 'value': 'VAL_2'},
            {'name': 'ENV_3', 'value': 'VAL_3'},
            {'name': 'NEW_ENV_VAR', 'value': 'NEW_VAL_2'},
        ]

        self.assertEqual(konfigured_env, expected_env)

    def test_volume_mounts(self):
        """Test patching volume mounts."""
        konfigured_resources = konfigenetes(
            resource_file_paths=[test_data_file('resources/pod_and_service.yml')],
            patch_file_paths=[test_data_file('patches/volume_mounts.yml')])

        konfigured_volume_mounts = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['volumeMounts']
        expected_volume_mounts = [
            {'name': 'volume-mount', 'mountPath': '/mnt'},
        ]

        self.assertEqual(konfigured_volume_mounts, expected_volume_mounts)

        konfigured_volumes = konfigured_resources[1]['spec']['template']['spec']['volumes']
        expected_volumes = [
            {
                'name': 'volume-mount',
                'hostPath': {
                    'path': '/mnt/basic-service',
                }
            },
        ]

        self.assertEqual(konfigured_volumes, expected_volumes)

    def test_variable_port(self):
        """Test patching service port."""
        with self.assertRaises(ValueError):
            # Missing var raises exception.
            konfigenetes(
                resource_file_paths=[test_data_file('resources/pod_and_service.yml')],
                patch_file_paths=[test_data_file('patches/var_port.yml')])

        konfigured_resources = konfigenetes(
            resource_file_paths=[test_data_file('resources/pod_and_service.yml')],
            patch_file_paths=[test_data_file('patches/var_port.yml')],
            var_values={'PORT': '8000'})

        konfigured_ports = konfigured_resources[0]['spec']['ports']
        expected_ports = [
            {'port': '8000', 'protocol': 'TCP', 'name': 'http'},
        ]

        self.assertEqual(konfigured_ports, expected_ports)

    def test_variable_config(self):
        """Test patching config map."""
        with self.assertRaises(ValueError):
            # Missing var raises exception.
            konfigenetes(
                resource_file_paths=[test_data_file('resources/var_config.yml')])

        konfigured_resources = konfigenetes(
            resource_file_paths=[test_data_file('resources/var_config.yml')],
            var_values={'VAR_VALUE': '1'})

        konfigured_data = konfigured_resources[0]['data']
        expected_data = {'TEST_VAR_1': '1', 'TEST_VAR_2': '2', 'TEST_VAR_3': 'start text 1 end text',
                         'TEST_VAR_4': '1 end value', 'TEST_VAR_5': 'start text 1',
                         'TEST_VAR_6': 'not a variable { VAR_VALUE }'}

        print(konfigured_data, expected_data)

        self.assertEqual(konfigured_data, expected_data)

    def test_big_input_file(self):
        """Test a large big input file works."""
        konfigured_resources = konfigenetes(
            input_file_paths=[test_data_file('inputs/input_file.yml')])

        konfigured_volume_mounts = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['volumeMounts']
        expected_volume_mounts = [
            {'name': 'volume-mount', 'mountPath': '/mnt'},
        ]

        self.assertEqual(konfigured_volume_mounts, expected_volume_mounts)

        konfigured_volumes = konfigured_resources[1]['spec']['template']['spec']['volumes']
        expected_volumes = [
            {
                'name': 'volume-mount',
                'hostPath': {
                    'path': '/mnt/basic-service',
                }
            },
        ]

        self.assertEqual(konfigured_volumes, expected_volumes)

        konfigured_env = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['env']
        expected_env = [
            {'name': 'ENV_1', 'value': 'NEW_VAL_1'},
            {'name': 'ENV_2', 'value': 'VAL_2'},
            {'name': 'ENV_3', 'value': 'VAL_3'},
            {'name': 'NEW_ENV_VAR', 'value': 'NEW_VAL_2'},
        ]

        self.assertEqual(konfigured_env, expected_env)

        konfigured_ports = konfigured_resources[0]['spec']['ports']
        expected_ports = [
            {'port': '8000', 'protocol': 'TCP', 'name': 'http'},
        ]

        self.assertEqual(konfigured_ports, expected_ports)

        konfigured_data = konfigured_resources[2]['data']
        expected_data = {'TEST_VAR_1': '1', 'TEST_VAR_2': '2', 'TEST_VAR_3': 'start text 1 end text',
                         'TEST_VAR_4': '1 end value', 'TEST_VAR_5': 'start text 1',
                         'TEST_VAR_6': 'not a variable { VAR_VALUE }'}

        self.assertEqual(konfigured_data, expected_data)

    def test_big_input_file_override(self):
        """Test a large input file works with var overrides."""
        konfigured_resources = konfigenetes(
            input_file_paths=[test_data_file('inputs/input_file.yml')],
            var_values={'PORT': '80', 'VAR_VALUE': '2'})

        konfigured_volume_mounts = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['volumeMounts']
        expected_volume_mounts = [
            {'name': 'volume-mount', 'mountPath': '/mnt'},
        ]

        self.assertEqual(konfigured_volume_mounts, expected_volume_mounts)

        konfigured_volumes = konfigured_resources[1]['spec']['template']['spec']['volumes']
        expected_volumes = [
            {
                'name': 'volume-mount',
                'hostPath': {
                    'path': '/mnt/basic-service',
                }
            },
        ]

        self.assertEqual(konfigured_volumes, expected_volumes)

        konfigured_env = konfigured_resources[1]['spec']['template']['spec']['containers'][0]['env']
        expected_env = [
            {'name': 'ENV_1', 'value': 'NEW_VAL_1'},
            {'name': 'ENV_2', 'value': 'VAL_2'},
            {'name': 'ENV_3', 'value': 'VAL_3'},
            {'name': 'NEW_ENV_VAR', 'value': 'NEW_VAL_2'},
        ]

        self.assertEqual(konfigured_env, expected_env)

        konfigured_ports = konfigured_resources[0]['spec']['ports']
        expected_ports = [
            {'port': '80', 'protocol': 'TCP', 'name': 'http'},
        ]

        self.assertEqual(konfigured_ports, expected_ports)

        konfigured_data = konfigured_resources[2]['data']
        expected_data = {'TEST_VAR_1': '2', 'TEST_VAR_2': '2', 'TEST_VAR_3': 'start text 2 end text',
                         'TEST_VAR_4': '2 end value', 'TEST_VAR_5': 'start text 2',
                         'TEST_VAR_6': 'not a variable { VAR_VALUE }'}

        self.assertEqual(konfigured_data, expected_data)
