import attr
from widgetastic.exceptions import NoSuchElementException
from widgetastic.widget import View, Text
from widgetastic_patternfly import Tab, Input, BootstrapSwitch, Button
from wrapanapi.systems import RHEVMSystem

from cfme.common.candu_views import VMUtilizationView
from cfme.common.provider import CANDUEndpoint, DefaultEndpoint, DefaultEndpointForm
from cfme.common.provider_views import BeforeFillMixin
from cfme.exceptions import ItemNotFound
from cfme.services.catalogs.catalog_items import RHVCatalogItem
from cfme.utils import version
from widgetastic_manageiq import LineChart
from . import InfraProvider


class RHEVMEndpoint(DefaultEndpoint):
    @property
    def view_value_mapping(self):
        tls_since_version = '5.8.0.8'
        return {'hostname': self.hostname,
                'api_port': getattr(self, 'api_port', None),
                'verify_tls': version.pick({
                    version.LOWEST: None,
                    tls_since_version: getattr(self, 'verify_tls', None)}),
                'ca_certs': version.pick({
                    version.LOWEST: None,
                    tls_since_version: getattr(self, 'ca_certs', None)})
                }


class RHEVMEndpointForm(View):
    @View.nested
    class default(Tab, DefaultEndpointForm, BeforeFillMixin):  # NOQA
        TAB_NAME = 'Default'
        api_port = Input('default_api_port')
        verify_tls = BootstrapSwitch(id='default_tls_verify')
        ca_certs = Input('default_tls_ca_certs')

    @View.nested
    class candu(Tab, BeforeFillMixin):  # NOQA
        TAB_NAME = 'C & U Database'
        hostname = Input('metrics_hostname')
        api_port = Input('metrics_api_port')
        database_name = Input('metrics_database_name')
        username = Input('metrics_userid')
        password = Input('metrics_password')
        confirm_password = Input('metrics_verify')
        change_password = Text(locator='.//a[normalize-space(.)="Change stored password"]')

        validate = Button('Validate')


class RHEVMVMUtilizationView(VMUtilizationView):
    """A VM Utilization view for rhevm providers"""
    vm_cpu = LineChart(id='miq_chart_parent_candu_0')
    vm_memory = LineChart(id='miq_chart_parent_candu_1')
    vm_disk = LineChart(id='miq_chart_parent_candu_2')
    vm_network = LineChart(id='miq_chart_parent_candu_3')


@attr.s(hash=False)
class RHEVMProvider(InfraProvider):
    SNAPSHOT_TITLE = 'description'  # Different for RHEV providers than other infra
    catalog_item_type = RHVCatalogItem
    vm_utilization_view = RHEVMVMUtilizationView
    type_name = "rhevm"
    mgmt_class = RHEVMSystem
    db_types = ["Redhat::InfraManager"]
    endpoints_form = RHEVMEndpointForm
    discover_dict = {"rhevm": True}
    settings_key = 'ems_redhat'
    # xpath locators for elements, to be used by selenium
    _console_connection_status_element = '//*[@id="connection-status"]|//*[@id="message-div"]'
    _canvas_element = '(//*[@id="remote-console"]/canvas|//*[@id="spice-screen"]/canvas)'
    _ctrl_alt_del_xpath = '//*[@id="ctrlaltdel"]'
    _fullscreen_xpath = '//*[@id="fullscreen"]'
    bad_credentials_error_msg = "Credential validation was not successful"
    log_name = 'rhevm'

    ems_events = [
        ('vm_create', {'event_type': 'USER_ADD_VM_FINISHED_SUCCESS', 'vm_or_template_id': None}),
        ('vm_stop', {'event_type': 'USER_STOP_VM', 'vm_or_template_id': None}),
        ('vm_start', {'event_type': 'USER_RUN_VM', 'vm_or_template_id': None}),
        ('vm_delete', {'event_type': 'USER_REMOVE_VM_FINISHED', 'vm_or_template_id': None})
    ]

    @property
    def view_value_mapping(self):
        return {
            'name': self.name,
            'prov_type': 'Red Hat Virtualization'
        }

    def deployment_helper(self, deploy_args):
        """ Used in utils.virtual_machines """
        if 'default_cluster' not in deploy_args:
            return {'cluster': self.data['default_cluster']}
        return {}

    @classmethod
    def from_config(cls, prov_config, prov_key):
        endpoints = {}
        for endp in prov_config['endpoints']:
            for expected_endpoint in (RHEVMEndpoint, CANDUEndpoint):
                if expected_endpoint.name == endp:
                    endpoints[endp] = expected_endpoint(**prov_config['endpoints'][endp])

        if prov_config.get('discovery_range'):
            start_ip = prov_config['discovery_range']['start']
            end_ip = prov_config['discovery_range']['end']
        else:
            start_ip = end_ip = prov_config.get('ipaddress')
        return cls.appliance.collections.infra_providers.instantiate(
            prov_class=cls,
            name=prov_config['name'],
            endpoints=endpoints,
            zone=prov_config.get('server_zone', 'default'),
            key=prov_key,
            start_ip=start_ip,
            end_ip=end_ip)

    # Following methods will only work if the remote console window is open
    # and if selenium focused on it. These will not work if the selenium is
    # focused on Appliance window.
    def get_console_connection_status(self):
        try:
            return self.appliance.browser.widgetastic.selenium.find_element_by_xpath(
                self._console_connection_status_element).text
        except NoSuchElementException:
            raise ItemNotFound("Element not found on screen, is current focus on console window?")

    def get_remote_console_canvas(self):
        try:
            return self.appliance.browser.widgetastic.selenium.find_element_by_xpath(
                self._canvas_element)
        except NoSuchElementException:
            raise ItemNotFound("Element not found on screen, is current focus on console window?")

    def get_console_ctrl_alt_del_btn(self):
        try:
            return self.appliance.browser.widgetastic.selenium.find_element_by_xpath(
                self._ctrl_alt_del_xpath)
        except NoSuchElementException:
            raise ItemNotFound("Element not found on screen, is current focus on console window?")

    def get_console_fullscreen_btn(self):
        try:
            return self.appliance.browser.widgetastic.selenium.find_element_by_xpath(
                self._fullscreen_xpath)
        except NoSuchElementException:
            raise ItemNotFound("Element not found on screen, is current focus on console window?")
