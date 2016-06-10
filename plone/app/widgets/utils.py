# -*- coding: utf-8 -*-

from Acquisition import aq_inner, aq_parent
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.utils import getToolByName
from datetime import datetime
from plone.app.layout.navigation.root import getNavigationRootObject
from zope.component import getMultiAdapter
from zope.component import providedBy
from zope.component import queryUtility
from zope.component.hooks import getSite
from zope.i18n import translate
from zope.i18nmessageid import MessageFactory
from zope.schema.interfaces import IVocabularyFactory
from z3c.form.interfaces import IAddForm
from Products.CMFCore.interfaces._content import IFolderish
from plone.uuid.interfaces import IUUID
from Products.CMFPlone.interfaces import IPloneSiteRoot

import logging


_ = MessageFactory('plone.app.widgets')
_plone = MessageFactory('plone')


logger = logging.getLogger('plone.app.widgets')


try:
    from plone.app.event import base as pae_base
    HAS_PAE = True
except ImportError:
    HAS_PAE = False


def first_weekday():
    if HAS_PAE:
        wkday = pae_base.wkday_to_mon1(pae_base.first_weekday())
        if wkday > 1:
            return 1  # Default to Monday
        return wkday
    else:
        cal = getToolByName(getSite(), 'portal_calendar', None)
        if cal:
            wkday = cal.firstweekday
            if wkday == 6:  # portal_calendar's Sunday is 6
                return 0  # Sunday
        return 1  # other cases: Monday


class NotImplemented(Exception):
    """Raised when method/property is not implemented"""


def get_date_options(request):
    calendar = request.locale.dates.calendars['gregorian']
    today = datetime.today()
    return {
        'time': False,
        'date': {
            'firstDay': calendar.week.get('firstDay') == 1 and 1 or 0,
            'weekdaysFull': [
                calendar.days.get(t, (None, None))[0]
                for t in (7, 1, 2, 3, 4, 5, 6)],
            'weekdaysShort': [
                calendar.days.get(t, (None, None))[1]
                for t in (7, 1, 2, 3, 4, 5, 6)],
            'monthsFull': calendar.getMonthNames(),
            'monthsShort': calendar.getMonthAbbreviations(),
            'selectYears': 200,
            'min': [today.year - 100, 1, 1],
            'max': [today.year + 20, 1, 1],
            'format': translate(
                _('pickadate_date_format', default='mmmm d, yyyy'),
                context=request),
            'placeholder': translate(_plone('Enter date...'), context=request),
            'today': translate(_plone(u"Today"), context=request),
            'clear': translate(_plone(u"Clear"), context=request),
        }
    }


def get_datetime_options(request):
    options = get_date_options(request)
    options['time'] = {
        'format': translate(
            _('pickadate_time_format', default='h:i a'),
            context=request),
        'placeholder': translate(_plone('Enter time...'), context=request),
        'today': translate(_plone(u"Today"), context=request),
    }
    return options


def get_ajaxselect_options(context, value, separator, vocabulary_name,
                           vocabulary_view, field_name=None):
    options = {'separator': separator}
    if vocabulary_name:
        options['vocabularyUrl'] = '{}/{}?name={}'.format(
            get_context_url(context), vocabulary_view, vocabulary_name)
        if field_name:
            options['vocabularyUrl'] += '&field={}'.format(field_name)
        if value:
            vocabulary = queryUtility(IVocabularyFactory, vocabulary_name)
            if vocabulary:
                options['initialValues'] = {}
                vocabulary = vocabulary(context)
                # Catalog
                if vocabulary_name == 'plone.app.vocabularies.Catalog':
                    if isinstance(value, (str, unicode)):
                        uids = value.split(separator)
                    else:
                        uids = value
                    try:
                        catalog = getToolByName(context, 'portal_catalog')
                    except AttributeError:
                        catalog = getToolByName(getSite(), 'portal_catalog')
                    for item in catalog(UID=uids):
                        options['initialValues'][item.UID] = item.Title
                else:
                    for value in value.split(separator):
                        try:
                            term = vocabulary.getTerm(value)
                            options['initialValues'][term.token] = term.title
                        except LookupError:
                            options['initialValues'][value] = value

    return options


