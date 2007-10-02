from django import newforms as forms
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

JS_PROTOTYPE = 'js/prototype.js'
JS_EDITOR = 'js/editor.js'
JS_SHOWDOWN = 'js/showdown.js'
JS_MAGICDOM = 'js/MagicDOM.js'

CLASS_RICHTEXTAREA = 'rich_text_area'
CSS_RICHTEXTAREA = 'css/pokus.css'

JS_GENERIC_LOOKUP = 'js/admin/GenericRelatedObjectLookups.js'
JS_JQUERY = 'js/jquery.js'

CLASS_TARGECT = 'target_ct'
CLASS_TARGEID = 'target_id'

class ContentTypeWidget(forms.Select):
    def __init__(self, attrs={}):
        super(ContentTypeWidget, self).__init__(attrs={'class': CLASS_TARGECT})

class ForeignKeyRawIdWidget(forms.TextInput):
    class Media:
        js = (
            settings.ADMIN_MEDIA_PREFIX + JS_JQUERY,
            settings.ADMIN_MEDIA_PREFIX + JS_GENERIC_LOOKUP,
)
    def __init__(self, attrs={}):
        super(ForeignKeyRawIdWidget, self).__init__(attrs={'class': CLASS_TARGEID})

class RichTextAreaWidget(forms.Textarea):
    class Media:
        js = (
            settings.ADMIN_MEDIA_PREFIX + JS_JQUERY,
            settings.ADMIN_MEDIA_PREFIX + JS_EDITOR,
            settings.ADMIN_MEDIA_PREFIX + JS_SHOWDOWN,
            settings.ADMIN_MEDIA_PREFIX + JS_MAGICDOM,
)
    def __init__(self, attrs={}):
        super(RichTextAreaWidget, self).__init__(attrs={'class': CLASS_RICHTEXTAREA})



