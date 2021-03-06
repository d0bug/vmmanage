# -*- coding:utf-8 -*-

import re
import string
import hashlib
import logging
import time
import threading
import datetime
import subprocess
import ConfigParser
import paramiko
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from django.shortcuts import render
from django.http import HttpResponse,HttpResponseRedirect,Http404
from vm.models import VpnUser
from vm.models import Tpl
from vm.models import Info
from vm.models import VmInfo
from django.db.models import Q
from django.utils import simplejson

class VMBase(object):
    def __init__(self):
        conf = ConfigParser.ConfigParser()
        conf.read("/home/django/vmmanage/vm/conf/vm.conf")

        try:
            self.hosts = [ item[1] for item in conf.items("host") ]
            self.admin = [ item[1] for item in conf.items("admin") ]
            self.tplhost = [ item[1] for item in conf.items("tplhost") ]
            self.dhcp = [ item[1] for item in conf.items("dhcp") ][0]
            self.env = [ item[1] for item in conf.items("env") ][0]
        except ConfigParser.NoSectionError,e:
            err = "ConfigParser Error.Details: %s" % e
            self.logrecord('error', err)

    def authsession(self, request, sesskey):
        redirect = 0
        for key in sesskey:
            if not request.session.has_key(key):
                redirect = 1
                break
        return redirect

    def logrecord(self, type, msg):
        log = logging.getLogger(type)
        log.info(msg)

    def remoteexe(self, host, cmd, port=22, user="root", passwd="MhxzKhl"):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port, user, passwd)
            stdin, stdout, stderr = ssh.exec_command(cmd, bufsize=-1)
            result = stdout.readlines()
            error = stderr.read()
        except Exception,e:
            result = ''
            error = "In remoteexe Error: connect %s %s" % (host,str(e))
            self.logrecord('error', error)
        finally:
            ssh.close()
        return result, error

    def pingtest(self, count, host):
        num = 0
        while num < count:
            s = subprocess.Popen("ping %s -c 1" % host, stdout = subprocess.PIPE, shell = True)
            if '1 received' in s.stdout.read():
                return True
            num += 1
        return False