def get_relateditems_options(context, value, separator, vocabulary_name,
                             vocabulary_view, field_name=None):

    portal = get_portal()
    options = get_ajaxselect_options(portal, value, separator,
                                     vocabulary_name, vocabulary_view,
                                     field_name)

    msgstr = translate(_plone(u'Search'), context=context.REQUEST)
    options.setdefault('searchText', msgstr)
    msgstr = translate(_(u'Entire site'), context=context.REQUEST)
    options.setdefault('searchAllText', msgstr)
    msgstr = translate(_plone('tabs_home',
                       default=u'Home'),
                       context=context.REQUEST)
    options.setdefault('homeText', msgstr)
    options.setdefault('folderTypes', ['Folder'])

    properties = getToolByName(context, 'portal_properties')
    if properties:
        options['folderTypes'] = properties.site_properties.getProperty(
            'typesLinkToFolderContentsInFC', options['folderTypes'])

    if field_name and hasattr(context, 'Schema'):
        field = context.Schema()[field_name]
        if isinstance(field.allowed_types, basestring):
            allowed_types = [field.allowed_types]
        else:
            allowed_types = list(field.allowed_types)
        if hasattr(field, 'allowed_types') and field.allowed_types:
            options['selectableTypes'] = allowed_types
            options['baseCriteria'] = [{
                'i': 'portal_type',
                'o': 'plone.app.querystring.operation.list.contains',
                'v': allowed_types + list(options['folderTypes'])
            }]

    portal_state = getMultiAdapter((context, context.REQUEST),
                                   name=u'plone_portal_state')
    if 'basePath' not in options:
        portal_path = '/'.join(portal.getPhysicalPath())
        options['basePath'] = portal_state.navigation_root_path()[len(portal_path):]
    return options


def get_querystring_options(context, querystring_view):
    portal_url = get_portal_url(context)
    try:
        base_url = context.absolute_url()
    except AttributeError:
        base_url = portal_url
    return {
        'indexOptionsUrl': '{}/{}'.format(portal_url, querystring_view),
        'previewURL': '%s/@@querybuilder_html_results' % base_url,
        'previewCountURL': '%s/@@querybuildernumberofresults' % base_url
    }


def get_tinymce_options(context, field, request):
    args = {'pattern_options': {}}
    folder = context
    if not IFolderish.providedBy(context):
        folder = aq_parent(context)
    if IPloneSiteRoot.providedBy(folder):
        initial = None
    else:
        initial = IUUID(folder, None)
    portal_url = get_portal_url(context)
    current_path = folder.absolute_url()[len(portal_url):]

    utility = getToolByName(aq_inner(context), 'portal_tinymce', None)
    if utility:
        try:
            config = utility.getConfiguration(context=context,
                                              field=field,
                                              request=request)

        except KeyError:
            # XXX: When a piece of content has an invalid layout, this fails
            logger.warn("Object %s has an invalid layout property set" % context.absolute_url())
            config = {'portal_url': portal_url,
                      'navigation_root_url': portal_url}

        if 'customplugins' in config:
            del config['customplugins']
        if 'plugins' in config:
            del config['plugins']
        if 'theme' in config:
            del config['theme']

        config['content_css'] = config['portal_url'] + '/base.css'
        args['pattern_options'] = {
            'relatedItems': {
                'vocabularyUrl': config['portal_url'] +
                '/@@getVocabulary?name=plone.app.vocabularies.Catalog'
            },
            'upload': {
                'initialFolder': initial,
                'currentPath': current_path,
                'baseUrl': config['navigation_root_url'],
                'relativePath': '@@fileUpload',
                'uploadMultiple': False,
                'maxFiles': 1,
                'showTitle': False
            },
            'tiny': config,
            'prependToUrl': 'resolveuid/',
            'linkAttribute': 'UID',
            'prependToScalePart': '/@@images/image/',
            'folderTypes': utility.containsobjects.replace('\n', ','),
            'imageTypes': utility.imageobjects.replace('\n', ','),
            'anchorSelector': utility.anchor_selector,
            'linkableTypes': utility.linkable.replace('\n', ',')
        }
    else:
        args['pattern_options'].update({
            'relatedItems': {
                'vocabularyUrl': portal_url +
                '/@@getVocabulary?name=plone.app.vocabularies.Catalog'
            },
            'upload': {
                'initialFolder': initial,
                'currentPath': current_path,
                'baseUrl': portal_url,
                'relativePath': '@@fileUpload',
                'uploadMultiple': False,
                'maxFiles': 1,
                'showTitle': False
            },
            'base_url': context.absolute_url(),
            'prependToUrl': 'resolveuid/',
            'linkAttribute': 'UID',
            'prependToScalePart': '/@@images/image/',
            # XXX need to get this from somewhere...
            'folderTypes': ','.join(['Folder']),
            'imageTypes': ','.join(['Image']),
            #'anchorSelector': utility.anchor_selector,
            #'linkableTypes': utility.linkable.replace('\n', ',')
        })
    return args


def get_portal():
    closest_site = getSite()
    if closest_site is not None:
        for potential_portal in closest_site.aq_chain:
            if ISiteRoot in providedBy(potential_portal):
                return potential_portal


def get_portal_url(context):
    portal = get_portal()
    if portal:
        root = getNavigationRootObject(context, portal)
        if root:
            try:
                return root.absolute_url()
            except AttributeError:
                return portal.absolute_url()
        else:
            return portal.absolute_url()
    return ''


def get_context_url(context):
    if IAddForm.providedBy(context):
        # Use the request URL if we are looking at an addform
        url = context.request.get('URL')
    elif hasattr(context, 'absolute_url'):
        url = context.absolute_url
        if callable(url):
            url = url()
    else:
        url = get_portal_url(context)
    return url
