# -*- coding: utf-8 -*-
import attr
from navmazing import NavigateToSibling, NavigateToAttribute
from widgetastic.widget import View, Text, NoSuchElementException
from widgetastic_patternfly import BreadCrumb, Button, Dropdown

from cfme.base.ui import BaseLoggedInPage
from cfme.common import TagPageView, Taggable
from cfme.exceptions import SnapshotNotFoundError, ItemNotFound
from cfme.modeling.base import BaseCollection, BaseEntity
from cfme.utils.appliance.implementations.ui import CFMENavigateStep, navigator, navigate_to
from cfme.utils.log import logger
from cfme.utils.providers import get_crud_by_name
from cfme.utils.wait import wait_for
from widgetastic_manageiq import (
    Accordion, BaseEntitiesView, ItemsToolBarViewSelector, ManageIQTree, SummaryTable)


class VolumeSnapshotToolbar(View):
    """The toolbar on the Volume Snapshot page"""
    policy = Dropdown('Policy')
    download = Dropdown('Download')
    view_selector = View.nested(ItemsToolBarViewSelector)


class VolumeSnapshotDetailsToolbar(View):
    """The toolbar on the Volume Snapshot detail page"""
    configuration = Dropdown('Configuration')
    policy = Dropdown('Policy')
    download = Button('Download summary in PDF format')


class VolumeSnapshotDetailsEntities(View):
    """The entities on the Volume Snapshot detail page"""
    breadcrumb = BreadCrumb()
    title = Text('.//div[@id="center_div" or @id="main-content"]//h1')
    properties = SummaryTable('Properties')
    relationships = SummaryTable('Relationships')
    smart_management = SummaryTable('Smart Management')


class VolumeSnapshotDetailSidebar(View):
    """The accordion on the Volume Snapshot details page"""

    @View.nested
    class properties(Accordion):  # noqa
        tree = ManageIQTree()

    @View.nested
    class relationships(Accordion):  # noqa
        tree = ManageIQTree()


class VolumeSnapshotView(BaseLoggedInPage):
    """A base view for all the Volume Snapshot pages"""

    @property
    def in_volume_snapshots(self):
        return (
            self.logged_in_as_current_user and
            self.navigation.currently_selected == ['Storage', 'Block Storage', 'Volume Snapshots']
        )

    @property
    def is_displayed(self):
        return self.in_volume_snapshots


class VolumeSnapshotAllView(VolumeSnapshotView):
    """The all Volume Snapshot page"""
    toolbar = View.nested(VolumeSnapshotToolbar)
    including_entities = View.include(BaseEntitiesView, use_parent=True)

    @property
    def is_displayed(self):
        return (
            self.in_volume_snapshots and
            self.entities.title.text == 'Cloud Volume Snapshots')


class VolumeSnapshotDetailsView(VolumeSnapshotView):
    """The detail Volume Snapshot page"""

    @property
    def is_displayed(self):
        expected_title = '{} (Summary)'.format(self.context['object'].name)

        return (
            self.in_volume_snapshots and
            self.entities.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title)

    toolbar = View.nested(VolumeSnapshotDetailsToolbar)
    sidebar = View.nested(VolumeSnapshotDetailSidebar)
    entities = View.nested(VolumeSnapshotDetailsEntities)


@attr.s
class VolumeSnapshot(BaseEntity, Taggable):
    """ Model of an Storage Volume Snapshots in cfme

    Args:
        name: name of the snapshot
        provider: provider
    """
    name = attr.ib()
    provider = attr.ib()

    def refresh(self):
        self.provider.refresh_provider_relationships()
        self.browser.refresh()

    @property
    def exists(self):
        """ check for snapshot exist on UI.

        Returns:
            :py:class:`bool`
        """
        view = navigate_to(self.parent, 'All')
        return self.name in view.entities.all_entity_names

    @property
    def status(self):
        """ status of cloud volume snapshot.

        Returns:
            :py:class:`str` Status of volume snapshot.
        """
        view = navigate_to(self.parent, 'All')
        view.toolbar.view_selector.select("List View")

        for item in view.entities.elements.read():
            if self.name in item['Name']:
                return str(item['Status'])

    @property
    def size(self):
        """ size of cloud volume snapshot.

        Returns:
            :py:class:`int` size of volume snapshot in GB.
        """
        view = navigate_to(self, 'Details')
        return int(view.entities.properties.get_text_of('Size').split()[0])

    @property
    def volume_name(self):
        """ volume name of snapshot.

        Returns:
            :py:class:`str` respective volume name.
        """
        view = navigate_to(self, 'Details')
        return view.entities.relationships.get_text_of('Cloud Volume')

    @property
    def tenant_name(self):
        """ Tenant name of snapshot.

        Returns:
            :py:class:`str` respective tenant name for snapshot.
        """
        view = navigate_to(self, 'Details')
        return view.entities.relationships.get_text_of('Cloud Tenants')

    def delete(self, wait=True):
        """Delete snapshot """

        view = navigate_to(self, 'Details')
        view.toolbar.configuration.item_select('Delete Cloud Volume Snapshot')
        view.flash.assert_success_message('Delete initiated for 1 Cloud Volume Snapshot.')
        if wait:
            wait_for(
                lambda: not self.exists,
                message="Wait snapshot to disappear",
                delay=20,
                timeout=800,
                fail_func=self.refresh
            )


@attr.s
class VolumeSnapshotCollection(BaseCollection):
    """Collection object for :py:class:`cfme.storage.volume_snapshots.VolumeSnapshot`"""

    ENTITY = VolumeSnapshot

    def all(self):
        """returning all Snapshot objects for respective storage manager type"""
        view = navigate_to(self, 'All')
        view.toolbar.view_selector.select("List View")
        snapshots = []

        try:
            if 'provider' in self.filters:
                for item in view.entities.elements.read():
                    if self.filters.get('provider').name in item['Storage Manager']:
                        snapshots.append(self.instantiate(name=item['Name'],
                                                          provider=self.filters.get('provider')))
            else:
                for item in view.entities.elements.read():
                    provider_name = item['Storage Manager'].split()[0]
                    provider = get_crud_by_name(provider_name)
                    snapshots.append(self.instantiate(name=item['Name'], provider=provider))

        except NoSuchElementException:
            if snapshots:
                logger.error('VolumeSnapshotCollection: '
                             'NoSuchElementException in the middle of entities read')
            else:
                logger.warning('The snapshot table is probably not present or empty')
        return snapshots


@navigator.register(VolumeSnapshotCollection, 'All')
class All(CFMENavigateStep):
    VIEW = VolumeSnapshotAllView
    prerequisite = NavigateToAttribute('appliance.server', 'LoggedIn')

    def step(self):
        self.prerequisite_view.navigation.select('Storage', 'Block Storage', 'Volume Snapshots')


@navigator.register(VolumeSnapshot, 'Details')
class Details(CFMENavigateStep):
    VIEW = VolumeSnapshotDetailsView
    prerequisite = NavigateToAttribute('parent', 'All')

    def step(self, *args, **kwargs):
        try:
            self.prerequisite_view.entities.get_entity(name=self.obj.name,
                                                       surf_pages=True).click()
        except ItemNotFound:
            raise SnapshotNotFoundError('Could not locate volume snapshot {}'.format(self.obj.name))


@navigator.register(VolumeSnapshot, 'EditTagsFromDetails')
class SnapshotDetailEditTag(CFMENavigateStep):
    """ This navigation destination help to Taggable"""
    VIEW = TagPageView
    prerequisite = NavigateToSibling('Details')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.policy.item_select('Edit Tags')
