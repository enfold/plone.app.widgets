from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView

import json


class getFolderUrl(BrowserView):
    """
    Helper view that will return the URL of a folder object based on its UUID.
    """

    def __call__(self):
        uuid = self.request.get('uuid')
        catalog = self.context.portal_catalog
        res = catalog.unrestrictedSearchResults(UID=uuid)
        if res:
            return json.dumps(res[0].getURL())
