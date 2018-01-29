
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from zope.component.hooks import getSite
from zope.interface import implements
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


class KeywordsVocabulary(object):

    implements(IVocabularyFactory)

    def __call__(self, context, query=None):
        site = getSite()
        catalog = getToolByName(site, 'portal_catalog', None)
        if catalog is None:
            return SimpleVocabulary([])
        index = catalog._catalog.getIndex('Subject')

        def safe_encode(v):
            if not isinstance(v, unicode):
                v = v.decode('utf-8')
            return v.encode('ascii', errors='backslashreplace')

        items = [
            SimpleTerm(i, safe_encode(i), safe_unicode(i))
            for i in index._index
            if query is None or safe_encode(query) in safe_encode(i)
        ]
        return SimpleVocabulary(items)

KeywordsVocabularyFactory = KeywordsVocabulary()