class VMApi(VMBase):
    def __vmstat(self, id):
        err, stat, host = '', '', ''

        try:
            result = Info.objects.filter(id=id)
        except Exception, e:
            err = "Query Info failure.Details: %s" % e
            self.logrecord('error', err)
            return err, stat, host

        if len(result) == 0:
            err = "VM failed: VM does not exist"
            self.logrecord('error', err)
            return err, stat, host

        host = result[0].hostip
        name = result[0].vmname
        result, error = self.remoteexe(host, "virsh list --all")
        if error != '':
            err = "Command exe failed: %s" % error
            self.logrecord('error', err)
            return err, stat, host
        for line in result:
            try:
                line_name = line.split()[1]
                line_stat = string.join(line.split()[2:])
            except IndexError:
                continue
            if name != line_name:
                continue
            else:
                stat = line_stat
                break
        return err, stat, host

    def vmstart(self, id, name):
        err, stat, host = self.__vmstat(id)
        if err != '':
            return err
        elif stat == '':
            err = "VM %s is not in the %s" % (name, host)
            self.logrecord('error', err)
        elif stat == 'running':
            info = "VM %s has started in the %s" % (name, host)
            self.logrecord('info', info)
        else:
            result, error = self.remoteexe(host, "virsh start %s" % name)
            if error != '':
                err = "Command exe failed: %s" % error
                self.logrecord('error', err)
                return err
            result_str = string.join(result, '')
            if u"%s started" % name in result_str or u"%s 已开始" % name in result_str:
                try:
                    Info.objects.filter(id=id).update(vmstatus='START')
                except Exception, e:
                    msg = "Update vmstatus failure.Details: %s" % e
                    self.logrecord('info', msg)
                info = "Start VM %s success" % name
                self.logrecord('info', info)
            else:
                err = "Start VM %s may fail,info: %s" % (name, result_str)
                self.logrecord('error', err)
        return err

    def vmstop(self, id, name):
        err, stat, host = self.__vmstat(id)
        if err != '':
            return err
        elif stat == '':
            err = "VM %s is not in the %s" % (name, host)
            self.logrecord('error', err)
        elif stat == 'shut off':
            info = "VM %s has stoped in the %s" % (name, host)
            self.logrecord('info', info)
        else:
            result, error = self.remoteexe(host, "virsh destroy %s" % name)
            if error != '':
                err = "Command exe failed: %s" % error
                self.logrecord('error', err)
                return err
            result_str = string.join(result, '')
            if u"%s destroyed" % name in result_str or u"%s 被删除" % name in result_str:
                try:
                    Info.objects.filter(id=id).update(vmstatus='STOP')
                except Exception, e:
                    msg = "Update vmstatus failure.Details: %s" % e
                    self.logrecord('info', msg)
                info = "Stop VM %s success" % name
                self.logrecord('info', info)
            else:
                err = "Stop VM %s may fail,info: %s" % (name, result_str)
                self.logrecord('error', err)
        return err

    def vmdel(self, id, name, move='n'):
        err, stat, host = self.__vmstat(id)
        if err != '':
            return err
        elif stat == '':
            err = "VM %s is not in the %s" % (name, host)
            self.logrecord('error', err)
        elif stat == 'running':
            result, error = self.remoteexe(host, "virsh destroy %s" % name)
            if error != '':
                err = "Command exe failed: %s" % error
                self.logrecord('error', err)
                return err
            result_str = string.join(result,'')
            if u"%s destroyed" % name in result_str or u"%s 被删除" % name in result_str:
                try:
                    Info.objects.filter(id=id).update(vmstatus='STOP')
                except Exception, e:
                    msg = "Update vmstatus failure.Details: %s" % e
                    self.logrecord('info', msg)
                info = "Stop VM %s success" % name
                self.logrecord('info', info)
            else:
                err = "Stop VM %s may fail,info: %s" % (name, result_str)
                self.logrecord('error', err)

        #delete vm
        result, error = self.remoteexe(host,"virsh undefine %s" % name)
        if error != '':
            err = "Command exe failed: %s" % error
            self.logrecord('error', err)
            return err
        result_str = string.join(result, '')
        if u"%s has been undefined" % name in result_str or u"%s 已经被取消定义" % name in result_str:
            try:
                Info.objects.filter(id=id).update(vmstatus='DELETE')
            except Exception, e:
                msg = "Update vmstatus failure.Details: %s" % e
                self.logrecord('info', msg)
            info = "Delete VM %s success" % name
            self.logrecord('info', info)
        else:
            err = "Delete VM %s may fail,info: %s" % (name, result_str)
            self.logrecord('error', err)

        if move == 'n':
            #Delete the DHCP MAC record.
            cmd = 'sed -i \'/%s/,+4d\' /etc/dhcp/dhcpd.conf' % name
            _, error = self.remoteexe(self.dhcp, cmd)
            if error != '':
                msg = "In the DHCP %s to delete the DHCP configuration file error" % self.dhcp
                self.logrecord('info', msg)

            #Delete the QA DB record.
            try:
                VmInfo.objects.using('qa').filter(hostname=name).delete()
            except Exception, e:
                msg = "Failed to delete the QA DB data.Details: %s" % e
                self.logrecord('info', msg)

        return err

    def vmmove(self, id, name, dhost):
        err = ''
        err = self.vmdel(id, name, 'y')
        if err != '':
            return err

        cmd = ("rm -rf /etc/libvirt/qemu/%(name)s.xml;"
            "cp /mnt/glusterfs/config/%(name)s.xml /etc/libvirt/qemu/%(name)s.xml;"
            "virsh define /etc/libvirt/qemu/%(name)s.xml"
             % {"name": name})
        result, error = self.remoteexe(dhost, cmd)
        if error != '':
            err = "Command exe failed: %s" % error
            self.logrecord('error', err)
            return err

        result_str = string.join(result, '')
        if u"%s defined from" % name in result_str or u"定义域 %s" % name in result_str:
            try:
                Info.objects.filter(id=id).update(hostip=dhost, vmstatus='STOP')
            except Exception, e:
                err = "Move update error.Details: %s" % e
                self.logrecord('error', err)
                return err

            info = "Define VM %s success" % name
            self.logrecord('info', info)
        else:
            err = "Move VM %s may fail,info: %s" % (name, result_str)
            self.logrecord('error', err)
            return err

        err = self.vmstart(id, name)

        return err

    def vmclone(self, id, vmtpl, vmname, tplhostip, tplvmip, vmowner, vmip, moveip):
        err = ''
        try:
            result = Tpl.objects.filter(tplname=vmtpl)
        except Exception, e:
            err = "Query Tpl failure.Details: %s" % e
            self.logrecord('error', err)
            return err
            
        if len(result) != 1:
            err = "Clone check failed: source vm %s mismatch condition in %s." % (vmtpl, tplhostip)
            self.logrecord('error', err)
            return err

        try:
            result_a = Info.objects.filter(Q(vmname=vmname) & Q(used=0) & ~Q(failed=1) & ~(Q(opexam=1) & Q(passexam=0)))
            result_b = Info.objects.filter(Q(vmname=vmname) & Q(used=1) & ~Q(vmstatus='DELETE'))
        except Exception, e:
            err = "Query Info failure.Details: %s" % e
            self.logrecord('error', err)
            return err

        if len(result_a) != 1 or len(result_b) != 0:
            err = "Clone check failed: dest vm %s mismatch condition." % vmname
            self.logrecord('error', err)
            return err

        try:
            result = Info.objects.filter(Q(vmip=vmip) & Q(used=1) & ~Q(vmstatus='DELETE'))
        except Exception, e:
            err = "Query Info failure.Details: %s" % e
            self.logrecord('error', err)
            return err

        if len(result) != 0:
            err = "Clone check failed: %s already in use" % vmip
            self.logrecord('error', err)
            return err

        info = "Wait for the VM %s to clone..." % vmname
        self.logrecord('info', info)

        clone = Clone(id, vmtpl, vmname, tplhostip, tplvmip, vmowner, vmip, moveip)
        clone.start()

        sendemail = Sendemail(vmowner + '@diditaxi.com.cn', '虚拟机制作中,请耐心等待')
        sendemail.start()

        return err

