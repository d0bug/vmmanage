from django.conf.urls import patterns, include, url
from vm.views import Auth, VMAdd, VMManage, ChangeField

from django.contrib import admin


auth = Auth()
v = VMAdd()
vm = VMManage()
c = ChangeField()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'vmmanage.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^auth/$', auth.login),
    url(r'^authredirect/$', auth.redirect),
    url(r'^logout/$', auth.logout),
#    url(r'^new/$', v.pubredirect),
    url(r'^add/$', v.showtpl),
    url(r'^enadd/$', v.ensuretpl),
    url(r'^adminauth/$', vm.adminauth),
    url(r'^usermanage/$', vm.usermanage),
    url(r'^operation/$', vm.operation),
    url(r'^changefield/$', c.changefield),
    url(r'^approvalaction/$', vm.approval),

    url(r'^redirect/$', auth.redirect),
#    url(r'^fe-adminmanage/$', auth.test),
#    url(r'^fe-manage/$', auth.test),
)
