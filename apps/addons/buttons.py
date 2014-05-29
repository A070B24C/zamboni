from django.shortcuts import render
from django.views.decorators.cache import cache_page

import jingo
import jinja2
from tower import ugettext_lazy as _lazy

import amo
from amo.helpers import urlparams


def _install_button(context, addon, version=None, show_contrib=True,
                    show_warning=True, src='', collection=None, size='',
                    detailed=False, mobile=False, impala=False):
    """If version isn't given, we use the latest version."""
    request = context['request']
    app, lang = context['APP'], context['LANG']
    src = src or context.get('src') or request.GET.get('src', '')
    collection = ((collection.uuid if hasattr(collection, 'uuid') else None)
                   or collection
                   or context.get('collection')
                   or request.GET.get('collection')
                   or request.GET.get('collection_id')
                   or request.GET.get('collection_uuid'))
    button = install_button_factory(addon, app, lang, version, show_contrib,
                                    show_warning, src, collection, size,
                                    detailed, impala)
    installed = (request.user.is_authenticated() and
                 addon.id in request.amo_user.mobile_addons)
    c = {'button': button, 'addon': addon, 'version': button.version,
         'installed': installed}
    if impala:
        template = 'addons/impala/button.html'
    elif mobile:
        template = 'addons/mobile/button.html'
    else:
        template = 'addons/button.html'
    t = jingo.render_to_string(request, template, c)
    return jinja2.Markup(t)


@jinja2.contextfunction
def install_button(context, addon, **kwargs):
    return _install_button(context, addon, **kwargs)


@jinja2.contextfunction
def big_install_button(context, addon, **kwargs):
    from addons.helpers import statusflags
    flags = jinja2.escape(statusflags(context, addon))
    base = _install_button(context, addon, detailed=True, size='prominent',
                           **kwargs)
    params = [flags, base]
    wrap = u'<div class="install-wrapper %s">%s</div>'
    return jinja2.Markup(wrap % (tuple(params)))


@jinja2.contextfunction
def mobile_install_button(context, addon, **kwargs):
    from addons.helpers import statusflags
    b = _install_button(context, addon, detailed=True, size='prominent',
                        mobile=True, **kwargs)
    flags = jinja2.escape(statusflags(context, addon))
    s = u'<div class="install-wrapper %s">%s</div>'
    return jinja2.Markup(s % (flags, b))


def install_button_factory(*args, **kwargs):
    button = InstallButton(*args, **kwargs)
    # Order matters.  We want to highlight unreviewed before featured.  They
    # should be mutually exclusive, but you never know.
    classes = (('lite', LiteInstallButton),
               ('unreviewed', UnreviewedInstallButton),
               ('featured', FeaturedInstallButton))
    for pred, cls in classes:
        if getattr(button, pred, False):
            button.__class__ = cls
            break
    button.prepare()
    return button


class InstallButton(object):
    button_class = ['download']
    install_class = []
    install_text = ''

    def __init__(self, addon, app, lang, version=None, show_contrib=True,
                 show_warning=True, src='', collection=None, size='',
                 detailed=False, impala=False):
        self.addon, self.app, self.lang = addon, app, lang
        self.latest = version is None
        self.version = version or addon.current_version
        self.src = src
        self.collection = collection
        self.size = size
        self.detailed = detailed
        self.impala = impala

        self.unreviewed = addon.is_unreviewed()
        self.featured = (not self.unreviewed
                         and addon.is_featured(app, lang))

        self.is_premium = addon.is_premium()
        self.is_webapp = addon.is_webapp()
        self._show_contrib = show_contrib
        self.show_contrib = show_contrib
        self.show_warning = show_warning and self.unreviewed

    def prepare(self):
        """Called after the class is set to manage contributions."""
        # Get a copy for this instance.
        self.button_class = list(self.__class__.button_class)
        self.install_class = list(self.__class__.install_class)
        if self.show_contrib:
            try:
                self.button_class.remove('download')
            except ValueError:
                pass
            self.button_class += ['contrib', 'go']
            self.install_class.append('contrib')

        if self.size:
            self.button_class.append(self.size)
        if self.is_webapp:
            self.install_class.append('webapp')

    def attrs(self):
        rv = {}
        addon = self.addon
        if self._show_contrib:
            rv['data-after'] = 'contrib'
        if addon.type == amo.ADDON_SEARCH:
            rv['data-search'] = 'true'
        return rv

    def links(self):
        return []

    def fix_link(self, url):
        if self.src:
            url = urlparams(url, src=self.src)
        if self.collection:
            url = urlparams(url, collection_id=self.collection)
        return url


class FeaturedInstallButton(InstallButton):
    install_class = ['featuredaddon']
    install_text = _lazy(u'Featured', 'install_button')


class UnreviewedInstallButton(InstallButton):
    install_class = ['unreviewed']
    install_text = _lazy(u'Not Reviewed', 'install_button')
    button_class = 'download caution'.split()


class LiteInstallButton(InstallButton):
    install_class = ['lite']
    button_class = ['caution']
    install_text = _lazy(u'Experimental', 'install_button')


class Link(object):

    def __init__(self, text, url, os=None, file=None):
        self.text, self.url, self.os, self.file = text, url, os, file


# Cache it for a year.
@cache_page(60 * 60 * 24 * 365)
def js(request):
    return render(request, 'addons/popups.html',
                  content_type='text/javascript')