class Sendemail(threading.Thread, VMBase):
    def __init__(self, msgto, content, title=u"虚拟机管理平台消息"):
        threading.Thread.__init__(self)
        VMBase.__init__(self)
        self.frommail = 'tech-alarm@diditaxi.com.cn'
        self.smtp = 'smtp.exmail.qq.com'
        self.passwd = 'diditaxi@2013'
        self.msgto = msgto
        self.content = content
        self.title = title

    def run(self):
        msg = MIMEMultipart()
        msg['Subject'] = self.title
        msg['From'] = self.frommail
        msg['To'] = self.msgto
        text_att = MIMEText(self.content, 'plain', 'utf-8')
        msg.attach(text_att)
        try:
            smtp = smtplib.SMTP()
            smtp.connect(self.smtp, 25)
            smtp.login(msg['From'], self.passwd)
            smtp.sendmail(msg['From'], msg['To'].split(','), msg.as_string())
        except Exception,e:
            error = "Email error: mail send failed.Details: %s" % e
            self.logrecord('error', error)

class Deployenv(threading.Thread, VMBase):
    def __init__(self, vmip):
        threading.Thread.__init__(self)
        VMBase.__init__(self)
        self.vmip = vmip

    def run(self):
        cmd = ("rsync -av %(host)s::env/xiaoju/nginx /home/xiaoju/;"
            "rsync -av %(host)s::env/xiaoju/php /home/xiaoju/;"
            "rsync -av %(host)s::env/xiaoju/mysql /home/xiaoju/"
             % {"host": self.env})
        result, error = self.remoteexe(self.vmip, cmd)
        if error != '':
            if 'connect' in error:
                msg = "The server connection failed, please try again later."
            else:
                msg = "Command exe failed: %s" % error
            self.logrecord('error', msg)

