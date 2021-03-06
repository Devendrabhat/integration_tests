# -*- coding: utf-8 -*-
import time

import pytest

from cfme.utils.blockers import BZ
from cfme.utils.browser import ensure_browser_open, quit
from cfme.utils.wait import wait_for


@pytest.mark.tier(3)
@pytest.mark.sauce
def test_session_timeout(request, appliance):
    """Sets the timeout to shortest possible time and waits if it really times out."""

    auth_settings = appliance.server.authentication

    @request.addfinalizer  # Wow, why we did not figure this out before?!
    def _finalize():
        quit()
        ensure_browser_open()
        auth_settings.set_session_timeout(hours="24", minutes="0")

    auth_settings.set_session_timeout(hours="0", minutes="5")
    # Wait 10 minutes
    time.sleep(10 * 60)
    # Try getting timeout
    # I had to use wait_for because on 5.4 and upstream builds it made weird errors
    wait_for(
        lambda: appliance.browser.widgetastic.selenium.find_elements_by_xpath(
            "//div[(@id='flash_div' or @id='login_div') and contains(normalize-space(.), "
            "'Session was timed out due to inactivity')]"),
        num_sec=60,
        delay=5,
        fail_func=lambda: appliance.browser.widgetastic.selenium.click(
            "//a[normalize-space(text())='Cloud Intelligence']"
        )
    )


@pytest.mark.tier(0)
@pytest.mark.ignore_stream('5.8')  # Modifying settings via rest in 5.9+
@pytest.mark.meta(blockers=[BZ(1553394)])
def test_bind_timeout_rest(appliance, request):
    """Sets the session timeout via REST

    Notes:
        Written for BZ 1553394
    """
    old_bind = appliance.get_yaml_config().get('authentication', {}).get('bind_timeout')
    if not old_bind:
        pytest.skip('Unable to locate authentication:bind_timeout in advanced settings REST')
    request.addfinalizer(lambda: appliance.set_yaml_config(
        {'authentication': {'bind_timeout': int(old_bind)}})
    )

    offset = int(old_bind) + 10
    appliance.set_yaml_config({'authentication': {'bind_timeout': int(offset)}})
    assert int(appliance.get_yaml_config()['authentication']['bind_timeout']) == offset