class Clone(threading.Thread, VMApi):
    def __init__(self, id, vmtpl, vmname, tplhostip, tplvmip, vmowner, vmip, moveip):
        threading.Thread.__init__(self)
        VMApi.__init__(self)
        self.id = id
        self.vmtpl = vmtpl
        self.vmname = vmname
        self.tplhostip = tplhostip
        self.tplvmip = tplvmip
        self.vmowner = vmowner
        self.vmip = vmip
        self.moveip = moveip

    def clonefailed(self):
        try:
            Info.objects.filter(id=self.id).update(failed=1)
        except Exception, e:
            err = "Update Info failed error.Details: %s" % e
            self.logrecord('error', err)

        sendemail = Sendemail(self.vmowner + '@diditaxi.com.cn', '虚拟机制作失败,请联系管理员')
        sendemail.start()

    def run(self):
        #clone vm
        err = ''
        cmd = "virt-clone -o %s -n %s -f /mnt/glusterfs/image/%s.img --force" % (self.vmtpl, self.vmname, self.vmname)
        result, error = self.remoteexe(self.tplhostip, cmd)
        if error != '':
            err = "Command exe failed: %s" % error
            self.logrecord('error', err)
            self.clonefailed()
            return err
        result_str = string.join(result,'')
        if "Clone '%s' created successfully" % self.vmname in result_str:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            exp_time = (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
            try:
                Info.objects.filter(id=self.id).update(hostip=self.tplhostip, vmstatus='STOP', starttime=now, exptime=exp_time, used=1)
            except Exception, e:
                err = "Clone update error.Details: %s" % e
                self.logrecord('error', err)

            #copy xml to glusterfs
            cmd = "rm -rf /mnt/glusterfs/config/%(dname)s.xml;cp /etc/libvirt/qemu/%(dname)s.xml /mnt/glusterfs/config/%(dname)s.xml" % {'dname': self.vmname}
            _, error = self.remoteexe(self.tplhostip, cmd)
            if error != '':
                info = "Copy /etc/libvirt/qemu/%s.xml to /mnt/glusterfs/config/%s.xml field" % (self.dname, self.vmname)
                self.logrecord('info', info)
            info = "Clone VM %s to %s success" % (self.vmtpl, self.vmname)
            self.logrecord('info', info)
        else:
            err = "Clone VM %s may fail,info: %s" % (self.vmname, result_str)
            self.logrecord('error', err)
            self.clonefailed()
            return err

        #The new VM is added to the DHCP server configuration
        cmd = 'awk -F"\'" \'$0~"mac address"{printf("%%s",$2)}\' /etc/libvirt/qemu/%s.xml' % self.vmname
        result, error = self.remoteexe(self.tplhostip, cmd)
        if error != '':
            err = "Get the %s MAC address from the host %s XML failure" % (self.vmname, self.tplhostip)
            self.logrecord('error', err)
            self.clonefailed()
            return err

        mac = result[0]
        dhcpconfadd = ('        host %s {\\\n'
                  '                hardware ethernet %s;\\\n'
                  '                fixed-address %s;\\\n'
                  '        }\\\n' % (self.vmname, mac, self.vmip))

        cmd = 'sed -i \'$i\\%s\' /etc/dhcp/dhcpd.conf;/etc/init.d/dhcpd restart' % dhcpconfadd
        for i in range(3):
            result, error = self.remoteexe(self.dhcp, cmd)
            if error == '':
                break
            time.sleep(10)

        if error != '':
            err = "In the DHCP %s to update the DHCP configuration file or restart DHCP error" % self.dhcp
            self.logrecord('error', err)
            self.clonefailed()
            return err

        info = "Wait for the VM %s to start..." % self.vmname
        self.logrecord('info', info)

        err = self.vmstart(self.id, self.vmname)
        if err != '':
            self.clonefailed()
            return err

        #Wait start ssh
        time.sleep(60)

        if not self.pingtest(180, self.vmip):
            err = "ping %s timeout" % self.vmip
            self.logrecord('error', err)
            self.clonefailed()
            return err

        info = "Configure VM %s network success." % self.vmname
        self.logrecord('info', info)

        err = self.vmmove(self.id, self.vmname, self.moveip)
        if err != '':
            self.clonefailed()
            return err

        sendemail = Sendemail(self.vmowner + '@diditaxi.com.cn', '虚拟机制作完成,请使用\n账号:root\n密码:MhxzKhl')
        sendemail.start()

        #Add record in QA db
        if self.vmtpl == 'qa-tpl' or self.vmtpl == 'wanliu-tpl':
            try:
                VmInfo.objects.using('qa').create(hostname=self.vmname, ip=self.vmip, owner=self.vmowner, role='rd')
            except Exception, e:
                msg = "Insert data into the QA DB failed.Details: %s" % e
                self.logrecord('info', msg)

        return err

class Auth(VMBase):
    '''Class for authentication user.'''
    def __init__(self, dbname='user'):
        super(Auth, self).__init__()
        self.dbname = dbname

    def login(self, request):
        self.username = request.POST.get('username', '')
        self.password = request.POST.get('password', '')

        user_dict = {'username': self.username, 'password': self.password}

        try:
            q_name = Q(username = "%s" % self.username)
            q_active = Q(active = 1)
            result = VpnUser.objects.using(self.dbname).filter(q_name & q_active)
        except Exception, e:
            msg = "Query authentication database failure.Details: %s" % e
            self.logrecord('error', msg)
            return_fe = {'errno': 1, 'errmsg': msg, 'data': user_dict}
            return HttpResponse(simplejson.dumps(return_fe))

        #Authentication success.
        if len(result) == 1 and hashlib.md5(self.password).hexdigest() == result[0].password:
            request.session['username'] = self.username
            request.session['password'] = self.password
            if self.username in self.admin:
                request.session['admin'] = 1
            else:
                request.session['admin'] = 0
            return_fe = {'errno': 0, 'errmsg': ''}
            return HttpResponse(simplejson.dumps(return_fe))

        #Authentication failed.
        return_fe = {'errno': 1, 'errmsg': 'Authentication failed', 'data': user_dict}
        return HttpResponse(simplejson.dumps(return_fe))

    def redirect(self, request):
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if self.authsession(request, ['username', 'password']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if username != self.username or password != self.password:
            return HttpResponseRedirect('http://vm.xiaojukeji.com/login')
        return HttpResponseRedirect('/new/')

    def logout(self, request):
        for sesskey in request.session.keys():
            del request.session[sesskey]
        request.session.flush()

        self.logrecord('error', str(request.session.keys()))
        return HttpResponseRedirect('http://vm.xiaojukeji.com/')

class VMAdd(VMBase):
    '''Class for new template page.'''
    def showtpl(self, request):
        if self.authsession(request, ['username']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')

        try:
            result = Tpl.objects.all()
            tplinfo_list = []
            for tplinfo in result:
                #tplinfo_dict[tplinfo.tplname] = dict([ conf.split(':') for conf in tplinfo.vmconfig.split() ])
                tmp_dict = dict([ conf.split(':') for conf in tplinfo.vmconfig.split() ])
                tmp_dict['chinesename'] = tplinfo.chinesename
                tmp_dict['name'] = tplinfo.tplname
                tplinfo_list.append(tmp_dict)
            return_fe = {'errno': 0, 'errmsg': '', 'data': tplinfo_list}
            return HttpResponse(simplejson.dumps(return_fe))
        except Exception, e:
            msg = "Show tpl failure.Details: %s" % e
            self.logrecord('error', msg)
            return_fe = {'errno': 1, 'errmsg': msg}
            return HttpResponse(simplejson.dumps(return_fe))

    def ensuretpl(self, request):
        if self.authsession(request, ['username']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')

        self.tplname = request.POST.get('tplname', '')
        if not self.tplname:
            return_fe = {'errno': 1, 'errmsg': 'tpl is null'}
            return HttpResponse(simplejson.dumps(return_fe))

        def genvmip():
            err, vmip = '', ''
            vmip_lastone = -1
            #Permission to begin IP the last one.
            beginip = 30

            try:
                #Recovery, not through the examination and approval, the failure to create a reusable VM IP.
                result = Info.objects.filter(~Q(vmstatus='DELETE') & ~(Q(opexam=1) & Q(passexam=0)) & ~Q(failed=1))
            except Exception, e:
                err = "Query Info failure.Details: %s" % e
                return err

            vmip_list = [ record.vmip for record in result if re.match('10.10.8',record.vmip) ]
            #Test data
            if not vmip_list:
                vmip_list = ['10.10.8.30']
            vmip_topthree = vmip_list[0][:vmip_list[0].rindex('.')]
            vmip_lastone_list =  [ int(ip.split('.')[-1]) for ip in vmip_list ]
            vmip_lastone_list.sort()
            for index in range(1,len(vmip_lastone_list)):
                if vmip_lastone_list[index] - vmip_lastone_list[index - 1] != 1 and vmip_lastone_list[index - 1] >= beginip:
                    vmip_lastone = vmip_lastone_list[index - 1] + 1
                    break

            if vmip_lastone == -1:
                vmip_lastone = vmip_lastone_list[-1] + 1

            vmip = string.join((vmip_topthree, str(vmip_lastone)),'.')
            return err, vmip

        def genvmname():
            err, vmname = '', ''
            vm_num = -1
            #Permission to begin vmname number.
            begin = 20

            try:
                result = Info.objects.filter(~Q(vmstatus='DELETE') & ~(Q(opexam=1) & Q(passexam=0)) & ~Q(failed=1))
            except Exception, e:
                err = "Query Info failure.Details: %s" % e
                return err

            vmname_list = [ record.vmname for record in result if record.vmname ]
            #Test data
            if not vmname_list:
                vmname_list = ['vm-001']
            vmname_num = [ int(vm_name.split('-')[-1])  for vm_name in vmname_list if re.match('vm-[0-9]{3}$', vm_name) ]
            vmname_num.sort()
            for index in range(1,len(vmname_num)):
                if vmname_num[index] - vmname_num[index - 1] != 1 and vmname_num[index - 1] >= begin:
                    vm_num = vmname_num[index - 1] + 1
                    break

            if vm_num == -1:
                vm_num = vmname_num[-1] + 1

            if vm_num/10 == 0:
                vm_strnum = string.join(('00', str(vm_num)), '')
            elif vm_num/100 == 0:    
                vm_strnum = string.join(('0', str(vm_num)), '')
            else:
                vm_strnum = str(vm_num)

            vmname = string.join(('vm', vm_strnum),'-')
            return err, vmname

        #Generation vmip and vmname.
        err, vmip = genvmip()
        err, vmname = genvmname()
        if err != '':
            self.logrecord('Generation vmip or vmname error.Details: %s', err)
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        #Within a minute of the same user cannot repeat application.
        try:
            subtime = [time.mktime(t.submittime.utctimetuple()) for t in Info.objects.filter(vmowner=request.session['username'])]
            subtime.sort()
            last_subtime = subtime[-1]
            if time.time() - last_subtime < 60:
                info = "The user %s within a minute repeated submission." % request.session['username']
                self.logrecord('info', info)
                return_fe = {'errno': 2, 'errmsg': info}
                return HttpResponse(simplejson.dumps(return_fe))
        except IndexError:
            pass
        except Exception, e:
            msg = "Gets the user submitted to the time of failure.Details: %s" % e
            self.logrecord('error', msg)

        try:
            Info.objects.create(vmname=vmname, vmip=vmip, vmowner=request.session['username'], tpl=self.tplname, type='new')
        except Exception, e:
            msg = "Insert new VM or query tpl failure.Details: %s" % e
            self.logrecord('error', msg)
            return_fe = {'errno': 1, 'errmsg': msg}
            return HttpResponse(simplejson.dumps(return_fe))

        sendemail = Sendemail(request.session['username'] + '@diditaxi.com.cn', '虚拟机申请提交成功,请等待审批')
        sendemail.start()

        return_fe = {'errno': 0, 'errmsg': ''}
        return HttpResponse(simplejson.dumps(return_fe))

class VMManage(VMApi):
    '''Class for VM manage.'''
    def adminauth(self, request):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')

        if request.session['admin'] == 1:
            return HttpResponseRedirect('/admin-manager/')
        else:
            return HttpResponseRedirect('/admin-users/')

    def usermanage(self, request):
        '''
            The common user management page data.
            The administrator management page data.
            Audit page data.
        '''
        type = {
            'admin': ['hostip', 'vmname', 'vmip', 'vmstatus', 'vmowner', 'tpl', 'exptime', 'status'],
            'user': ['vmip', 'vmstatus', 'tpl', 'exptime', 'status'],
            'audit': ['vmowner', 'submittime', 'tpl', 'hostip', 'vmname', 'vmip', 'type'],
        }
        self.pagetype = request.POST.get('pagetype', '')

        field_list = type.get(self.pagetype)
        if not field_list:
            err = "POST data acquisition failure or incorrect."
            self.logrecord('error', err)
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')

        try:
            if request.session['admin'] == 1:
                result = Info.objects.all()
            else:
                q_name = Q(vmowner = "%s" % request.session['username'])
                result = Info.objects.filter(q_name)
        except Exception, e:
            msg = "Query VM info failure.Details: %s" % e
            self.logrecord('error', msg)
            return_fe = {'errno': 1, 'errmsg': msg}
            return HttpResponse(simplejson.dumps(return_fe))

        vminfo_dict = {}
        vminfo_filter_dict = {}
        vminfo_result = {}
        vminfo_result_list = []
        for vminfo in result:
            #Records of 6 kinds of state.
            # 1 - in use
            # 2 - recovery(delete)
            # 3 - clone failed
            # 4 - waiting for approval
            # 5 - through the approval
            # 6 - not through the approval
            if vminfo.failed:
                status = 3
            elif vminfo.used and vminfo.vmstatus != 'DELETE':
                status = 1
            elif vminfo.used:
                status = 2
            elif not vminfo.opexam:
                status = 4
            elif vminfo.passexam:
                status = 5
            elif not vminfo.passexam:
                status = 6
            else:
                msg = "Record status does not match the expected."
                self.logrecord('error', msg)
                return_fe = {'errno': 1, 'errmsg': msg}
                return HttpResponse(simplejson.dumps(return_fe))

            vminfo_dict[vminfo.id] = dict((['vmname', vminfo.vmname], ['vmip', vminfo.vmip], ['vmowner', vminfo.vmowner],
                                    ['hostip', vminfo.hostip], ['vmstatus', vminfo.vmstatus], ['tpl', vminfo.tpl],
                                    ['type', vminfo.type], ['submittime', str(vminfo.submittime)], ['starttime', str(vminfo.starttime)],
                                    ['exptime', str(vminfo.exptime)], ['status', status]))

        #According to the different page filtering data.
        if self.pagetype == 'admin':
            vminfo_filter_dict = vminfo_dict
        elif self.pagetype == 'user':
            for id in vminfo_dict:
                if vminfo_dict[id]['status'] != 2:
                    vminfo_filter_dict[id] = vminfo_dict[id]
        else:
            for id in vminfo_dict:
                if vminfo_dict[id]['status'] == 4:
                    vminfo_filter_dict[id] = vminfo_dict[id]
        
        for id in vminfo_filter_dict:
            vminfo_result[id] = dict(((field, vminfo_dict[id][field]) for field in field_list))
            vminfo_result[id]['id'] = id

        for id in vminfo_result:
            vminfo_result_list.append(vminfo_result[id])

        return_fe = {'errno': 0, 'errmsg': '', 'data': vminfo_result_list}
        return HttpResponse(simplejson.dumps(return_fe))

    def operation(self, request):
        if self.authsession(request, ['username']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')

        id = request.POST.get('id', '')
        op = request.POST.get('op', '')

        return_fe = {'errno': 0, 'errmsg': ''}

        try:
            vmip = Info.objects.filter(Q(id=id))[0].vmip
            vmname = Info.objects.filter(Q(id=id))[0].vmname
        except Exception, e:
            msg = "Query VM info failure(id=%s).Details: %s" % (id, e)
            self.logrecord('error', msg)
            return_fe = {'errno': 1, 'errmsg': msg}
            return HttpResponse(simplejson.dumps(return_fe))

        #To be change deployenv commond

        if op == 'deployenv':
            env = Deployenv(vmip)
            env.start()
            return_fe = {'errno': 0, 'errmsg': 'In the deployment environment, please later landing.'}
        elif op == 'passwordchange':
            result, error = self.remoteexe(vmip, 'echo MhxzKhl|passwd --stdin root')
            if error != '':
                if 'connect' in error:
                    msg = "The server connection failed, please try again later."
                else:
                    msg = "Command exe failed: %s" % error
                self.logrecord('error', msg)
                return_fe = {'errno': 1, 'errmsg': msg}
        elif op == 'shutdown':
            err = self.vmstop(id, vmname)
            if err != '':
                return_fe = {'errno': 1, 'errmsg': err}
        elif op == 'start':
            err = self.vmstart(id, vmname)
            if err != '':
                return_fe = {'errno': 1, 'errmsg': err}
        elif op == 'reboot':
            err = self.vmstop(id, vmname)
            if err != '':
                return_fe = {'errno': 1, 'errmsg': err}
                return HttpResponse(simplejson.dumps(return_fe))

            err = self.vmstart(id, vmname)
            if err != '':
                return_fe = {'errno': 1, 'errmsg': err}
        elif op == 'delete':
            err = self.vmdel(id, vmname)
            if err != '':
                return_fe = {'errno': 1, 'errmsg': err}
        elif op == 'renew':
            exp_time = (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
            try:
                Info.objects.filter(id=id).update(exptime=exp_time)
            except Exception, e:
                err = "Update exptime failure.Details: %s" % e
                self.logrecord('error', err)
                return_fe = {'errno': 1, 'errmsg': err}
        else:
            err = "The post data op is not defined."
            self.logrecord('error', err)
            return_fe = {'errno': 1, 'errmsg': err}
            
        return HttpResponse(simplejson.dumps(return_fe))

    def approval(self, request):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        id = request.POST.get('id', '')
        apppass = request.POST.get('yorn', '')

        return_fe = {'errno': 0, 'errmsg': ''}
        err = ''
        
        if apppass == 'y':
            err = self.approvalpass(request, id)
        elif apppass == 'n':
            err = self.approvalnopass(request, id)

            try:
                vmowner = Info.objects.filter(Q(id=id))[0].vmowner
                sendemail = Sendemail(vmowner + '@diditaxi.com.cn', '虚拟机申请未通过审批')
                sendemail.start()
            except Exception, e:
                err = "Query vmowner failure(id=%s).Details: %s" % (id, e)
                self.logrecord('error', err)
        else:
            err = "The post data apppass is not defined."

        if err != '':
            return_fe = {'errno': 1, 'errmsg': err}

        return HttpResponse(simplejson.dumps(return_fe))

    def approvalpass(self, request, id):

        err = ''
        try:
            vmip = Info.objects.filter(Q(id=id))[0].vmip
            vmname = Info.objects.filter(Q(id=id))[0].vmname
            vmtpl = Info.objects.filter(Q(id=id))[0].tpl
            tplhostip = Tpl.objects.filter(Q(tplname=vmtpl))[0].hostip
            tplvmip = Tpl.objects.filter(Q(tplname=vmtpl))[0].vmip
            vmowner = Info.objects.filter(Q(id=id))[0].vmowner
        except Exception, e:
            err = "Query VM or tpl info failure(id=%s).Details: %s" % (id, e)
            self.logrecord('error', err)
            return err

        #Choose the least loaded host
        load_dict = {}
        cmd = ('cpunum=`cat /proc/cpuinfo |grep "processor"|wc -l`;'
            'awk \'{printf(\"%f\",$2/($1*\"\'$cpunum\'\"))}\' /proc/uptime')
        for host in self.hosts:
            result, error = self.remoteexe(host, cmd)
            if error != '':
                err = "Command exe failed: %s" % error
                self.logrecord('error', err)
                return err
            try:
                load_dict[host] = float(result[0])
            except Exception, e:
                self.logrecord('error', 'Conversion failed float.')

        idle = [k for k in load_dict if load_dict[k] == max(load_dict.values())]
        if len(idle) == 0:
            err = "The load_dict element is 0."
            self.logrecord('error', err)
            return err

        moveip = idle[0]

        try:
            Info.objects.filter(id=id).update(opexam=1, passexam=1)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
            return err

        err = self.vmclone(id, vmtpl, vmname, tplhostip, tplvmip, vmowner, vmip, moveip)
        if err != '':
            try:
                Info.objects.filter(id=id).update(failed=1)
            except Exception, e:
                err = "Update Info failed error.Details: %s" % e
                self.logrecord('error', err)

            sendemail = Sendemail(vmowner + '@diditaxi.com.cn', '虚拟机制作失败,请联系管理员')
            sendemail.start()

        return err

    def approvalnopass(self, request, id):

        err = ''
        try:
            Info.objects.filter(id=id).update(opexam=1, passexam=0)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
            #return_fe = {'errno': 1, 'errmsg': err}
        return err

class ChangeField(VMBase):
    def changefield(self, request):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))
        
        id = request.POST.get('id', '')
        change = request.POST.get('changefield', '')
        value = request.POST.get('value', '')

        return_fe = {'errno': 0, 'errmsg': ''}

        method = {
                    'changeowner': self.changeowner, 
                    'changeexp': self.changeexp, 
                    'changetpl': self.changetpl, 
                    'changeip': self.changeip, 
                    'changevmip': self.changevmip
                 }

        if change not in method:
            err = "The post data changefield is not defined."
            self.logrecord('error', err)
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        err = method[change](request, id, value)

        if err != '':
            return_fe = {'errno': 1, 'errmsg': err}

        return HttpResponse(simplejson.dumps(return_fe))

    def changeowner(self, request, id, owner):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))
        err = ''

        try:
            result = VpnUser.objects.using('user').filter(username=owner)
        except Exception, e:
            err = "Query VpnUser error.Details: %s" % e
            self.logrecord('error', err)
            return err

        if len(result) != 1:
            err = "Input the owner %s is invalid." % owner
            self.logrecord('error', err)
            return err

        try:
            Info.objects.filter(id=id).update(vmowner=owner)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
        return err

    def changeexp(self, request, id, exp_str):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        err = ''

        try:
            exp_timestamp = time.mktime(time.strptime(exp_str, "%Y-%m-%d %H:%M:%S"))
        except Exception, e:
            err = "Input time format error."
            self.logrecord('error', err)
            return err

        now = time.time()
        if exp_timestamp < now or exp_timestamp > now + (3600 * 24 * 360):
            err = "Input the time is out of range."
            self.logrecord('error', err)
            return err

        try:
            Info.objects.filter(id=id).update(exptime=exp_str)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
        return err

    def changetpl(self, request, id, tpl):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        err = ''

        try:
            result = Tpl.objects.filter(tplname=tpl)
        except Exception, e:
            err = "Query Tpl error.Details: %s" % e
            self.logrecord('error', err)
            return err

        if len(result) != 1:
            err = "Input the tpl %s is invalid." % tpl
            self.logrecord('error', err)
            return err

        try:
            Info.objects.filter(id=id).update(tpl=tpl)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
        return err

    def changeip(self, request, id, ip):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return_fe = {'errno': 1, 'errmsg': err}
            return HttpResponse(simplejson.dumps(return_fe))

        err =''

        if ip not in self.hosts:
            err = "Input the ip %s not in the host list." % ip
            self.logrecord('error', err)
            return err

        try:
            Info.objects.filter(id=id).update(hostip=ip)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
        return err

    def changevmip(self, request, id, vmip):
        if self.authsession(request, ['username', 'admin']):
            return HttpResponseRedirect('http://vm.xiaojukeji.com/')
        if request.session['admin'] != 1:
            err = "Restricted permissions."
            return err
        err = ''

        re_ip = '''^(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.\
(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.\
(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.\
(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])$'''

        try:
            result = Info.objects.filter(Q(vmip=vmip) & Q(used=1) & ~Q(vmstatus='DELETE'))
        except Exception, e:
            err = "Query Info error.Details: %s" % e
            self.logrecord('error', err)
            return err

        if not re.compile(re_ip).search(vmip) or len(result) != 0:
            err = "Input the vmip %s format is invalid or already in use." % vmip
            self.logrecord('error', err)
            return err

        try:
            Info.objects.filter(id=id).update(vmip=vmip)
        except Exception, e:
            err = "Update Info error.Details: %s" % e
            self.logrecord('error', err)
        return err
